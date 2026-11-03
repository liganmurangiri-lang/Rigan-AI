
import os
import uuid
import base64
from datetime import datetime, timezone

import requests
from flask import (
    Flask, request, jsonify, session,
    render_template_string
)
from sqlalchemy import (
    create_engine, Column, String, Text,
    DateTime, Integer
)
from sqlalchemy.orm import declarative_base, sessionmaker
from openai import OpenAI

# ==========================================
# RIGAN AGI V16 ULTIMATE
# ==========================================

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("SECRET_KEY haijawekwa Render.")

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
    "openai/gpt-4o-mini"
)

IMAGE_MODEL = os.environ.get(
    "IMAGE_MODEL",
    "google/gemini-2.5-flash-image"
)

DATABASE_URL = os.environ.get("DATABASE_URL")

if not API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY haijawekwa.")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL haijawekwa.")

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


# ==========================================
# DATABASE - PRESERVE V15 MEMORY
# ==========================================

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


# ==========================================
# OPENROUTER CONNECTION
# ==========================================

client = OpenAI(
    api_key=API_KEY,
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": os.environ.get(
            "APP_URL", "https://riganai.onrender.com"
        ),
        "X-Title": "RIGAN AGI V16 ULTIMATE"
    }
)

API_URL = "https://openrouter.ai/api/v1"


def api_headers():
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }


# ==========================================
# USER ID AND MEMORY
# ==========================================

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
            content=str(content)[:12000]
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
            .limit(40)
            .all()
        )
        return [r.content for r in reversed(rows)]
    finally:
        db.close()


# ==========================================
# INTELLIGENCE AND PERSONALITY
# ==========================================

def system_prompt(user_id):
    facts = get_knowledge(user_id)

    saved_facts = "\n".join(
        "- " + item for item in facts
    ) or "Hakuna maarifa mapya yaliyohifadhiwa."

    return f"""
You are RIGAN AGI V16 ULTIMATE.

CREATOR:
Your creator and owner is {OWNER_NAME}.

IDENTITY:
- Your name is RIGAN AGI V16.
- You are a helpful personal AI assistant.
- Respect your creator.
- Communicate in Swahili, English and other languages.
- Understand the user's language and reply in that language.

INTELLIGENCE:
You help with:
Science, education, technology, mathematics,
history, geography, programming, AI and world knowledge.

INTERNET:
When web search is available, use current sources
for questions about recent events and changing facts.
Clearly distinguish sourced information from your own explanation.
Never invent sources or links.

LEARNING:
- Use saved knowledge when relevant.
- Do not claim to remember facts that are not saved.
- You may learn new facts when the user explicitly requests it.
- Never claim to modify your own program or weights.
- Do not invent information.

VISION:
When an image is provided, examine it carefully.
Describe visible details and answer questions about it.
Do not pretend to see an image if none was provided.

CREATOR RECOGNITION:
The configured owner is {OWNER_NAME}.
Do not reveal private information or passwords.

SAVED KNOWLEDGE:
{saved_facts}

BEHAVIOUR:
- Be intelligent, clear and helpful.
- Explain difficult subjects simply.
- Admit uncertainty.
- Never fabricate facts.
"""


# ==========================================
# CHAT ENGINE
# ==========================================

def ask_rigan(user_message, use_web=False):
    user_id = get_user_id()
    message = user_message.strip()

    if not message or len(message) > 12000:
        return "Tafadhali tuma ujumbe wenye urefu unaofaa."

    # Explicit learning
    lower = message.lower()

    if lower.startswith(("jifunze:", "learn:")):
        fact = message.split(":", 1)[1].strip()

        if not fact:
            return "Andika taarifa unayotaka nijifunze."

        save_knowledge(user_id, fact)

        answer = (
            "Nimehifadhi taarifa hii kwenye PostgreSQL. "
            "Nitaiweza kuitumia katika mazungumzo yajayo."
        )

        save_memory(user_id, "user", message)
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
        "content": message
    })

    extra = {}

    # Web search is optional and user-controlled.
    if use_web:
        extra["plugins"] = [
            {"id": "web", "max_results": 5}
        ]

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=2000,
        extra_body=extra if extra else None
    )

    answer = response.choices[0].message.content

    if not answer:
        answer = "Samahani, sijapata jibu."

    save_memory(user_id, "user", message)
    save_memory(user_id, "assistant", answer)

    return answer


# ==========================================
# IMAGE UNDERSTANDING
# ==========================================

def understand_image(user_message, image_data):
    user_id = get_user_id()

    if not image_data.startswith("data:image/"):
        raise ValueError("Picha haijatambuliwa.")

    if len(image_data) > 5 * 1024 * 1024:
        raise ValueError("Picha ni kubwa sana. Tumia picha ndogo.")

    content = [
        {
            "type": "text",
            "text": user_message or "Eleza picha hii kwa undani."
        },
        {
            "type": "image_url",
            "image_url": {
                "url": image_data
            }
        }
    ]

    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt(user_id)
            },
            {
                "role": "user",
                "content": content
            }
        ],
        max_tokens=1800
    )

    answer = response.choices[0].message.content

    if not answer:
        answer = "Sijaweza kuchambua picha."

    save_memory(
        user_id,
        "user",
        "[Picha] " + (user_message or "Chambua picha")
    )

    save_memory(user_id, "assistant", answer)

    return answer


