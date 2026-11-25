import os
import uuid
import base64
import sqlite3
import secrets
import hmac
import time
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from functools import wraps
from threading import Lock
from urllib.parse import urlparse

import requests
from flask import (
    Flask, request, jsonify, render_template_string, session
)

try:
    import psycopg2
except Exception:
    psycopg2 = None


# =========================================================
# RIGAN AI - SECURITY HARDENED EDITION
# Keeps: Chat, Vision, Image Generation, browser voice,
# PostgreSQL/Neon, SQLite fallback, and conversation history.
# =========================================================

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

APP_NAME = "RIGAN AI"
OWNER_NAME = (
    os.getenv("OWNER_NAME", "Ligan Murangiri").strip()
    or "Ligan Murangiri"
)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SQLITE_FILE = os.getenv("SQLITE_FILE", "rigan_v16.db")

OPENROUTER_API_KEY = (
    os.getenv("OPENROUTER_API_KEY")
    or os.getenv("OPENAI_API_KEY")
    or os.getenv("OPENAI_KEY")
    or ""
).strip()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
CHAT_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
VISION_MODEL = os.getenv("VISION_MODEL", "google/gemini-2.5-flash")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "google/gemini-2.5-flash-image")
APP_URL = os.getenv("APP_URL", "https://riganai.onrender.com").strip()

MAX_IMAGE_SIZE = 6 * 1024 * 1024
MAX_MESSAGE_LENGTH = 12000
MAX_IMAGE_PROMPT = 1500
CHAT_TIMEOUT = (15, 120)
IMAGE_TIMEOUT = (15, 180)

# Set FLASK_SECRET_KEY in Render Environment.
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "").strip()
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(48)
    app.logger.warning(
        "FLASK_SECRET_KEY is missing. Sessions may reset after restart."
    )

app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    SESSION_REFRESH_EACH_REQUEST=True,
)

logging.basicConfig(level=logging.INFO)

if DATABASE_URL and not psycopg2:
    raise RuntimeError(
        "DATABASE_URL is set but psycopg2-binary is unavailable."
    )

if urlparse(OPENROUTER_BASE_URL).hostname != "openrouter.ai":
    raise RuntimeError("Invalid OpenRouter API host.")


SYSTEM_PROMPT = f"""
You are {APP_NAME}, an AI assistant created by {OWNER_NAME}.
You are helpful, truthful, respectful, and clear.
You can answer questions, explain ideas, help with learning and writing,
analyze images supplied by the user, and help generate images when the
image-generation service is available.
Do not claim abilities or access that you do not have.
If image generation fails, explain that the image service or selected
model may not be available; do not pretend an image was created.
Reply in the language used by the user. You can communicate in Swahili
and English. Be concise unless the user asks for detail.
Only mention the creator when the user asks who created or owns you.
"""


# ------------------------- DATABASE -------------------------

def utc_now():
    return datetime.now(timezone.utc).isoformat()


