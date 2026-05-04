import json
import os
import secrets
import uuid
from pathlib import Path
from time import time

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from flask import Flask, jsonify, render_template, request, session

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fitmind-dev-secret")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

REGION = os.environ.get("AWS_REGION", "us-east-1")
KNOWLEDGE_BASE_ID = os.environ.get("BEDROCK_KNOWLEDGE_BASE_ID", "")
MODEL_ARN = os.environ.get("BEDROCK_MODEL_ARN", "")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0")
MAX_HISTORY = 12
MAX_CHATS = 6
CHAT_STORAGE_DIR = Path(app.instance_path) / "chat_sessions"
CHAT_SESSION_TTL_SECONDS = 60 * 60 * 24 * 2


def ensure_chat_storage_dir() -> None:
    CHAT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def cleanup_expired_chat_sessions() -> None:
    ensure_chat_storage_dir()
    cutoff = time() - CHAT_SESSION_TTL_SECONDS

    for session_file in CHAT_STORAGE_DIR.glob("*.json"):
        try:
            if session_file.stat().st_mtime < cutoff:
                session_file.unlink()
        except OSError:
            continue


def get_session_chat_id() -> str:
    session_chat_id = session.get("chat_session_id")

    if session_chat_id:
        return session_chat_id

    session_chat_id = secrets.token_hex(16)
    session["chat_session_id"] = session_chat_id
    session.modified = True
    return session_chat_id


def get_chat_store_path() -> Path:
    cleanup_expired_chat_sessions()
    return CHAT_STORAGE_DIR / f"{get_session_chat_id()}.json"


def clear_current_chat_store() -> None:
    store_path = get_chat_store_path()

    try:
        if store_path.exists():
            store_path.unlink()
    except OSError:
        pass


def load_chats_from_store() -> list:
    store_path = get_chat_store_path()

    if not store_path.exists():
        return []

    try:
        with store_path.open("r", encoding="utf-8") as handle:
            stored = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []

    return stored if isinstance(stored, list) else []


def save_chats_to_store(chats: list) -> None:
    store_path = get_chat_store_path()
    temp_path = store_path.with_suffix(".tmp")

    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(chats[:MAX_CHATS], handle, ensure_ascii=False)

    temp_path.replace(store_path)


def new_chat(title: str = "New chat") -> dict:
    return {
        "id": uuid.uuid4().hex[:10],
        "title": title,
        "messages": [],
    }


def get_chats() -> list:
    chats = load_chats_from_store()

    if chats:
        return chats

    first_chat = new_chat("Current chat")
    session["active_chat_id"] = first_chat["id"]
    save_chats_to_store([first_chat])
    return [first_chat]


def get_active_chat(chats: list) -> dict:
    active_chat_id = session.get("active_chat_id")

    for chat in chats:
        if chat["id"] == active_chat_id:
            return chat

    session["active_chat_id"] = chats[0]["id"]
    return chats[0]


def save_chats(chats: list) -> None:
    save_chats_to_store(chats)
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


def reset_browser_session_chats() -> tuple[list, dict]:
    clear_current_chat_store()
    session.pop("active_chat_id", None)
    replacement_chat = new_chat("Current chat")
    session["active_chat_id"] = replacement_chat["id"]
    save_chats_to_store([replacement_chat])
    session.modified = True
    return [replacement_chat], replacement_chat


def build_chat_summaries(chats: list) -> list:
    summaries = []

    for chat in chats:
        last_user_message = next(
            (message for message in reversed(chat["messages"]) if message["role"] == "user"),
            None,
        )
        preview_source = last_user_message["text"] if last_user_message else "Start a new recipe or healthy eating question."
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


def submit_question(chats: list, active_chat: dict, question: str, answer_style: str) -> dict:
    result = query_bedrock_knowledge_base(question, answer_style)

    if active_chat["title"] in {"New chat", "Current chat"}:
        active_chat["title"] = question[:42] + ("..." if len(question) > 42 else "")

    chat_history = active_chat["messages"]
    user_message = {"role": "user", "label": "Your note", "text": question}
    bot_message = {
        "role": "bot",
        "label": "Journal answer",
        "text": result["answer"],
        "source": result["source"],
        "answer_style": answer_style,
    }

    chat_history.append(user_message)
    chat_history.append(bot_message)
    chat_history = chat_history[-MAX_HISTORY:]
    active_chat["messages"] = chat_history
    save_chats(chats)

    return {
        "user_message": user_message,
        "bot_message": bot_message,
        "active_chat_id": active_chat["id"],
        "active_chat_title": active_chat["title"],
        "chat_summaries": build_chat_summaries(chats),
    }


