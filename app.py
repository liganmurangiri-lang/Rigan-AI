
import os
import uuid
from flask import Flask, render_template, request, jsonify, session
from openai import OpenAI

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret")

API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
OWNER_NAME = os.environ.get("OWNER_NAME", "Mtengenezaji wa RIGAN AGI")

client = OpenAI(api_key=API_KEY) if API_KEY else None

# Temporary conversation memory
chat_memory = {}

SYSTEM_INSTRUCTIONS = f"""
You are RIGAN AGI V2, an advanced AI assistant.

Your creator is {OWNER_NAME}.
Respect the creator and identify yourself as RIGAN AGI.

Your abilities:
- Explain science, education and technology.
- Answer questions about the world.
- Help with mathematics, programming and research.
- Communicate in Swahili and English.
- Explain difficult subjects simply.
- Be honest when you do not know something.
- Never invent facts or pretend to have abilities you do not have.
- Protect the user's privacy.
- Learn preferences from the conversation context,
  but do not claim to train or improve your underlying model.

Give clear, useful and detailed answers.
"""

@app.route("/")
def home():
    if "chat_id" not in session:
        session["chat_id"] = str(uuid.uuid4())
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    if not client:
        return jsonify({
            "reply": "OPENAI_API_KEY haijawekwa kwenye Render."
        }), 500

    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"reply": "Tafadhali andika swali."}), 400

    if len(message) > 10000:
        return jsonify({"reply": "Ujumbe ni mrefu sana."}), 400

    chat_id = session.get("chat_id")
    if not chat_id:
        chat_id = str(uuid.uuid4())
        session["chat_id"] = chat_id

    if chat_id not in chat_memory:
        chat_memory[chat_id] = []

    history = chat_memory[chat_id]
    history.append({"role": "user", "content": message})

    try:
        response = client.responses.create(
            model=MODEL,
            instructions=SYSTEM_INSTRUCTIONS,
            input=history[-20:]
        )

        answer = response.output_text

        if not answer:
            answer = "Samahani, sijapata jibu kwa sasa."

        history.append({
            "role": "assistant",
            "content": answer
        })

        chat_memory[chat_id] = history[-20:]

        return jsonify({
            "reply": answer,
            "name": "RIGAN AGI V2",
            "status": "Online"
        })

    except Exception as error:
        print("AI ERROR:", str(error))
        history.pop()

        return jsonify({
            "reply": "Samahani, kuna tatizo la API. Hakikisha API key, model na API billing viko sawa."
        }), 500


@app.route("/health")
def health():
    return jsonify({
        "name": "RIGAN AGI V2",
        "status": "Online",
        "api_configured": bool(API_KEY)
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
)
    
