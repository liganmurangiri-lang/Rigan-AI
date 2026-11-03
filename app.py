
import os
import sqlite3
import uuid
from datetime import datetime, timezone

from flask import Flask, request, jsonify, session, render_template_string
from openai import OpenAI

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY", "change-this-rigan-secret"
)

OWNER_NAME = os.environ.get("OWNER_NAME", "RIGAN Creator")

# OpenRouter key: sk-or-v1-...
API_KEY = (
    os.environ.get("OPENROUTER_API_KEY")
    or os.environ.get("OPENAI_API_KEY")
)

MODEL = os.environ.get("OPENROUTER_MODEL", "openrouter/free")

DB_FILE = os.environ.get("DB_PATH", "rigan_memory.db")


# ---------------- DATABASE ----------------

def get_db():
    con = sqlite3.connect(DB_FILE, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def setup_database():
    with get_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


setup_database()


# ---------------- MEMORY SYSTEM ----------------

def save_memory(fact):
    fact = fact.strip()

    if not fact:
        return

    with get_db() as con:
        con.execute(
            "INSERT INTO memories (fact, created_at) VALUES (?, ?)",
            (fact, datetime.now(timezone.utc).isoformat())
        )


def get_memories():
    with get_db() as con:
        rows = con.execute("""
            SELECT fact FROM memories
            ORDER BY id DESC LIMIT 100
        """).fetchall()

    return [row["fact"] for row in reversed(rows)]


def save_message(sid, role, content):
    with get_db() as con:
        con.execute("""
            INSERT INTO conversations
            (session_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            sid,
            role,
            content,
            datetime.now(timezone.utc).isoformat()
        ))


def get_history(sid):
    with get_db() as con:
        rows = con.execute("""
            SELECT role, content FROM conversations
            WHERE session_id = ?
            ORDER BY id DESC LIMIT 16
        """, (sid,)).fetchall()

    return [
        {"role": row["role"], "content": row["content"]}
        for row in reversed(rows)
    ]


# ---------------- OPENROUTER AI ----------------

def get_client():
    if not API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY haijawekwa kwenye Render."
        )

    return OpenAI(
        api_key=API_KEY,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "X-OpenRouter-Title": "RIGAN AI"
        }
    )


def ai_reply(message, sid):

    memories = get_memories()

    memory_text = "\n".join(
        "- " + item for item in memories
    )

    if not memory_text:
        memory_text = "Hakuna kumbukumbu bado."

    system_prompt = f"""
Wewe ni RIGAN AI.

Jina la mtengenezaji wako ni {OWNER_NAME}.

MAJUKUMU:
1. Jibu maswali kwa Kiswahili na Kiingereza.
2. Saidia kwenye sayansi, elimu na teknolojia.
3. Eleza mambo kwa lugha rahisi na sahihi.
4. Jibu kwa heshima na kwa undani unaohitajika.
5. Usibuni taarifa usizozijua.
6. Tumia kumbukumbu zinazohusika kujibu maswali.
7. Usidai kuwa umejifunza jambo ambalo hujahifadhi.

KUMBUKUMBU ZA RIGAN:
{memory_text}
"""

    client = get_client()

    messages = [
        {"role": "system", "content": system_prompt}
    ]

    messages.extend(get_history(sid))

    messages.append({
        "role": "user",
        "content": message
    })

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=1500
    )

    answer = response.choices[0].message.content

    if not answer:
        return "Samahani, sijapata jibu. Jaribu tena."

    return answer


# ---------------- WEBSITE ----------------

PAGE = """
<!DOCTYPE html>
<html lang="sw">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RIGAN AI</title>

<style>
body {
    background: #101827;
    color: white;
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 15px;
}

h2 {
    color: #35d6c5;
    text-align: center;
}

.subtitle {
    text-align: center;
    color: #aab7c5;
}

#chat {
    max-width: 750px;
    height: 65vh;
    overflow-y: auto;
    margin: 20px auto;
    padding: 15px;
    background: #1b293c;
    border-radius: 12px;
}

.msg {
    padding: 12px;
    margin: 12px 0;
    border-radius: 10px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    line-height: 1.5;
}

.user {
    background: #245b80;
    text-align: right;
}

.ai {
    background: #334155;
}

.controls {
    display: flex;
    max-width: 750px;
    margin: auto;
    gap: 8px;
}

input {
    flex: 1;
    min-width: 0;
    padding: 14px;
    border-radius: 8px;
    border: none;
    font-size: 16px;
}

button {
    background: #19b9a7;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 12px 18px;
    cursor: pointer;
}

button:disabled {
    opacity: 0.5;
}

.footer {
    text-align: center;
    color: #8795a6;
    margin-top: 20px;
    font-size: 12px;
}
</style>
</head>

<body>

<h2>RIGAN AI 🧠</h2>

<div class="subtitle">
LONG-TERM MEMORY | INTELLIGENT ASSISTANT
</div>

<div id="chat">
    <div class="msg ai">
        Karibu kwenye RIGAN AI!
        Niulize swali lolote.
    </div>
</div>

<div class="controls">
    <input id="message"
           placeholder="Andika swali lako...">
    <button id="send" onclick="sendMessage()">
        TUMA
    </button>
</div>

<div class="footer">
    RIGAN AI - Created by RIGAN Creator
</div>

<script>
async function sendMessage() {

    const input = document.getElementById("message");
    const chat = document.getElementById("chat");
    const button = document.getElementById("send");

    const message = input.value.trim();

    if (!message || button.disabled) return;

    const user = document.createElement("div");
    user.className = "msg user";
    user.textContent = message;
    chat.appendChild(user);

    input.value = "";
    button.disabled = true;

    const answer = document.createElement("div");
    answer.className = "msg ai";
    answer.textContent = "RIGAN AI inafikiria...";
    chat.appendChild(answer);

    chat.scrollTop = chat.scrollHeight;

    try {

        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message
            })
        });

        const data = await response.json();

        if (!response.ok) {
            answer.textContent =
                data.reply || "Tatizo limetokea.";
        } else {
            answer.textContent = data.reply;
        }

    } catch (error) {

        answer.textContent =
            "Imeshindikana kuunganisha na RIGAN AI.";

    } finally {

        button.disabled = false;
        chat.scrollTop = chat.scrollHeight;
        input.focus();

    }
}

