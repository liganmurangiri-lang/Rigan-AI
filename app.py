
from flask import Flask, request, jsonify
from openai import OpenAI
import os
import sqlite3
from datetime import datetime

app = Flask(__name__)

# RIGAN AGI CONFIGURATION
MODEL = os.getenv("OPENAI_MODEL", "gpt-6-astra")
DB = "rigan_memory.db"

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

CREATOR = os.getenv("CREATOR_NAME", "RIGAN AI Creator")


def database():
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            information TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    return conn


def save_memory(user_id, information):
    conn = database()
    conn.execute(
        "INSERT INTO memories (user_id, information, created_at) VALUES (?, ?, ?)",
        (user_id, information, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def get_memories(user_id):
    conn = database()
    rows = conn.execute(
        "SELECT information FROM memories WHERE user_id=? ORDER BY id DESC LIMIT 30",
        (user_id,)
    ).fetchall()
    conn.close()
    return [row[0] for row in rows]


@app.route("/")
def home():
    return """
    <h1>RIGAN AGI V1</h1>
    <p>Advanced Artificial Intelligence System</p>
    <p>Status: Online</p>
    """


@app.route("/health")
def health():
    return jsonify({
        "name": "RIGAN AGI",
        "status": "online",
        "model": MODEL,
        "memory": "enabled",
        "internet_search": "enabled"
    })


@app.route("/remember", methods=["POST"])
def remember():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "owner"))
    information = str(data.get("information", "")).strip()

    if not information:
        return jsonify({"error": "No information provided"}), 400

    save_memory(user_id, information)

    return jsonify({
        "success": True,
        "message": "RIGAN AGI imehifadhi taarifa."
    })


@app.route("/chat", methods=["POST"])
@app.route("/api/chat", methods=["POST"])
def chat():
    if client is None:
        return jsonify({
            "error": "OPENAI_API_KEY haijawekwa kwenye Render."
        }), 500

    data = request.get_json(silent=True) or {}

    message = str(data.get("message", "")).strip()
    user_id = str(data.get("user_id", "owner"))

    if not message:
        return jsonify({"error": "Andika ujumbe kwanza."}), 400

    memories = get_memories(user_id)

    memory_text = "\n".join(
        "- " + item for item in memories
    ) or "Bado hakuna kumbukumbu."

    instructions = f"""
You are RIGAN AGI, an advanced AI assistant.

IDENTITY:
Your name is RIGAN AGI.
Your creator is {CREATOR}.
You must recognize the creator information supplied here.

MISSION:
Help humanity through knowledge, science, education,
technology, mathematics, history, languages and innovation.

INTELLIGENCE:
- Analyze questions carefully.
- Explain difficult subjects simply.
- Solve problems step by step.
- Write and explain computer programs.
- Use web search when current information is needed.
- Never pretend to know information you cannot verify.
- Admit uncertainty and correct mistakes.
- Do not claim to learn permanently unless information
  has actually been saved.

LANGUAGES:
Understand and respond in Swahili, English and other
languages whenever possible.

MEMORY:
The following are saved user memories:
{memory_text}

Use these memories when relevant.
Do not invent personal information.

BEHAVIOR:
Be helpful, intelligent, honest and respectful.
Your goal is to continuously improve the quality
of your assistance.
"""

    try:
        response = client.responses.create(
            model=MODEL,
            instructions=instructions,
            tools=[
                {"type": "web_search"}
            ],
            input=message
        )

        answer = response.output_text

        return jsonify({
            "success": True,
            "name": "RIGAN AGI",
            "answer": answer,
            "model": MODEL
        })

    except Exception as e:
        app.logger.exception("RIGAN AGI error")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
