
import os
import uuid
import base64
from datetime import datetime, timezone

import requests
from flask import Flask, request, jsonify, session, render_template_string
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker


# ---------------- CONFIGURATION ----------------

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "rigan-stable-session-key-change-this"
)

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

VISION_MODEL = os.environ.get(
    "VISION_MODEL",
    MODEL
)

IMAGE_MODEL = os.environ.get(
    "IMAGE_MODEL",
    "openai/gpt-5-image"
)

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL haijawekwa kwenye Render.")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://", "postgresql://", 1
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

Base = declarative_base()
DBSession = sessionmaker(bind=engine)


# ---------------- DATABASE ----------------
# Majina na columns hizi zinahifadhi muundo wa V15.

class Memory(Base):
    __tablename__ = "rigan_memory"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), nullable=False, index=True)
    role = Column(String(30), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )


class Knowledge(Base):
    __tablename__ = "rigan_knowledge"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )


Base.metadata.create_all(engine)


def get_user_id():
    if "rigan_user_id" not in session:
        session["rigan_user_id"] = str(uuid.uuid4())
    return session["rigan_user_id"]


def save_memory(role, content):
    db = DBSession()
    try:
        item = Memory(
            user_id=get_user_id(),
            role=role,
            content=str(content)
        )
        db.add(item)
        db.commit()
    finally:
        db.close()


def get_history(limit=16):
    db = DBSession()
    try:
        rows = (
            db.query(Memory)
            .filter(Memory.user_id == get_user_id())
            .order_by(Memory.id.desc())
            .limit(limit)
            .all()
        )
        rows.reverse()

        return [
            {"role": row.role, "content": row.content}
            for row in rows
        ]
    finally:
        db.close()


def save_knowledge(content):
    db = DBSession()
    try:
        item = Knowledge(
            user_id=get_user_id(),
            content=content
        )
        db.add(item)
        db.commit()
    finally:
        db.close()


def get_knowledge(limit=20):
    db = DBSession()
    try:
        rows = (
            db.query(Knowledge)
            .filter(Knowledge.user_id == get_user_id())
            .order_by(Knowledge.id.desc())
            .limit(limit)
            .all()
        )
        return [row.content for row in rows]
    finally:
        db.close()


# ---------------- OPENROUTER ----------------

def api_headers():
    if not API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY haijawekwa kwenye Render."
        )

    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.environ.get(
            "APP_URL", "https://riganai.onrender.com"
        ),
        "X-Title": "RIGAN AGI"
    }


def system_prompt():
    knowledge = get_knowledge()

    knowledge_text = "\n".join(
        f"- {item}" for item in knowledge
    )

    return f"""
You are RIGAN AGI, an intelligent AI assistant.

Your creator and owner is {OWNER_NAME}.
When asked who created you, explain that {OWNER_NAME} is your creator.

You communicate fluently in Kiswahili and English.
Reply in the language used by the user.

Help with science, education, technology, mathematics,
history, programming, business and general knowledge.

Be honest. Never invent facts or claim you performed
an action that you did not perform.

Use saved knowledge when relevant, but do not treat
unverified user statements as guaranteed facts.

You can remember saved conversations and facts.
You do not retrain your underlying AI model by yourself.

SAVED KNOWLEDGE:
{knowledge_text}
"""


def ask_rigan(message):
    history = get_history()

    messages = [
        {"role": "system", "content": system_prompt()}
    ]

    messages.extend(history)
    messages.append({
        "role": "user",
        "content": message
    })

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=api_headers(),
        json={
            "model": MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1800
        },
        timeout=90
    )

    if not response.ok:
        raise RuntimeError(
            f"OpenRouter chat error {response.status_code}: "
            f"{response.text[:900]}"
        )

    data = response.json()
    answer = data["choices"][0]["message"]["content"]

    if isinstance(answer, list):
        answer = "\n".join(
            part.get("text", "")
            for part in answer
            if isinstance(part, dict)
        )

    if not answer:
        raise RuntimeError("AI haijarudisha jibu.")

    save_memory("user", message)
    save_memory("assistant", answer)

    return answer


# ---------------- IMAGE UNDERSTANDING ----------------

def understand_image(image_data, mime_type, question):
    if not API_KEY:
        raise RuntimeError("OpenRouter API key haijawekwa.")

    data_url = (
        f"data:{mime_type};base64,{image_data}"
    )

    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt()
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": question or
                        ""Eleza picha hii kwa Kiswahili.""
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_url
                        }
                    }
                ]
            }
        ],
        "max_tokens": 1500
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=api_headers(),
        json=payload,
        timeout=120
    )

    if not response.ok:
        raise RuntimeError(
            f"Vision error {response.status_code}: "
            f"{response.text[:900]}"
        )

    answer = response.json()["choices"][0]["message"]["content"]

    if isinstance(answer, list):
        answer = "\n".join(
            part.get("text", "")
            for part in answer
            if isinstance(part, dict)
        )

    save_memory("user", "[Picha] " + (question or "Eleza picha"))
    save_memory("assistant", answer)

    return answer


