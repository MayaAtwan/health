import json
import os
import uuid
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from flask import Flask, render_template, request, session

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fitmind-dev-secret")

REGION = os.environ.get("AWS_REGION", "us-east-1")
KNOWLEDGE_BASE_ID = os.environ.get("BEDROCK_KNOWLEDGE_BASE_ID", "")
MODEL_ARN = os.environ.get("BEDROCK_MODEL_ARN", "")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0")
AGENT_ID = os.environ.get("BEDROCK_AGENT_ID", "")
AGENT_ALIAS_ID = os.environ.get("BEDROCK_AGENT_ALIAS_ID", "")
MAX_HISTORY = 12
MAX_CHATS = 6


def new_chat(title: str = "New chat") -> dict:
    return {
        "id": uuid.uuid4().hex[:10],
        "title": title,
        "messages": [],
    }


def get_chats() -> list:
    chats = session.get("chats")

    if chats:
        return chats

    legacy_history = session.pop("chat_history", [])
    first_chat = new_chat("Current chat")
    first_chat["messages"] = legacy_history
    session["chats"] = [first_chat]
    session["active_chat_id"] = first_chat["id"]
    return session["chats"]


def get_active_chat(chats: list) -> dict:
    active_chat_id = session.get("active_chat_id")

    for chat in chats:
        if chat["id"] == active_chat_id:
            return chat

    session["active_chat_id"] = chats[0]["id"]
    return chats[0]


def save_chats(chats: list) -> None:
    session["chats"] = chats[:MAX_CHATS]
    session.modified = True


def delete_chat(chats: list, chat_id: str) -> tuple[list, dict]:
    remaining_chats = [chat for chat in chats if chat["id"] != chat_id]

    if not remaining_chats:
        replacement_chat = new_chat()
        remaining_chats = [replacement_chat]

    if session.get("active_chat_id") == chat_id:
        session["active_chat_id"] = remaining_chats[0]["id"]

    active_chat = get_active_chat(remaining_chats)
    save_chats(remaining_chats)
    return remaining_chats, active_chat


def build_chat_summaries(chats: list) -> list:
    summaries = []

    for chat in chats:
        last_user_message = next(
            (message for message in reversed(chat["messages"]) if message["role"] == "user"),
            None,
        )
        preview_source = last_user_message["text"] if last_user_message else "Start a new fitness question."
        preview = preview_source[:68] + ("..." if len(preview_source) > 68 else "")

        summaries.append({
            "id": chat["id"],
            "title": chat["title"],
            "preview": preview,
            "message_count": len(chat["messages"]),
        })

    return summaries


def render_home(question: str, chats: list, active_chat: dict, chat_history: list | None = None):
    return render_template(
        "index.html",
        question=question,
        chat_history=active_chat["messages"] if chat_history is None else chat_history,
        chats=chats,
        chat_summaries=build_chat_summaries(chats),
        active_chat_id=active_chat["id"],
    )


def claude_complete(prompt: str) -> str:
    bedrock = boto3.client("bedrock-runtime", region_name=REGION)

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 400,
        "temperature": 0.2,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    }

    try:
        resp = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        payload = resp["body"].read()
        data = json.loads(payload)
        parts = data.get("content", [])
        text = "".join(
            part.get("text", "")
            for part in parts
            if isinstance(part, dict) and part.get("type") == "text"
        )
        return text.strip()
    except ClientError as exc:
        msg = exc.response.get("Error", {}).get("Message", str(exc))
        raise RuntimeError(f"Bedrock InvokeModel failed: {msg}") from exc


def invoke_bedrock_agent(prompt: str) -> str:
    if not AGENT_ID or not AGENT_ALIAS_ID:
        return "Set BEDROCK_AGENT_ID and BEDROCK_AGENT_ALIAS_ID to use a Bedrock Agent."

    client = boto3.client("bedrock-agent-runtime", region_name=REGION)
    session_id = str(uuid.uuid4())

    try:
        response = client.invoke_agent(
            agentId=AGENT_ID,
            agentAliasId=AGENT_ALIAS_ID,
            sessionId=session_id,
            inputText=prompt,
        )

        output_parts = []

        for event in response.get("completion", []):
            chunk = event.get("chunk")
            if chunk and "bytes" in chunk:
                output_parts.append(chunk["bytes"].decode("utf-8"))

        return "".join(output_parts).strip()
    except NoCredentialsError:
        return "AWS credentials were not found."
    except ClientError as exc:
        return f"AWS error: {exc.response['Error']['Message']}"
    except Exception as exc:  # pragma: no cover - AWS runtime behavior
        return f"Unexpected error: {exc}"