def resolve_model_arn() -> str:
    if MODEL_ARN:
        return MODEL_ARN

    if not MODEL_ID:
        return ""

    if MODEL_ID.startswith("arn:"):
        return MODEL_ID

    if MODEL_ID.startswith(("global.", "us.", "eu.", "apac.", "au.")):
        return MODEL_ID

    resource_type = "foundation-model"
    return f"arn:aws:bedrock:{REGION}::{resource_type}/{MODEL_ID}"


def describe_runtime_identity() -> str:
    try:
        sts_client = boto3.client("sts", region_name=REGION)
        identity = sts_client.get_caller_identity()
        account_id = identity.get("Account", "unknown-account")
        return f"region={REGION}, account={account_id}"
    except Exception:
        return f"region={REGION}, account=unavailable"


def query_bedrock_knowledge_base(question: str, answer_style: str = "simple") -> dict:
    model_arn = resolve_model_arn()

    if not KNOWLEDGE_BASE_ID or not model_arn:
        return {
            "answer": "The knowledge base is not configured yet. Add AWS_REGION, BEDROCK_KNOWLEDGE_BASE_ID, and either BEDROCK_MODEL_ID or BEDROCK_MODEL_ARN, then try again.",
            "source": "App setup needed",
        }

    if answer_style == "simple":
        style_prompt = (
            "Answer in a short, clear, friendly way. "
            "Use simple language and keep it practical."
        )
    else:
        style_prompt = (
            "Answer in a clear, detailed, well-structured way. "
            "Explain the idea step by step when useful."
        )

    prompt = f"""
You are a healthy recipe and food habit assistant.

Use only the information retrieved from the knowledge base.
If the knowledge base does not contain enough information, say that clearly.
Do not make up facts.
Keep the answer focused on recipes, ingredients, meals, or healthy eating habits.

{style_prompt}

User question:
{question}
""".strip()
    client = boto3.client("bedrock-agent-runtime", region_name=REGION)

    try:
        response = client.retrieve_and_generate(
            input={"text": prompt},
            retrieveAndGenerateConfiguration={
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": KNOWLEDGE_BASE_ID,
                    "modelArn": model_arn,
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
            "answer": "AWS credentials are missing, so the app cannot reach Bedrock right now.",
            "source": "AWS sign-in needed",
        }
    except ClientError as exc:
        error_message = exc.response.get("Error", {}).get("Message", str(exc))
        runtime_identity = describe_runtime_identity()
        return {
            "answer": f"Bedrock returned an error while trying to answer your question: {error_message} ({runtime_identity}, kb={KNOWLEDGE_BASE_ID})",
            "source": "Amazon Bedrock error",
        }
    except Exception as exc:  # pragma: no cover - AWS runtime behavior
        return {
            "answer": "Something unexpected happened while generating the answer. Please try again.",
            "source": "App runtime issue",
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

        if action == "reset_session":
            chats, active_chat = reset_browser_session_chats()
            return render_home("", chats, active_chat, [])

        if action == "clear":
            active_chat["messages"] = []
            save_chats(chats)
            return render_home("", chats, active_chat, [])

        question = request.form.get("question", "").strip()
        answer_style = request.form.get("answer_style", "simple")

        if question:
            submit_question(chats, active_chat, question, answer_style)
            chat_history = active_chat["messages"]

    return render_home(question, chats, active_chat, chat_history)


@app.route("/ask", methods=["POST"])
def ask():
    chats = get_chats()
    active_chat = get_active_chat(chats)
    question = request.form.get("question", "").strip()
    answer_style = request.form.get("answer_style", "simple")

    if not question:
        return jsonify({"error": "Question is required."}), 400

    payload = submit_question(chats, active_chat, question, answer_style)
    return jsonify(payload)


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