# ---------------- IMAGE GENERATION ----------------

def generate_image(prompt):
    response = requests.post(
        "https://openrouter.ai/api/v1/images",
        headers=api_headers(),
        json={
            "model": IMAGE_MODEL,
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024"
        },
        timeout=180
    )

    if not response.ok:
        raise RuntimeError(
            f"Image error {response.status_code}: "
            f"{response.text[:900]}"
        )

    data = response.json()
    images = data.get("data", [])

    if not images or not images[0].get("b64_json"):
        raise RuntimeError(
            "Hakuna picha iliyorejeshwa. "
            "Angalia kama IMAGE_MODEL inaunga mkono Images API."
        )

    mime = images[0].get("media_type", "image/png")
    encoded = images[0]["b64_json"]

    return f"data:{mime};base64,{encoded}"


# ---------------- WEB PAGE ----------------

PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RIGAN AGI V16</title>
<style>
body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #101827;
    color: white;
}
header {
    background: #17263c;
    padding: 17px;
    text-align: center;
    font-size: 22px;
    font-weight: bold;
}
main {
    max-width: 850px;
    margin: auto;
    padding: 15px;
}
#chat {
    min-height: 55vh;
    max-height: 65vh;
    overflow-y: auto;
    background: #172235;
    border-radius: 12px;
    padding: 12px;
}
.msg {
    padding: 12px;
    margin: 10px 0;
    border-radius: 10px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}
.user { background: #174c76; }
.bot { background: #26354a; }
img.result {
    width: 100%;
    max-width: 500px;
    display: block;
    margin-top: 10px;
    border-radius: 12px;
}
textarea {
    width: 100%;
    box-sizing: border-box;
    min-height: 75px;
    margin-top: 12px;
    padding: 12px;
    border-radius: 10px;
    font-size: 16px;
}
button, .upload {
    background: #1676c5;
    color: white;
    border: 0;
    padding: 12px;
    border-radius: 9px;
    margin: 5px 2px;
    font-size: 15px;
}
button:disabled { opacity: 0.5; }
.small { color: #bdc9d8; font-size: 13px; }
</style>
</head>
<body>
<header>RIGAN AGI V16</header>
<main>
<p class="small">AI yako • Kiswahili • English • Memory • Images • Voice</p>

<div id="chat">
<div class="msg bot">Karibu! Mimi ni RIGAN AGI. Niulize swali au nifundishe jambo jipya.</div>
</div>

<textarea id="message" placeholder="Andika ujumbe wako hapa..."></textarea>

<div>
<button onclick="sendMessage()">Tuma</button>
<button onclick="startVoice()">🎤 Sauti</button>
<button onclick="speakLast()">🔊 Soma jibu</button>
</div>

<hr>

<p><b>Jifunze:</b> Andika ujumbe unaoanza na JIFUNZE: ili RIGAN ihifadhi maarifa.</p>

<p><b>Tengeneza picha:</b></p>
<textarea id="imagePrompt" placeholder="Eleza picha unayotaka RIGAN itengeneze..."></textarea>
<button onclick="makeImage()">🎨 Tengeneza picha</button>

<hr>

<p><b>Chunguza picha:</b></p>
<input type="file" id="photo" accept="image/*">
<textarea id="photoQuestion" placeholder="Unataka RIGAN ichunguze nini kwenye picha?"></textarea>
<button onclick="analyzePhoto()">Chunguza picha</button>

<p class="small" id="status"></p>
</main>

<script>
const chat = document.getElementById("chat");
let lastAnswer = "";

function addMessage(text, who) {
    const div = document.createElement("div");
    div.className = "msg " + who;
    div.textContent = text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return div;
}

function addImage(src) {
    const img = document.createElement("img");
    img.className = "result";
    img.src = src;
    chat.appendChild(img);
    chat.scrollTop = chat.scrollHeight;
}

async function sendMessage() {
    const box = document.getElementById("message");
    const message = box.value.trim();
    if (!message) return;

    addMessage(message, "user");
    box.value = "";
    const waiting = addMessage("RIGAN inafikiri...", "bot");

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({message})
        });

        const data = await response.json();
        waiting.textContent = data.answer || data.error || "Hitilafu imetokea.";
        lastAnswer = data.answer || "";
    } catch (error) {
        waiting.textContent = "Tatizo la mtandao: " + error;
    }
}

async function makeImage() {
    const prompt = document.getElementById("imagePrompt").value.trim();
    if (!prompt) return;

    addMessage("Tengeneza picha: " + prompt, "user");
    const waiting = addMessage("RIGAN inatengeneza picha...", "bot");
    document.getElementById("status").textContent =
        "Kutengeneza picha kunaweza kuchukua muda na kutumia salio la API.";

    try {
        const response = await fetch("/image", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({prompt})
        });

        const data = await response.json();

        if (!response.ok) {
            waiting.textContent = data.error || "Picha haikutengenezwa.";
            return;
        }

        waiting.textContent = "Picha yako imetengenezwa:";
        addImage(data.image);
    } catch (error) {
        waiting.textContent = "Hitilafu: " + error;
    }
}