def query_bedrock_knowledge_base(question: str, answer_style: str = "simple") -> dict:
    if not KNOWLEDGE_BASE_ID or not MODEL_ARN:
        return {
            "answer": "Set BEDROCK_KNOWLEDGE_BASE_ID and BEDROCK_MODEL_ARN before querying the knowledge base.",
            "source": "Configuration needed",
            "related_questions": [],
        }

    style_prompt = "Answer simply and clearly." if answer_style == "simple" else "Answer in detail."
    prompt = f"{style_prompt} Use the knowledge base results only.\n\nQuestion: {question}"
    client = boto3.client("bedrock-agent-runtime", region_name=REGION)

    try:
        response = client.retrieve_and_generate(
            input={"text": prompt},
            retrieveAndGenerateConfiguration={
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": KNOWLEDGE_BASE_ID,
                    "modelArn": MODEL_ARN,
                    "retrievalConfiguration": {
                        "vectorSearchConfiguration": {
                            "numberOfResults": 5,
                        }
                    },
                },
            },
        )
    except NoCredentialsError:
        return {
            "answer": "AWS credentials were not found.",
            "source": "AWS credentials",
            "related_questions": [],
        }
    except ClientError as exc:
        return {
            "answer": f"AWS error: {exc.response['Error']['Message']}",
            "source": "Amazon Bedrock",
            "related_questions": [],
        }
    except Exception as exc:  # pragma: no cover - AWS runtime behavior
        return {
            "answer": f"Unexpected error: {exc}",
            "source": "Amazon Bedrock",
            "related_questions": [],
        }

    citations = response.get("citations", [])
    source_names = []

    for citation in citations:
        for reference in citation.get("retrievedReferences", []):
            location = reference.get("location", {})
            s3_uri = location.get("s3Location", {}).get("uri")
            web_url = location.get("webLocation", {}).get("url")
            source_value = s3_uri or web_url
            if source_value and source_value not in source_names:
                source_names.append(source_value)

    return {
        "answer": response.get("output", {}).get("text", "").strip() or "No answer returned from Bedrock.",
        "source": ", ".join(source_names[:2]) if source_names else "Amazon Bedrock Knowledge Base",
        "related_questions": [
            "Can you summarize that answer?",
            "Which document did this come from?",
        ],
    }


@app.route("/", methods=["GET", "POST"])
def home():
    chats = get_chats()
    active_chat = get_active_chat(chats)
    chat_history = active_chat["messages"]
    question = ""

    if request.method == "POST":
        action = request.form.get("action")

        if action == "new_chat":
            active_chat = new_chat()
            chats.insert(0, active_chat)
            session["active_chat_id"] = active_chat["id"]
            save_chats(chats)
            return render_home("", chats, active_chat, [])

        if action == "switch_chat":
            requested_chat_id = request.form.get("chat_id")
            if any(chat["id"] == requested_chat_id for chat in chats):
                session["active_chat_id"] = requested_chat_id
            active_chat = get_active_chat(chats)
            return render_home("", chats, active_chat)

        if action == "delete_chat":
            requested_chat_id = request.form.get("chat_id", "")
            if any(chat["id"] == requested_chat_id for chat in chats):
                chats, active_chat = delete_chat(chats, requested_chat_id)
            else:
                active_chat = get_active_chat(chats)
            return render_home("", chats, active_chat)

        if action == "clear":
            active_chat["messages"] = []
            save_chats(chats)
            return render_home("", chats, active_chat, [])

        question = request.form.get("question", "").strip()
        answer_style = request.form.get("answer_style", "simple")

        if question:
            result = query_bedrock_knowledge_base(question, answer_style)
            if active_chat["title"] in {"New chat", "Current chat"}:
                active_chat["title"] = question[:42] + ("..." if len(question) > 42 else "")

            chat_history.append({"role": "user", "label": "Your mission", "text": question})
            chat_history.append({
                "role": "bot",
                "label": "Coach answer",
                "text": result["answer"],
                "source": result["source"],
                "related_questions": result["related_questions"],
                "answer_style": answer_style,
            })
            chat_history = chat_history[-MAX_HISTORY:]
            active_chat["messages"] = chat_history
            save_chats(chats)

    return render_home(question, chats, active_chat, chat_history)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
