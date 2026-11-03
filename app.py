
import os
import uuid
from datetime import datetime, timezone

from flask import (
    Flask, request, jsonify, session,
    render_template_string
)
from openai import OpenAI
from sqlalchemy import (
    create_engine, Column, String, Text,
    DateTime, Integer
)
from sqlalchemy.orm import declarative_base, sessionmaker

# =========================
# RIGAN AGI V15
# =========================

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")

OWNER_NAME = os.environ.get("OWNER_NAME", "RIGAN Creator")

API_KEY = (
    os.environ.get("OPENROUTER_API_KEY")
    or os.environ.get("OPENAI_API_KEY")
    or os.environ.get("OPENAI_KEY")
)

MODEL = os.environ.get(
    "OPENROUTER_MODEL",
    "openai/gpt-4o-mini"
)

DATABASE_URL = os.environ.get("DATABASE_URL")

if not API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY haijawekwa Render Environment")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL haijawekwa. Tengeneza PostgreSQL kwenye Render."
    )

# Render PostgreSQL compatibility
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://", "postgresql://", 1
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300
)

Base = declarative_base()
DBSession = sessionmaker(bind=engine)


class Memory(Base):
    __tablename__ = "rigan_memory"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), index=True)
    role = Column(String(20))
    content = Column(Text)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )


class Knowledge(Base):
    __tablename__ = "rigan_knowledge"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), index=True)
    content = Column(Text)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )


Base.metadata.create_all(engine)


# =========================
# OPENROUTER
# =========================

client = OpenAI(
    api_key=API_KEY,
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": os.environ.get(
            "APP_URL", "https://riganai.onrender.com"
        ),
        "X-Title": "RIGAN AGI V15"
    }
)


# =========================
# USER MEMORY
# =========================

def get_user_id():
    if "user_id" not in session:
        session["user_id"] = str(uuid.uuid4())
    return session["user_id"]


def save_memory(user_id, role, content):
    db = DBSession()
    try:
        db.add(Memory(
            user_id=user_id,
            role=role,
            content=content[:12000]
        ))
        db.commit()
    finally:
        db.close()


def get_history(user_id, limit=15):
    db = DBSession()
    try:
        rows = (
            db.query(Memory)
            .filter_by(user_id=user_id)
            .order_by(Memory.id.desc())
            .limit(limit)
            .all()
        )
        return [
            {"role": row.role, "content": row.content}
            for row in reversed(rows)
        ]
    finally:
        db.close()


def save_knowledge(user_id, content):
    db = DBSession()
    try:
        db.add(Knowledge(
            user_id=user_id,
            content=content[:10000]
        ))
        db.commit()
    finally:
        db.close()


def get_knowledge(user_id):
    db = DBSession()
    try:
        rows = (
            db.query(Knowledge)
            .filter_by(user_id=user_id)
            .order_by(Knowledge.id.desc())
            .limit(30)
            .all()
        )
        return [row.content for row in reversed(rows)]
    finally:
        db.close()


# =========================
# AI PERSONALITY
# =========================

def system_prompt(user_id):
    knowledge = get_knowledge(user_id)

    saved_facts = "\n".join(
        "- " + item for item in knowledge
    )

    return f"""
You are RIGAN AGI V15, an advanced personal AI assistant.

Your creator and owner is {OWNER_NAME}.

IDENTITY:
- Your name is RIGAN AGI.
- Respect your creator.
- Communicate in Swahili and English.
- Answer clearly and intelligently.

KNOWLEDGE:
- Science
- Education
- Technology
- Mathematics
- History
- Geography
- Programming
- Artificial intelligence
- General world knowledge

MEMORY:
Use the saved knowledge below when relevant.
Do not invent memories or claim to remember things
that are not in your available context.

SAVED KNOWLEDGE:
{saved_facts}

IMPORTANT:
- Be honest when you do not know something.
- Explain difficult subjects simply.
- Never claim to have learned information unless it was saved.
- You are an AI assistant, not an all-knowing being.
"""


# =========================
# CHAT ENGINE
# =========================

