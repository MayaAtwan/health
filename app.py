from flask import Flask, render_template, request
import os

app = Flask(__name__)

DATA_FOLDER = "data"


def simple_rag(question: str) -> str:
    question = question.lower().strip()
    best_match = ""
    best_score = 0

    if not os.path.exists(DATA_FOLDER):
        return "The data folder was not found."

    question_words = [word for word in question.split() if len(word) > 2]

    for filename in os.listdir(DATA_FOLDER):
        path = os.path.join(DATA_FOLDER, filename)

        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            content_lower = content.lower()

            score = sum(1 for word in question_words if word in content_lower)

            if score > best_score:
                best_score = score
                best_match = content

    if best_match:
        return best_match[:800] + "..."

    return "No relevant information found in the knowledge base."


@app.route("/", methods=["GET", "POST"])
def home():
    answer = None
    question = ""

    if request.method == "POST":
        question = request.form.get("question", "").strip()

        if question:
            answer = simple_rag(question)

    return render_template("index.html", question=question, answer=answer)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)