async function analyzePhoto() {
    const file = document.getElementById("photo").files[0];
    if (!file) {
        alert("Chagua picha kwanza.");
        return;
    }

    if (file.size > 5 * 1024 * 1024) {
        alert("Picha iwe chini ya 5 MB.");
        return;
    }

    const question = document.getElementById("photoQuestion").value;
    addMessage("Nimepakia picha. " + question, "user");
    const waiting = addMessage("RIGAN inachunguza picha...", "bot");

    try {
        const form = new FormData();
        form.append("photo", file);
        form.append("question", question);

        const response = await fetch("/vision", {
            method: "POST",
            body: form
        });

        const data = await response.json();
        waiting.textContent = data.answer || data.error || "Hitilafu imetokea.";
        lastAnswer = data.answer || "";
    } catch (error) {
        waiting.textContent = "Hitilafu: " + error;
    }
}

function speakLast() {
    if (!lastAnswer) {
        alert("Hakuna jibu la kusoma bado.");
        return;
    }

    if (!("speechSynthesis" in window)) {
        alert("Simu au browser hii haitumii kusoma kwa sauti.");
        return;
    }

    const speech = new SpeechSynthesisUtterance(lastAnswer);
    speech.lang = "sw-KE";
    speech.rate = 1;
    speechSynthesis.cancel();
    speechSynthesis.speak(speech);
}

function startVoice() {
    const Recognition =
        window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!Recognition) {
        alert("Voice input haipatikani kwenye browser hii.");
        return;
    }

    const recognition = new Recognition();
    recognition.lang = "sw-KE";
    recognition.interimResults = false;

    recognition.onresult = function(event) {
        document.getElementById("message").value =
            event.results[0][0].transcript;
    };

    recognition.onerror = function() {
        alert("Voice haikufanya kazi. Ruhusu microphone kwenye browser.");
    };

    recognition.start();
}
</script>
</body>
</html>
"""


# ---------------- ROUTES ----------------

@app.route("/")
def home():
    return render_template_string(PAGE)


@app.route("/chat", methods=["POST"])
def chat_route():
    try:
        data = request.get_json(silent=True) or {}
        message = str(data.get("message", "")).strip()

        if not message:
            return jsonify({"error": "Andika ujumbe kwanza."}), 400

        if message.upper().startswith("JIFUNZE:") or \
           message.upper().startswith("LEARN:"):

            fact = message.split(":", 1)[1].strip()

            if not fact:
                return jsonify({
                    "error": "Andika maarifa baada ya JIFUNZE:"
                }), 400

            save_knowledge(fact)
            save_memory("user", message)

            answer = (
                "Nimehifadhi maarifa haya kwenye kumbukumbu "
                "ya RIGAN. Unaweza kuniuliza baadaye."
            )

            save_memory("assistant", answer)

            return jsonify({"answer": answer})

        answer = ask_rigan(message)
        return jsonify({"answer": answer})

    except Exception as error:
        app.logger.exception("RIGAN CHAT ERROR")
        return jsonify({
            "error": "RIGAN CHAT ERROR: " + str(error)[:1200]
        }), 500


@app.route("/vision", methods=["POST"])
def vision_route():
    try:
        photo = request.files.get("photo")

        if not photo:
            return jsonify({"error": "Pakia picha kwanza."}), 400

        mime = photo.mimetype or ""

        if not mime.startswith("image/"):
            return jsonify({"error": "Faili lazima liwe picha."}), 400

        raw = photo.read()

        if len(raw) > 5 * 1024 * 1024:
            return jsonify({"error": "Picha iwe chini ya 5 MB."}), 400

        encoded = base64.b64encode(raw).decode("utf-8")
        question = request.form.get("question", "")

        answer = understand_image(encoded, mime, question)
        return jsonify({"answer": answer})

    except Exception as error:
        app.logger.exception("RIGAN VISION ERROR")
        return jsonify({
            "error": "RIGAN VISION ERROR: " + str(error)[:1200]
        }), 500


@app.route("/image", methods=["POST"])
def image_route():
    try:
        data = request.get_json(silent=True) or {}
        prompt = str(data.get("prompt", "")).strip()

        if not prompt:
            return jsonify({"error": "Eleza picha unayotaka."}), 400

        image = generate_image(prompt)
        return jsonify({"image": image})

    except Exception as error:
        app.logger.exception("RIGAN IMAGE ERROR")
        return jsonify({
            "error": "RIGAN IMAGE ERROR: " + str(error)[:1200]
        }), 500


@app.route("/health")
def health():
    return jsonify({
        "status": "RIGAN AGI is running",
        "owner": OWNER_NAME,
        "model": MODEL,
        "database": "configured",
        "version": "V16"
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
)