document.getElementById("message")
.addEventListener("keydown", function(event) {
    if (event.key === "Enter") {
        sendMessage();
    }
});
</script>

</body>
</html>
"""


@app.route("/")
def home():

    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())

    return render_template_string(PAGE)


# ---------------- CHAT API ----------------

@app.route("/chat", methods=["POST"])
def chat():

    try:

        if "sid" not in session:
            session["sid"] = str(uuid.uuid4())

        data = request.get_json(silent=True) or {}

        message = str(data.get("message", "")).strip()

        if not message:
            return jsonify({
                "reply": "Tafadhali andika swali lako."
            }), 400

        if len(message) > 10000:
            return jsonify({
                "reply": "Ujumbe ni mrefu sana."
            }), 400

        sid = session["sid"]

        # Mfumo wa kufundisha na kuhifadhi kumbukumbu
        lower = message.lower()

        triggers = [
            "kumbuka kwamba",
            "kumbuka kuwa",
            "remember that",
            "jifunze kwamba"
        ]

        for trigger in triggers:

            if lower.startswith(trigger):

                fact = message[len(trigger):].strip()

                if not fact:
                    return jsonify({
                        "reply": "Andika taarifa unayotaka nikumbuke."
                    })

                save_memory(fact)

                reply = (
                    "Nimehifadhi taarifa hii kwenye kumbukumbu yangu: "
                    + fact
                )

                save_message(sid, "user", message)
                save_message(sid, "assistant", reply)

                return jsonify({"reply": reply})

        # Pata jibu la AI
        answer = ai_reply(message, sid)

        save_message(sid, "user", message)
        save_message(sid, "assistant", answer)

        return jsonify({"reply": answer})

    except Exception as error:

        print("RIGAN ERROR:", repr(error))

        return jsonify({
            "reply": "Samahani, kuna tatizo. Angalia Render Logs."
        }), 500


# ---------------- MEMORY VIEW ----------------

@app.route("/memory", methods=["GET"])
def memory():

    return jsonify({
        "owner": OWNER_NAME,
        "memories": get_memories()
    })


# ---------------- HEALTH CHECK ----------------

@app.route("/health")
def health():

    return jsonify({
        "status": "online",
        "name": "RIGAN AI",
        "provider": "OpenRouter"
    })


# ---------------- START SERVER ----------------

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
    