def db_connect():
    if DATABASE_URL and psycopg2:
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        return psycopg2.connect(
            url,
            connect_timeout=15,
            sslmode="require"
        )

    conn = sqlite3.connect(SQLITE_FILE, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db_connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation
            ON chat_messages (conversation_id, created_at)
        """)
        conn.commit()
    finally:
        conn.close()


def save_message(conversation_id, role, content):
    conn = db_connect()
    try:
        cur = conn.cursor()
        sql = """
            INSERT INTO chat_messages
            (id, conversation_id, role, content, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """ if DATABASE_URL and psycopg2 else """
            INSERT INTO chat_messages
            (id, conversation_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
        """
        cur.execute(sql, (
            str(uuid.uuid4()),
            conversation_id,
            role,
            str(content),
            utc_now()
        ))
        conn.commit()
    finally:
        conn.close()


def get_history(conversation_id, limit=20):
    conn = db_connect()
    try:
        cur = conn.cursor()
        sql = """
            SELECT role, content FROM chat_messages
            WHERE conversation_id = %s
            ORDER BY created_at DESC LIMIT %s
        """ if DATABASE_URL and psycopg2 else """
            SELECT role, content FROM chat_messages
            WHERE conversation_id = ?
            ORDER BY created_at DESC LIMIT ?
        """
        cur.execute(sql, (conversation_id, limit))
        rows = list(reversed(cur.fetchall()))
        return [
            {"role": row[0], "content": row[1]}
            for row in rows
        ]
    finally:
        conn.close()


# ------------------------- RATE LIMITING -------------------------
# In-process limiter. For multiple Render instances, use a shared
# Redis/database-backed limiter in a later deployment.

_RATE_LOCK = Lock()
_RATE_BUCKETS = defaultdict(deque)
_RATE_RULES = {
    "chat": (20, 60),
    "image": (5, 60),
    "session": (30, 60),
}
_RATE_MAX_KEYS = 10000


def rate_limit(kind):
    limit, window = _RATE_RULES[kind]

    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            now = time.monotonic()
            identity = session.get("conversation_id")
            if not identity:
                identity = request.remote_addr or "unknown"
            key = (kind, str(identity))

            with _RATE_LOCK:
                bucket = _RATE_BUCKETS[key]
                while bucket and now - bucket[0] > window:
                    bucket.popleft()

                if len(bucket) >= limit:
                    return jsonify(
                        error="Maombi ni mengi sana. Tafadhali subiri kidogo."
                    ), 429

                bucket.append(now)

                if len(_RATE_BUCKETS) > _RATE_MAX_KEYS:
                    _RATE_BUCKETS.clear()

            return func(*args, **kwargs)
        return wrapped
    return decorator


# ------------------------- SESSION / CSRF -------------------------

def ensure_session():
    if not session.get("conversation_id"):
        session["conversation_id"] = str(uuid.uuid4())
        session["csrf_token"] = secrets.token_urlsafe(32)
        session.permanent = True

    if not session.get("csrf_token"):
        session["csrf_token"] = secrets.token_urlsafe(32)

    return session["conversation_id"], session["csrf_token"]


def require_csrf(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        expected = session.get("csrf_token", "")
        supplied = request.headers.get("X-CSRF-Token", "")

        if (
            not expected
            or not supplied
            or not hmac.compare_digest(expected, supplied)
        ):
            return jsonify(
                error="Session security check failed. Refresh the page."
            ), 403

        return func(*args, **kwargs)
    return wrapped


# ------------------------- CREATOR IDENTITY -------------------------

def creator_identity_answer(message):
    text = (message or "").lower()
    patterns = (
        "who created you", "who made you", "who is your creator",
        "who owns you", "who developed you", "who built you",
        "nani amekutengeneza", "nani alikutengeneza",
        "nani alikuumba", "nani mmiliki wako",
        "nani amekuunda", "umetengenezwa na nani",
        "uliundwa na nani", "mtengenezaji wako ni nani",
    )
    if any(pattern in text for pattern in patterns):
        return (
            f"Mimi ni {APP_NAME}. Nimetengenezwa na kumilikiwa na "
            f"{OWNER_NAME}."
        )
    return None


# ------------------------- OPENROUTER -------------------------

def api_headers():
    if not OPENROUTER_API_KEY:
        raise RuntimeError("API_KEY_MISSING")

    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": APP_URL,
        "X-Title": APP_NAME,
    }


def safe_api_error(response, service):
    # Do not send provider response bodies or internal details to visitors.
    app.logger.warning(
        "%s returned HTTP %s", service, response.status_code
    )
    return f"{service} service error ({response.status_code})."


def openrouter_chat(messages, model):
    response = requests.post(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        headers=api_headers(),
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1800,
        },
        timeout=CHAT_TIMEOUT,
    )

    if not response.ok:
        raise RuntimeError(safe_api_error(response, "OpenRouter chat"))

    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("AI haikurudisha jibu.")

    message = choices[0].get("message") or {}
    content = message.get("content", "")

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        content = "\n".join(parts)

    content = str(content).strip()
    if not content:
        raise RuntimeError("AI haikurudisha jibu.")
    return content


# ------------------------- IMAGE VALIDATION -------------------------

def validate_image(raw, mimetype):
    if not raw:
        raise ValueError("Picha haina data.")

    if len(raw) > MAX_IMAGE_SIZE:
        raise ValueError("Picha iwe chini ya 6 MB.")

    signatures = {
        "image/jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
        "image/png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": lambda b: (
            len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP"
        ),
    }

    checker = signatures.get(mimetype)
    if not checker or not checker(raw):
        raise ValueError(
            "Aina halisi ya picha haijathibitishwa. Tumia JPG, PNG au WEBP."
        )

    if mimetype == "image/jpeg" and not raw.endswith(b"\xff\xd9"):
        raise ValueError("Picha ya JPG haijakamilika.")

    if mimetype == "image/png" and b"IEND" not in raw[-16:]:
        raise ValueError("Picha ya PNG haijakamilika.")

    return True


# ------------------------- HTML INTERFACE -------------------------

PAGE = r"""
<!DOCTYPE html>
<html lang="sw">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#050805">
<title>RIGAN AI</title>
<style>
:root{--green:#39ff65;--dark:#050805}
*{box-sizing:border-box}
body{margin:0;background:var(--dark);color:white;font-family:Arial,sans-serif;min-height:100vh;display:flex;flex-direction:column}
header{text-align:center;padding:18px 10px 12px;border-bottom:1px solid #174d22}
h1{margin:0;color:var(--green);letter-spacing:3px;font-size:28px}
.sub{font-size:11px;color:#9bff9b;margin-top:6px;letter-spacing:1px}
#chat{flex:1;overflow-y:auto;padding:14px;max-width:900px;width:100%;margin:auto}
.bubble{padding:12px 14px;border-radius:14px;margin:10px 0;max-width:88%;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.45}
.bot{background:#101a12;border:1px solid #23552c;margin-right:auto}
.user{background:#12351b;border:1px solid var(--green);margin-left:auto}
.who{font-size:10px;color:var(--green);font-weight:bold;margin-bottom:6px;letter-spacing:1px}
.bubble img{display:block;max-width:100%;max-height:420px;border-radius:10px;margin-top:10px}
.controls{width:100%;max-width:900px;margin:0 auto;padding:10px 12px 14px;border-top:1px solid #174d22}
.buttons{display:flex;gap:8px;margin-bottom:10px}
button{border:1px solid var(--green);border-radius:10px;background:#101a12;color:var(--green);padding:12px 10px;font-weight:bold;cursor:pointer}
button.active{background:var(--green);color:#001500}
button:disabled{opacity:.5;cursor:wait}
#message{flex:1;min-width:0;background:#090d09;border:2px solid var(--green);border-radius:13px;color:white;padding:13px;font-size:16px;outline:none}
#send{background:var(--green);color:#001500;padding:0 20px;font-size:17px}
#status{font-size:12px;color:#9bff9b;min-height:16px;padding:0 3px 5px}
.small{font-size:11px;color:#aaa;text-align:center;margin-top:7px}
.entry{display:flex;gap:8px}
@media(max-width:390px){button{font-size:12px;padding:10px 3px}.entry{gap:6px}#send{padding:0 13px}}
</style>
</head>
<body>
<header>
<h1>RIGAN AI</h1>
<div class="sub">ULTIMATE | VOICE + VISION + IMAGE AI</div>
</header>

<main id="chat">
<div class="bubble bot">
<div class="who">RIGAN AI</div>
Habari! Mimi ni RIGAN AI.
Naweza kujibu maswali, kusikiliza sauti,
kuchambua picha na kutengeneza picha.
Andika ujumbe wako au tumia vitufe hapa chini.
</div>
</main>

<section class="controls">
<div id="status"></div>
<div class="buttons">
<button id="listen" type="button">🎙️ SIKILIZA</button>
<button id="voice" class="active" type="button">🔊 SAUTI ON</button>
<button id="picture" type="button">🖼️ PICHA</button>
</div>
<div class="entry">
<input id="message" type="text" placeholder="Sema au andika ujumbe..." autocomplete="off">
<button id="send" type="button">TUMA</button>
</div>
<input id="file" type="file" accept="image/jpeg,image/png,image/webp" hidden>
<div class="small">RIGAN AI ULTIMATE</div>
</section>

<script>
const chat=document.getElementById('chat');
const input=document.getElementById('message');
const statusEl=document.getElementById('status');
const fileInput=document.getElementById('file');

let conversationId=null;
let csrfToken=null;
let voiceOn=true;
let selectedImage=null;
let busy=false;

function status(t){statusEl.textContent=t||'';}

async function initializeSession(){
 const res=await fetch('/api/session',{credentials:'same-origin'});
 if(!res.ok)throw new Error('Session initialization failed');
 const data=await res.json();
 conversationId=data.conversation_id;
 csrfToken=data.csrf_token;
}

function addBubble(text,who='bot',imageUrl=null){
 const box=document.createElement('div');
 box.className='bubble '+who;
 const label=document.createElement('div');
 label.className='who';
 label.textContent=who==='user'?'WEWE':'RIGAN AI';
 box.appendChild(label);
 const body=document.createElement('div');
 body.textContent=text||'';
 box.appendChild(body);
 if(imageUrl){
  const img=document.createElement('img');
  img.src=imageUrl;
  img.alt='Picha';
  box.appendChild(img);
 }
 chat.appendChild(box);
 chat.scrollTop=chat.scrollHeight;
 return box;
}

function speak(text){
 if(!voiceOn||!('speechSynthesis' in window))return;
 speechSynthesis.cancel();
 const u=new SpeechSynthesisUtterance(text);
 u.lang='sw-KE';
 u.rate=1;
 speechSynthesis.speak(u);
}

async function send(){
 const text=input.value.trim();
 if(busy||(!text&&!selectedImage))return;
 if(!conversationId||!csrfToken){
  status('Inaandaa session...');
  return;
 }

 if(!selectedImage&&/^(tengeneza picha|generate image|draw image)\s+/i.test(text)){
  input.value='';
  const prompt=text.replace(/^(tengeneza picha|generate image|draw image)\s+(ya\s+)?/i,'');
  await generateImage(prompt);
  return;
 }

 busy=true;
 document.getElementById('send').disabled=true;
 const localImage=selectedImage?URL.createObjectURL(selectedImage):null;
 addBubble(text||'Tafadhali chambua picha hii.','user',localImage);

 const form=new FormData();
 form.append('message',text);
 if(selectedImage)form.append('image',selectedImage);

 input.value='';
 selectedImage=null;
 fileInput.value='';
 status('RIGAN AI inafikiri...');

 try{
  const res=await fetch('/api/chat',{
   method:'POST',
   credentials:'same-origin',
   headers:{'X-CSRF-Token':csrfToken},
   body:form
  });
  const data=await res.json();
  if(!res.ok)throw new Error(data.error||'Hitilafu imetokea');
  addBubble(data.reply);
  speak(data.reply);
  status('');
 }catch(e){
  addBubble('Samahani: '+e.message);
  status('Angalia muunganisho au Render Logs.');
 }finally{
  if(localImage)URL.revokeObjectURL(localImage);
  busy=false;
  document.getElementById('send').disabled=false;
  input.focus();
 }
}

document.getElementById('send').addEventListener('click',send);
input.addEventListener('keydown',e=>{if(e.key==='Enter')send();});
document.getElementById('picture').onclick=()=>fileInput.click();

fileInput.onchange=()=>{
 const file=fileInput.files[0]||null;
 if(!file){selectedImage=null;return;}
 const allowed=['image/jpeg','image/png','image/webp'];
 if(!allowed.includes(file.type)){
  status('Tumia JPG, PNG au WEBP.');
  fileInput.value='';
  selectedImage=null;
  return;
 }
 if(file.size>6*1024*1024){
  status('Picha iwe chini ya 6 MB.');
  fileInput.value='';
  selectedImage=null;
  return;
 }
 selectedImage=file;
 status('Picha imechaguliwa. Andika swali kisha bonyeza TUMA.');
};

document.getElementById('voice').onclick=()=>{
 voiceOn=!voiceOn;
 document.getElementById('voice').classList.toggle('active',voiceOn);
 document.getElementById('voice').textContent=voiceOn?'🔊 SAUTI ON':'🔇 SAUTI OFF';
 if(!voiceOn&&'speechSynthesis'in window)speechSynthesis.cancel();
};

document.getElementById('listen').onclick=()=>{
 const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
 if(!SR){status('Browser hii haitumii speech recognition. Jaribu Chrome.');return;}
 const rec=new SR();
 rec.lang='sw-KE';
 rec.interimResults=false;
 status('Ninasikiliza... Ruhusu microphone.');
 rec.onresult=e=>{
  input.value=e.results[0][0].transcript;
  status('Sauti imegeuzwa kuwa maandishi. Bonyeza TUMA.');
 };
 rec.onerror=e=>status('Tatizo la microphone: '+e.error);
 rec.onend=()=>{
  if(statusEl.textContent==='Ninasikiliza... Ruhusu microphone.')status('');
 };
 rec.start();
};

async function generateImage(prompt){
 if(!prompt.trim()||busy)return;
 if(!conversationId||!csrfToken){status('Session haijakamilika.');return;}
 busy=true;
 document.getElementById('send').disabled=true;
 addBubble(prompt,'user');
 status('RIGAN AI inatengeneza picha...');
 try{
  const res=await fetch('/api/generate-image',{
   method:'POST',
   credentials:'same-origin',
   headers:{
    'Content-Type':'application/json',
    'X-CSRF-Token':csrfToken
   },
   body:JSON.stringify({prompt})
  });
  const data=await res.json();
  if(!res.ok)throw new Error(data.error||'Image generation failed');
  addBubble(data.message||'Picha imetengenezwa.','bot',data.image||null);
  status(data.image?'Picha imetengenezwa.':'Model imerudisha jibu bila picha.');
 }catch(e){
  addBubble('Imeshindikana kutengeneza picha: '+e.message);
  status('');
 }finally{
  busy=false;
  document.getElementById('send').disabled=false;
 }
}

initializeSession().then(()=>status('')).catch(()=>{
 status('Imeshindikana kuanzisha session. Refresh ukurasa.');
});
</script>
</body>
</html>
"""


# ------------------------- SECURITY HEADERS -------------------------

@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), geolocation=(), payment=()"
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob: https:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none';"
    )
    return response


# ------------------------- ROUTES -------------------------

@app.route("/", methods=["GET"])
def home():
    return render_template_string(PAGE)


@app.route("/api/session", methods=["GET"])
@rate_limit("session")
def create_session():
    conversation_id, csrf_token = ensure_session()
    return jsonify(
        conversation_id=conversation_id,
        csrf_token=csrf_token
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "app": APP_NAME,
        "database": (
            "postgresql" if DATABASE_URL and psycopg2 else "sqlite"
        ),
        "api_key_configured": bool(OPENROUTER_API_KEY),
        "security": "enabled",
    })


@app.route("/api/chat", methods=["POST"])
@rate_limit("chat")
@require_csrf
def chat():
    try:
        conversation_id = session.get("conversation_id")
        if not conversation_id:
            return jsonify(error="Session haipo. Refresh ukurasa."), 403

        message = (request.form.get("message") or "").strip()
        if len(message) > MAX_MESSAGE_LENGTH:
            return jsonify(error="Ujumbe ni mrefu sana."), 400

        image = request.files.get("image")
        if not message and not image:
            return jsonify(error="Andika ujumbe au chagua picha."), 400

        user_content = message or "Tafadhali eleza picha hii."
        identity_reply = (
            creator_identity_answer(message) if not image else None
        )

        if identity_reply:
            save_message(conversation_id, "user", user_content)
            save_message(conversation_id, "assistant", identity_reply)
            return jsonify(reply=identity_reply)

        history = get_history(conversation_id)

        if image:
            if image.mimetype not in (
                "image/jpeg", "image/png", "image/webp"
            ):
                return jsonify(error="Tumia JPG, PNG au WEBP."), 400

            raw = image.read(MAX_IMAGE_SIZE + 1)
            validate_image(raw, image.mimetype)

            encoded = base64.b64encode(raw).decode("ascii")
            data_url = f"data:{image.mimetype};base64,{encoded}"

            content = [
                {"type": "text", "text": user_content},
                {
                    "type": "image_url",
                    "image_url": {"url": data_url}
                },
            ]
            model = VISION_MODEL
        else:
            content = user_content
            model = CHAT_MODEL

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": content})

        reply = openrouter_chat(messages, model)

        save_message(
            conversation_id,
            "user",
            user_content + (" [picha ilitumwa]" if image else "")
        )
        save_message(conversation_id, "assistant", reply)

        return jsonify(reply=reply)

    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    except requests.RequestException:
        app.logger.exception("Chat network error")
        return jsonify(
            error="Huduma ya AI haipatikani kwa sasa. Jaribu tena."
        ), 502

    except Exception:
        app.logger.exception("Chat endpoint failed")
        return jsonify(
            error="Hitilafu ya ndani imetokea. Jaribu tena."
        ), 500


@app.route("/api/generate-image", methods=["POST"])
@rate_limit("image")
@require_csrf
def generate_image():
    try:
        if not session.get("conversation_id"):
            return jsonify(error="Session haipo."), 403

        payload = request.get_json(silent=True) or {}
        prompt = payload.get("prompt")

        if not isinstance(prompt, str):
            return jsonify(error="Prompt si sahihi."), 400

        prompt = prompt.strip()
        if not prompt:
            return jsonify(error="Andika maelezo ya picha."), 400

        if len(prompt) > MAX_IMAGE_PROMPT:
            return jsonify(error="Maelezo ya picha ni marefu sana."), 400

        response = requests.post(
            f"{OPENROUTER_BASE_URL}/images",
            headers=api_headers(),
            json={
                "model": IMAGE_MODEL,
                "prompt": prompt,
                "size": "1024x1024",
            },
            timeout=IMAGE_TIMEOUT,
        )

        if not response.ok:
            raise RuntimeError(
                safe_api_error(response, "OpenRouter image")
            )

        data = response.json()
        items = data.get("data") or []
        item = items[0] if items else {}

        b64 = item.get("b64_json")
        if b64:
            try:
                decoded = base64.b64decode(b64, validate=True)
            except Exception:
                raise RuntimeError("Image response is invalid.")

            if len(decoded) > 7 * 1024 * 1024:
                raise RuntimeError("Generated image is too large.")

            if not decoded.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError("Generated image format is invalid.")

            return jsonify(
                message="Picha imetengenezwa.",
                image="data:image/png;base64," + b64
            )

        image_url = item.get("url")
        if image_url:
            parsed = urlparse(image_url)
            if parsed.scheme != "https" or not parsed.hostname:
                raise RuntimeError("Image URL is invalid.")
            return jsonify(
                message="Picha imetengenezwa.",
                image=image_url
            )

        choices = data.get("choices") or []
        if choices:
            msg = choices[0].get("message") or {}
            images = msg.get("images") or []
            if images and isinstance(images[0], dict):
                image_url = (
                    images[0].get("image_url", {}).get("url")
                )
                if image_url:
                    return jsonify(
                        message="Picha imetengenezwa.",
                        image=image_url
                    )

        raise RuntimeError(
            "Model haikurudisha picha inayoweza kuonyeshwa."
        )

    except requests.RequestException:
        app.logger.exception("Image network error")
        return jsonify(
            error="Huduma ya picha haipatikani kwa sasa."
        ), 502

    except RuntimeError as exc:
        app.logger.warning("Image service error: %s", str(exc))
        return jsonify(
            error="Image generation imeshindwa. "
                  "Angalia model au API configuration."
        ), 502

    except Exception:
        app.logger.exception("Image generation failed")
        return jsonify(
            error="Hitilafu imetokea wakati wa kutengeneza picha."
        ), 500


@app.errorhandler(413)
def file_too_large(_error):
    return jsonify(
        error="Faili ni kubwa mno. Tumia picha chini ya 6 MB."
    ), 413


# ------------------------- STARTUP -------------------------

try:
    init_db()
    app.logger.info("%s database initialized.", APP_NAME)
except Exception:
    app.logger.exception("Database initialization failed")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
            