# ==========================================
# IMAGE GENERATION
# ==========================================

def generate_image(prompt):
    if not prompt or len(prompt) > 3000:
        raise ValueError("Maelekezo ya picha si sahihi.")

    response = requests.post(
        API_URL + "/images",
        headers=api_headers(),
        json={
            "model": IMAGE_MODEL,
            "prompt": prompt
        },
        timeout=180
    )

    if not response.ok:
        raise RuntimeError(
            f"Image API error {response.status_code}: "
            + response.text[:1200]
        )

    result = response.json()
    images = result.get("data") or []

    if not images or not images[0].get("b64_json"):
        raise RuntimeError("API haikurudisha picha.")

    image = images[0]

    media_type = image.get("media_type", "image/png")
    if media_type not in ("image/png", "image/jpeg", "image/webp"):
        media_type = "image/png"

    return "data:" + media_type + ";base64," + image["b64_json"]


# ==========================================
# WEBSITE INTERFACE
# ==========================================

HTML = r"""
<!DOCTYPE html>
<html lang="sw">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<title>RIGAN AGI V16 ULTIMATE</title>

<style>
* {box-sizing:border-box}

body {
    background:#0b1120;
    color:white;
    font-family:Arial,sans-serif;
    margin:0;
    padding:12px;
}

.container {
    max-width:850px;
    margin:auto;
}

h1 {
    text-align:center;
    color:#38bdf8;
    margin-bottom:5px;
}

.subtitle {
    text-align:center;
    color:#94a3b8;
}

#chat {
    background:#172033;
    border:1px solid #334155;
    border-radius:14px;
    height:53vh;
    min-height:300px;
    overflow-y:auto;
    padding:12px;
    margin-top:15px;
}

.message {
    padding:12px;
    margin:10px 0;
    border-radius:12px;
    white-space:pre-wrap;
    overflow-wrap:anywhere;
    line-height:1.5;
}

.user {background:#075985}
.ai {background:#334155}

.message img {
    max-width:100%;
    border-radius:10px;
    margin-top:10px;
}

textarea {
    width:100%;
    height:75px;
    border:0;
    border-radius:10px;
    padding:13px;
    font-size:16px;
    margin-top:12px;
    background:#e2e8f0;
    color:#111827;
}

button {
    border:0;
    border-radius:9px;
    padding:12px;
    margin:4px 2px;
    background:#0284c7;
    color:white;
    font-size:14px;
    cursor:pointer;
}

button:disabled {opacity:.5}

.tools {
    display:flex;
    flex-wrap:wrap;
    gap:5px;
    margin-top:8px;
}

.tools button {flex:1}

.options {
    display:flex;
    gap:12px;
    flex-wrap:wrap;
    margin-top:10px;
    color:#cbd5e1;
    font-size:13px;
}

input[type=file] {
    display:none;
}

.status {
    color:#94a3b8;
    font-size:12px;
    text-align:center;
    margin-top:10px;
}
</style>
</head>

<body>
<div class="container">

<h1>RIGAN AGI V16</h1>
<p class="subtitle">ULTIMATE SELF-LEARNING INTELLIGENCE</p>

<div id="chat">
<div class="message ai">
Habari! Mimi ni RIGAN AGI V16.

Naweza kujibu maswali, kuchambua picha,
kutafuta taarifa mtandaoni na kutengeneza picha.

Niulize chochote!
</div>
</div>

<textarea id="question"
placeholder="Andika swali au maelekezo hapa..."></textarea>

<div class="options">
<label>
<input type="checkbox" id="web">
Tafuta mtandaoni
</label>

<label>
<input type="checkbox" id="speak">
Jibu kwa sauti
</label>
</div>

<div class="tools">
<button id="sendBtn" onclick="sendMessage()">TUMA</button>

<button onclick="generateImage()">CHORA PICHA</button>

<button onclick="startVoice()">ONGEA</button>

<button onclick="stopVoice()">SIMAMISHA SAUTI</button>
</div>

<div class="tools">
<button onclick="document.getElementById('imageFile').click()">
PAKIA PICHA
</button>
<button onclick="learnHelp()">JIFUNZE
</button>
</div>

<input type="file" id="imageFile" accept="image/*">

<p class="status" id="status">
RIGAN V16 ONLINE
</p>

</div>

<script>
const chat = document.getElementById("chat");
const question = document.getElementById("question");
const statusText = document.getElementById("status");

function addMessage(text, type) {
    const div = document.createElement("div");
    div.className = "message " + type;
    div.textContent = text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return div;
}

function addImage(src, type) {
    const div = document.createElement("div");
    div.className = "message " + type;

    const img = document.createElement("img");
    img.src = src;
    img.alt = "RIGAN AI image";

    div.appendChild(img);
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
}

function speakText(text) {
    if (!document.getElementById("speak").checked) return;

    if (!("speechSynthesis" in window)) {
        statusText.textContent = "Sauti haiungwi mkono kwenye browser hii.";
        return;
    }

    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "sw-KE";
    utterance.rate = 1;

    window.speechSynthesis.speak(utterance);
}

async function sendMessage() {
    const message = question.value.trim();
    if (!message) return;

    addMessage(message, "user");
    question.value = "";

    const loading = addMessage("RIGAN anafikiri...", "ai");

    statusText.textContent = "Inachakata...";

    try {
        const response = await fetch("/chat", {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({
                message:message,
                use_web:document.getElementById("web").checked
            })
        });

        const data = await response.json();

        if (!response.ok) throw new Error(data.error || "Tatizo.");

        loading.textContent = data.reply;
        speakText(data.reply);
        statusText.textContent = "RIGAN ONLINE";

    } catch(error) {
        loading.textContent = "RIGAN ERROR: " + error.message;
        statusText.textContent = "Kuna tatizo.";
    }

    chat.scrollTop = chat.scrollHeight;
}

async function generateImage() {
    const prompt = question.value.trim();

    if (!prompt) {
        alert("Andika maelekezo ya picha kwanza.");
        return;
    }

    addMessage("Chora picha: " + prompt, "user");
    question.value = "";

    const loading = addMessage(
        "RIGAN anatengeneza picha... Tafadhali subiri.",
        "ai"
    );

    statusText.textContent = "Image generation...";

    try {
        const response = await fetch("/image", {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({prompt:prompt})
        });

        const data = await response.json();

        if (!response.ok) throw new Error(data.error || "Picha imeshindikana.");

        loading.remove();
        addImage(data.image, "ai");

        statusText.textContent = "Picha imeundwa.";

    } catch(error) {
        loading.textContent = "IMAGE ERROR: " + error.message;
        statusText.textContent = "Image error.";
    }
}

document.getElementById("imageFile").addEventListener(
    "change", async function() {

    const file = this.files[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
        alert("Chagua picha.");
        return;
    }

    if (file.size > 3 * 1024 * 1024) {
        alert("Picha iwe chini ya 3 MB.");
        this.value = "";
        return;
    }

    const reader = new FileReader();

    reader.onload = async function() {
        const imageData = reader.result;

        addImage(imageData, "user");

        const prompt = question.value.trim() ||
            "Chambua picha hii na nieleze unaona nini.";

        question.value = "";

        const loading = addMessage(
            "RIGAN anachunguza picha...",
            "ai"
        );

        try {
            const response = await fetch("/vision", {
                method:"POST",
                headers:{"Content-Type":"application/json"},
                body:JSON.stringify({
                    message:prompt,
                    image:imageData
                })
            });

            const data = await response.json();

            if (!response.ok) throw new Error(data.error || "Vision error.");

            loading.textContent = data.reply;
            speakText(data.reply);

        } catch(error) {
            loading.textContent = "VISION ERROR: " + error.message;
        }
    };

    reader.readAsDataURL(file);
    this.value = "";
});

function startVoice() {
    const SpeechRecognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        alert("Browser hii haiungi mkono speech recognition. Jaribu Chrome.");
        return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "sw-KE";
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = function() {
        statusText.textContent = "RIGAN anasikiliza...";
    };

    recognition.onresult = function(event) {
        question.value = event.results[0][0].transcript;
        statusText.textContent = "Sauti imepokelewa.";
    };

    recognition.onerror = function(event) {
        statusText.textContent = "Voice error: " + event.error;
    };

    recognition.onend = function() {
        if (statusText.textContent === "RIGAN anasikiliza...") {
            statusText.textContent = "Usikilizaji umemalizika.";
        }
    };

    recognition.start();
    window.riganRecognition = recognition;
}

function stopVoice() {
    if (window.riganRecognition) {
        window.riganRecognition.stop();
    }

    if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
    }

    statusText.textContent = "Sauti imesimamishwa.";
}

function learnHelp() {
    question.value = "JIFUNZE: ";
    question.focus();
}

question.addEventListener("keydown", function(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});
</script>
</body>
</html>
"""


# ==========================================
# FLASK ROUTES
# ==========================================

@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/chat", methods=["POST"])
@app.route("/ask", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}

    message = data.get("message") or data.get("question")
    use_web = data.get("use_web") is True

    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Andika swali kwanza."}), 400

    try:
        answer = ask_rigan(message.strip(), use_web)

        return jsonify({
            "reply": answer,
            "answer": answer,
            "status": "success"
        })

    except Exception as error:
        app.logger.exception("RIGAN CHAT ERROR")
        return jsonify({
            "error": "RIGAN CHAT ERROR: " + str(error)[:
