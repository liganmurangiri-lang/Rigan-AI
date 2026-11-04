
import os
import uuid
from datetime import datetime, timezone

from flask import Flask, request, jsonify, session, render_template_string
from openai import OpenAI
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# ==================================
# RIGAN AGI V15
# ==================================

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "rigan-v15-change-this-secret")

OWNER_NAME = os.environ.get("OWNER_NAME", "RIGAN Creator")

# OpenRouter configuration
API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "openrouter/free")

client = None

if API_KEY:
    client = OpenAI(
        api_key=API_KEY,
        base_url="https://openrouter.ai/api/v1",
        timeout=90.0,
        max_retries=2
    )

# ==================================
# DATABASE
# ==================================

Base = declarative_base()

DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or os.environ.get("DATABASE_URI")
)

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://", "postgresql+psycopg://", 1
        )
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )
else:
    DATABASE_URL = "sqlite:///rigan_v15.db"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False
)


class ChatMemory(Base):
    __tablename__ = "rigan_memory"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(100), index=True, nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


try:
    Base.metadata.create_all(bind=engine)
    print("RIGAN DATABASE READY")
except SQLAlchemyError as error:
    print("DATABASE WARNING:", str(error))


# ==================================
# AI PERSONALITY
# ==================================

SYSTEM_PROMPT = f"""
You are RIGAN AGI V15.

Your creator and owner is {OWNER_NAME}.

Your identity is RIGAN AGI V15.

Your responsibilities:
1. Answer questions accurately and clearly.
2. Understand and communicate in Swahili and English.
3. Help with science, education, technology, mathematics,
   history, business and general knowledge.
4. Explain difficult subjects in simple language.
5. Remember relevant previous conversations when available.
6. Never invent facts when you are uncertain.
7. Treat the user respectfully.
8. Give useful examples and step-by-step instructions.
9. Do not claim to have learned permanently unless information
   has actually been saved in your database.

You are an AI assistant called RIGAN AGI V15.
"""


# ==================================
# HOME PAGE
# ==================================

HTML = """
<!DOCTYPE html>
<html lang="sw">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RIGAN AGI V15</title>

<style>
* { box-sizing: border-box; }

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #101827;
    color: white;
}

header {
    background: #17243a;
    padding: 17px;
    text-align: center;
    border-bottom: 1px solid #334155;
}

header h2 {
    margin: 0;
    color: #38bdf8;
}

header p {
    margin-bottom: 0;
    color: #cbd5e1;
    font-size: 13px;
}

#chat {
    max-width: 850px;
    margin: auto;
    padding: 15px;
    height: calc(100vh - 160px);
    overflow-y: auto;
}

.message {
    padding: 13px;
    border-radius: 12px;
    margin: 12px 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    line-height: 1.6;
}

.user {
    background: #075985;
    margin-left: 12%;
}

.bot {
    background: #263449;
    margin-right: 8%;
}

#bottom {
    position: fixed;
    bottom: 0;
    width: 100%;
    background: #17243a;
    padding: 12px;
    border-top: 1px solid #334155;
}

#form {
    max-width: 850px;
    margin: auto;
    display: flex;
    gap: 8px;
}

input {
    flex: 1;
    min-width: 0;
    padding: 14px;
    border: 1px solid #475569;
    border-radius: 10px;
    background: #101827;
    color: white;
    font-size: 16px;
}

button {
    border: 0;
    padding: 12px 19px;
    border-radius: 10px;
    background: #0284c7;
    color: white;
    font-weight: bold;
}

button:disabled {
    opacity: .5;
}

</style>
</head>

<body>

<header>
    <h2>RIGAN AGI V15</h2>
    <p>Your Personal Artificial Intelligence</p>
</header>

<div id="chat">
    <div class="message bot">
        Habari! Mimi ni RIGAN AGI V15.
        Niulize swali lolote.
    </div>
</div>

<div id="bottom">
    <form id="form">
        <input id="message"
            placeholder="Andika swali lako hapa..."
            autocomplete="off" required>
        <button id="send" type="submit">Tuma</button>
    </form>
</div>

<script>
const form = document.getElementById("form");
const input = document.getElementById("message");
const chat = document.getElementById("chat");
const send = document.getElementById("send");

function addMessage(text, type) {
    const div = document.createElement("div");
    div.className = "message " + type;
    div.textContent = text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
}

form.addEventListener("submit", async function(e) {
    e.preventDefault();

    const message = input.value.trim();
    if (!message) return;

    addMessage(message, "user");
    input.value = "";
    send.disabled = true;
    send.textContent = "...";

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({message: message})
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Tatizo limetokea.");
        }

        addMessage(data.reply, "bot");

    } catch (error) {
        addMessage("RIGAN ERROR: " + error.message, "bot");
    } finally {
        send.disabled = false;
        send.textContent = "Tuma";
        input.focus();
    }
});
</script>

</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(HTML)


# ==================================
# CHAT ENGINE
# ==================================

@app.route("/chat", methods=["POST"])
def chat():

    if client is None:
        return jsonify({
            "error": "OPENROUTER_API_KEY haijawekwa kwenye Render."
        }), 500

    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify({"error": "Andika swali kwanza."}), 400

    if len(message) > 12000:
        return jsonify({"error": "Ujumbe ni mrefu sana."}), 400

    if "rigan_user_id" not in session:
        session["rigan_user_id"] = str(uuid.uuid4())

    user_id = session["rigan_user_id"]
    db = SessionLocal()

    try:
        # Save user message
        db.add(ChatMemory(
            id=str(uuid.uuid4()),
            user_id=user_id,
            role="user",
            content=message
        ))
        db.commit()

        # Load previous conversations
        memories = (
            db.query(ChatMemory)
            .filter(ChatMemory.user_id == user_id)
            .order_by(ChatMemory.created_at.desc())
            .limit(16)
            .all()
        )

        memories.reverse()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        for item in memories:
            messages.append({
                "role": item.role,
                "content": item.content
            })

        # Ask AI
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=1500
        )

        reply = response.choices[0].message.content

        if not reply:
            reply = "Samahani, jaribu kuuliza tena."

        # Save AI response
        db.add(ChatMemory(
            id=str(uuid.uuid4()),
            user_id=user_id,
            role="assistant",
            content=reply
        ))
        db.commit()

        return jsonify({
            "reply": reply,
            "ai": "RIGAN AGI V15"
        })

    except Exception as error:
        db.rollback()
        print("RIGAN CHAT ERROR:", repr(error))

        return jsonify({
            "error": "RIGAN imeshindwa kujibu. Angalia API na database settings."
        }), 500

    finally:
        db.close()


# ==================================
# HEALTH CHECK
# ==================================

@app.route("/health")
def health():
    return jsonify({
        "status": "running",
        "ai": "RIGAN AGI V15",
        "owner": OWNER_NAME,
        "api_configured": client is not None
    })


# ==================================
# START APPLICATION
# ==================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
)