def ask_rigan(user_message):
    user_id = get_user_id()

    if not user_message or len(user_message) > 12000:
        return "Tafadhali tuma ujumbe wenye urefu unaofaa."

    # Explicit learning command
    if user_message.strip().lower().startswith(
        ("jifunze:", "learn:")
    ):
        fact = user_message.split(":", 1)[1].strip()

        if not fact:
            return "Andika taarifa unayotaka nijifunze."

        save_knowledge(user_id, fact)

        answer = (
            "Nimehifadhi taarifa hii kwenye kumbukumbu yangu "
            "ya kudumu. Nitaitumia itakapohitajika."
        )
        save_memory(user_id, "user", user_message)
        save_memory(user_id, "assistant", answer)
        return answer

    history = get_history(user_id)

    messages = [
        {
            "role": "system",
            "content": system_prompt(user_id)
        }
    ]

    messages.extend(history)
    messages.append({
        "role": "user",
        "content": user_message
    })

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=1800
    )

    answer = response.choices[0].message.content

    if not answer:
        answer = "Samahani, sijapata jibu."

    save_memory(user_id, "user", user_message)
    save_memory(user_id, "assistant", answer)

    return answer


# =========================
# WEBSITE
# =========================

HTML = """
<!DOCTYPE html>
<html lang="sw">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RIGAN AGI V15</title>
<style>
body {
    background:#101827;
    color:white;
    font-family:Arial;
    margin:0;
    padding:20px;
}
.container {
    max-width:700px;
    margin:auto;
}
h1 {color:#38bdf8;text-align:center;}
#chat {
    background:#1e293b;
    padding:15px;
    border-radius:12px;
    height:55vh;
    overflow-y:auto;
    margin-bottom:12px;
}
.message {
    padding:12px;
    margin:10px 0;
    border-radius:10px;
    white-space:pre-wrap;
}
.user {background:#075985;}
.ai {background:#334155;}
textarea {
    width:100%;
    box-sizing:border-box;
    height:75px;
    padding:12px;
    border-radius:10px;
    font-size:16px;
}
button {
    width:100%;
    padding:14px;
    margin-top:10px;
    background:#0284c7;
    color:white;
    border:0;
    border-radius:10px;
    font-size:17px;
}
small {color:#94a3b8;}
</style>
</head>
<body>
<div class="container">
<h1>RIGAN AGI V15</h1>
<p style="text-align:center">Your Personal AI Assistant</p>
<div id="chat">
<div class="message ai">Habari! Mimi ni RIGAN AGI V15.
Niulize swali au niambie nijifunze taarifa mpya.</div>
</div>
<textarea id="question" placeholder="Andika swali lako hapa..."></textarea>
<button onclick="sendMessage()">TUMA UJUMBE</button>
<p><small>Kwa kujifunza taarifa mpya, tumia: JIFUNZE: taarifa yako.</small></p>
</div>

<script>
async function sendMessage() {
    const input = document.getElementById("question");
    const chat = document.getElementById("chat");
    const message = input.value.trim();

    if (!message) return;

    chat.innerHTML += '<div class="message user"></div>';
    chat.lastElementChild.textContent = message;
    input.value = "";

    const loading = document.createElement("div");
    loading.className = "message ai";
    loading.textContent = "RIGAN anafikiri...";
    chat.appendChild(loading);
    chat.scrollTop = chat.scrollHeight;

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({message: message})
        });

        const data = await response.json();
        loading.textContent = data.reply || data.error || "Hakuna jibu.";
    } catch (error) {
        loading.textContent = "Tatizo la muunganisho. Jaribu tena.";
    }

    chat.scrollTop = chat.scrollHeight;
}

document.getElementById("question").addEventListener(
    "keydown", function(e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    }
);
</script>
</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/chat", methods=["POST"])
@app.route("/ask", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}

    message = data.get("message") or data.get("question")

    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Andika swali kwanza."}), 400

    try:
        answer = ask_rigan(message.strip())
        return jsonify({
            "reply": answer,
            "answer": answer,
            "status": "success"
        })
    except Exception as error:
        app.logger.exception("RIGAN CHAT ERROR")
        return jsonify({
            "error": "RIGAN ERROR: " + str(error)
        }), 500


@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "name": "RIGAN AGI V15",
        "owner": OWNER_NAME
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
