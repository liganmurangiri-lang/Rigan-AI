
import os
import sqlite3
import uuid
from datetime import datetime

from flask import Flask, request, jsonify, session, render_template_string
from openai import OpenAI

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "rigan-change-this-secret")

OWNER_NAME = os.environ.get("OWNER_NAME", "RIGAN Creator")
API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

DB_FILE = os.environ.get("DB_PATH", "rigan_memory.db")

def db():
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    return connection

def setup_database():
    with db() as con:
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

def save_memory(fact):
    fact = fact.strip()
    if not fact:
        return
    with db() as con:
        con.execute(
            "INSERT INTO memories (fact, created_at) VALUES (?, ?)",
            (fact, datetime.utcnow().isoformat())
        )

def get_memories():
    with db() as con:
        rows = con.execute(
            "SELECT fact FROM memories ORDER BY id DESC LIMIT 100"
        ).fetchall()
    return [row["fact"] for row in reversed(rows)]

def save_message(sid, role, content):
    with db() as con:
        con.execute("""
            INSERT INTO conversations
            (session_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
        """, (sid, role, content, datetime.utcnow().isoformat()))

def get_history(sid):
    with db() as con:
        rows = con.execute("""
            SELECT role, content FROM conversations
            WHERE session_id = ?
            ORDER BY id DESC LIMIT 16
        """, (sid,)).fetchall()
    return [
        {"role": row["role"], "content": row["content"]}
        for row in reversed(rows)
    ]

def ai_reply(message, sid):
    memories = get_memories()
    memory_text = "\n".join(
        "- " + fact for fact in memories
    ) or "Hakuna kumbukumbu zilizohifadhiwa bado."

    instructions = f"""
Wewe ni RIGAN AI, msaidizi mwenye akili na heshima.

Mtengenezaji wako ni {OWNER_NAME}.
Jibu kwa Kiswahili au Kiingereza kulingana na lugha ya mtumiaji.
Jibu maswali kuhusu sayansi, elimu, teknolojia na maarifa mbalimbali.
Toa majibu sahihi, ya kueleweka na yenye manufaa.
Usibuni ukweli unapokuwa huna uhakika.
Tumia kumbukumbu zifuatazo pale zinapohusika:

{memory_text}

Kumbuka: Kumbukumbu ni taarifa za kumsaidia mtumiaji,
si uthibitisho kwamba kila taarifa ni ya kweli.
"""

    if not API_KEY:
        return "Tatizo: OPENAI_API_KEY haijawekwa kwenye Render Environment."

    client = OpenAI(api_key=API_KEY)

    messages = [{"role": "system", "content": instructions}]
    messages.extend(get_history(sid))
    messages.append({"role": "user", "content": message})

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=1500
    )

    return response.choices[0].message.content

@app.route("/")
def home():
    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())

    return render_template_string(PAGE)

@app.route("/chat", methods=["POST"])
def chat():
    try:
        if "sid" not in session:
            session["sid"] = str(uuid.uuid4())

        data = request.get_json(silent=True) or {}
        message = str(data.get("message", "")).strip()

        if not message:
            return jsonify({"reply": "Tafadhali andika swali lako."}), 400

        if len(message) > 10000:
            return jsonify({"reply": "Ujumbe ni mrefu sana."}), 400

        sid = session["sid"]

        # Hifadhi taarifa anazoomba mtumiaji zikumbukwe.
        lower = message.lower()
        triggers = ("kumbuka kwamba", "kumbuka kuwa",
                    "remember that", "jifunze kwamba")

        for trigger in triggers:
            if lower.startswith(trigger):
                fact = message[len(trigger):].strip()
                if fact:
                    save_memory(fact)
                    save_message(sid, "user", message)
                    reply = "Nimehifadhi taarifa hii kwenye kumbukumbu yangu: " + fact
                    save_message(sid, "assistant", reply)
                    return jsonify({"reply": reply})

        save_message(sid, "user", message)
        answer = ai_reply(message, sid)
        save_message(sid, "assistant", answer)

        return jsonify({"reply": answer})

    except Exception as error:
        print("RIGAN ERROR:", repr(error))
        return jsonify({
            "reply": "Samahani, kuna tatizo la mfumo. Angalia Render Logs."
        }), 500

@app.route("/memory", methods=["GET"])
def memory():
    return jsonify({"memories": get_memories()})

@app.route("/health")
def health():
    return jsonify({"status": "online", "name": "RIGAN AI"})

PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RIGAN AI</title>
<style>
body {
    background:#101827;
    color:white;
    font-family:Arial;
    margin:0;
    padding:15px;
}
h2 {text-align:center;color:#36d6c5;}
#chat {
    max-width:700px;
    margin:20px auto;
    height:65vh;
    overflow-y:auto;
    background:#1b293c;
    padding:15px;
    border-radius:12px;
}
.msg {
    padding:12px;
    margin:10px 0;
    border-radius:10px;
    white-space:pre-wrap;
}
.user {background:#245b80;text-align:right;}
.ai {background:#334155;}
.controls {
    max-width:700px;
    margin:auto;
    display:flex;
    gap:8px;
}
input {
    flex:1;
    padding:14px;
    border-radius:8px;
    border:0;
    min-width:0;
}
button {
    background:#19b9a7;
    color:white;
    border:0;
    border-radius:8px;
    padding:12px;
}
</style>
</head>
<body>
<h2>RIGAN AI 🧠</h2>
<div id="chat">
<div class="msg ai">Karibu! Mimi ni RIGAN AI. Niulize swali lolote.</div>
</div>
<div class="controls">
<input id="message" placeholder="Andika ujumbe wako...">
<button onclick="send()">TUMA</button>
</div>
<script>
async function send() {
    const input = document.getElementById("message");
    const chat = document.getElementById("chat");
    const message = input.value.trim();
    if (!message) return;

    chat.innerHTML += '<div class="msg user"></div>';
    chat.lastElementChild.textContent = message;
    input.value = "";

    const waiting = document.createElement("div");
    waiting.className = "msg ai";
    waiting.textContent = "RIGAN AI inafikiria...";
    chat.appendChild(waiting);
    chat.scrollTop = chat.scrollHeight;

    try {
        const res = await fetch("/chat", {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({message})
        });
        const data = await res.json();
        waiting.textContent = data.reply || "Hakuna jibu.";
    } catch (e) {
        waiting.textContent = "Tatizo la kuunganisha na server.";
    }
    chat.scrollTop = chat.scrollHeight;
}

document.getElementById("message").addEventListener("keydown", e => {
    if (e.key === "Enter") send();
});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
                    
