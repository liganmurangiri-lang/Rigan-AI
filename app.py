import os
import uuid
import base64
import sqlite3
from datetime import datetime, timezone

import requests
from flask import Flask, request, jsonify, render_template_string

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except Exception:
    psycopg2 = None
    RealDictCursor = None


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

APP_NAME = "RIGAN AI"
OWNER_NAME = os.getenv("OWNER_NAME", "Ligan Murangiri").strip() or "Ligan Murangiri"

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
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

SQLITE_FILE = os.getenv("SQLITE_FILE", "rigan_v16.db")


SYSTEM_PROMPT = f"""
You are {APP_NAME}, an AI assistant created by {OWNER_NAME}.
You are helpful, truthful, respectful, and clear.
You can answer questions, explain ideas, help with learning and writing,
analyze images supplied by the user, and help generate images when the
image-generation service is available.
Do not claim to have abilities or access that you do not have.
If an image-generation request fails, explain that the image service or
selected model may not be available; do not pretend an image was created.
Reply in the language used by the user. You can communicate in Swahili
and English. Be concise unless the user asks for detail.
Only mention the creator when the user asks who created or owns you.
"""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def db_connect():
    if DATABASE_URL and psycopg2:
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        return psycopg2.connect(url, connect_timeout=15)

    conn = sqlite3.connect(SQLITE_FILE, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db_connect()
    try:
        cur = conn.cursor()
        if DATABASE_URL and psycopg2:
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
        else:
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
        cur.execute(
            """
            INSERT INTO chat_messages
            (id, conversation_id, role, content, created_at)
            VALUES (%s, %s, %s, %s, %s)
            """ if DATABASE_URL and psycopg2 else """
            INSERT INTO chat_messages
            (id, conversation_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), conversation_id, role, str(content), utc_now())
        )
        conn.commit()
    finally:
        conn.close()


def get_history(conversation_id, limit=20):
    conn = db_connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT role, content FROM chat_messages
            WHERE conversation_id = %s
            ORDER BY created_at DESC LIMIT %s
            """ if DATABASE_URL and psycopg2 else """
            SELECT role, content FROM chat_messages
            WHERE conversation_id = ?
            ORDER BY created_at DESC LIMIT ?
            """,
            (conversation_id, limit)
        )
        rows = cur.fetchall()
        rows = list(reversed(rows))
        result = []
        for row in rows:
            if isinstance(row, dict):
                role, content = row["role"], row["content"]
            else:
                role, content = row[0], row[1]
            result.append({"role": role, "content": content})
        return result
    finally:
        conn.close()


def api_headers():
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY haijawekwa kwenye Render Environment."
        )
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("APP_URL", "https://riganai.onrender.com"),
        "X-Title": APP_NAME,
    }


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
        timeout=120,
    )

    if not response.ok:
        try:
            detail = response.json().get("error", {}).get("message", response.text)
        except Exception:
            detail = response.text
        raise RuntimeError(
            f"OpenRouter chat error ({response.status_code}): {detail}"
        )

    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("OpenRouter haikurudisha jibu.")
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
        raise RuntimeError("Jibu la AI lilikuwa tupu.")
    return content


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
    if any(p in text for p in patterns):
        return (
            f"Mimi ni {APP_NAME}. Nimetengenezwa na kumilikiwa na "
            f"{OWNER_NAME}."
        )
    return None


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
<input id="file" type="file" accept="image/png,image/jpeg,image/webp" hidden>
<div class="small">RIGAN AI ULTIMATE</div>
</section>

<script>
const chat=document.getElementById('chat');
const input=document.getElementById('message');
const statusEl=document.getElementById('status');
const fileInput=document.getElementById('file');
const conversationId=localStorage.getItem('rigan_v16_conversation')||crypto.randomUUID();
localStorage.setItem('rigan_v16_conversation',conversationId);
let voiceOn=true,selectedImage=null,busy=false;

function status(t){statusEl.textContent=t||'';}

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
  img.src=imageUrl;img.alt='Picha';box.appendChild(img);
 }
 chat.appendChild(box);chat.scrollTop=chat.scrollHeight;return box;
}

function speak(text){
 if(!voiceOn||!('speechSynthesis' in window))return;
 speechSynthesis.cancel();
 const u=new SpeechSynthesisUtterance(text);
 u.lang='sw-KE';u.rate=1;speechSynthesis.speak(u);
}

async function send(){
 const text=input.value.trim();
 if(busy||(!text&&!selectedImage))return;
 if(!selectedImage&&/^(tengeneza picha|generate image|draw image)\s+/i.test(text)){
  input.value='';
  const prompt=text.replace(/^(tengeneza picha|generate image|draw image)\s+(ya\s+)?/i,'');
  await generateImage(prompt);return;
 }
 busy=true;document.getElementById('send').disabled=true;
 const localImage=selectedImage?URL.createObjectURL(selectedImage):null;
 addBubble(text||'Tafadhali chambua picha hii.','user',localImage);
 const form=new FormData();
 form.append('message',text);
 form.append('conversation_id',conversationId);
 if(selectedImage)form.append('image',selectedImage);
 input.value='';selectedImage=null;fileInput.value='';
 status('RIGAN AI inafikiri...');
 try{
  const res=await fetch('/api/chat',{method:'POST',body:form});
  const data=await res.json();
  if(!res.ok)throw new Error(data.error||'Hitilafu imetokea');
  addBubble(data.reply);speak(data.reply);status('');
 }catch(e){
  addBubble('Samahani: '+e.message);status('Angalia API key, model au Render Logs.');
 }finally{
  if(localImage)URL.revokeObjectURL(localImage);
  busy=false;document.getElementById('send').disabled=false;input.focus();
 }
}

document.getElementById('send').addEventListener('click',send);
input.addEventListener('keydown',e=>{if(e.key==='Enter')send();});
document.getElementById('picture').onclick=()=>fileInput.click();
fileInput.onchange=()=>{
 selectedImage=fileInput.files[0]||null;
 if(selectedImage)status('Picha imechaguliwa. Andika swali kisha bonyeza TUMA.');
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
 const rec=new SR();rec.lang='sw-KE';rec.interimResults=false;
 status('Ninasikiliza... Ruhusu microphone.');
 rec.onresult=e=>{input.value=e.results[0][0].transcript;status('Sauti imegeuzwa kuwa maandishi. Bonyeza TUMA.');};
 rec.onerror=e=>status('Tatizo la microphone: '+e.error);
 rec.onend=()=>{if(statusEl.textContent==='Ninasikiliza... Ruhusu microphone.')status('');};
 rec.start();
};

async function generateImage(prompt){
 if(!prompt.trim()||busy)return;
 busy=true;document.getElementById('send').disabled=true;
 addBubble(prompt,'user');status('RIGAN AI inatengeneza picha...');
 try{
  const res=await fetch('/api/generate-image',{
   method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({prompt})
  });
  const data=await res.json();
  if(!res.ok)throw new Error(data.error||'Image generation failed');
  addBubble(data.message||'Picha imetengenezwa.','bot',data.image||null);
  status(data.image?'Picha imetengenezwa.':'Model imerudisha jibu bila picha.');
 }catch(e){addBubble('Imeshindikana kutengeneza picha: '+e.message);status('');}
 finally{busy=false;document.getElementById('send').disabled=false;}
}
</script>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def home():
    return render_template_string(PAGE)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "app": APP_NAME,
        "database": "postgresql" if DATABASE_URL and psycopg2 else "sqlite",
        "api_key_configured": bool(OPENROUTER_API_KEY),
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        message = (request.form.get("message") or "").strip()
        conversation_id = (request.form.get("conversation_id") or "").strip()

        if not conversation_id or len(conversation_id) > 100:
            return jsonify(error="conversation_id si sahihi."), 400

        image = request.files.get("image")
        if not message and not image:
            return jsonify(error="Andika ujumbe au chagua picha."), 400

        user_content = message or "Tafadhali eleza picha hii."
        identity_reply = creator_identity_answer(message) if not image else None

        if identity_reply:
            save_message(conversation_id, "user", user_content)
            save_message(conversation_id, "assistant", identity_reply)
            return jsonify(reply=identity_reply)

        history = get_history(conversation_id)

        if image:
            if image.mimetype not in ("image/jpeg", "image/png", "image/webp"):
                return jsonify(error="Tumia picha ya JPG, PNG au WEBP."), 400
            raw = image.read()
            if len(raw) > 6 * 1024 * 1024:
                return jsonify(error="Picha iwe chini ya 6 MB."), 400
            encoded = base64.b64encode(raw).decode("utf-8")
            data_url = f"data:{image.mimetype};base64,{encoded}"
            content = [
                {"type": "text", "text": user_content},
                {"type": "image_url", "image_url": {"url": data_url}},
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

    except Exception as exc:
        app.logger.exception("Chat endpoint failed")
        return jsonify(error=str(exc)[:700]), 500


@app.route("/api/generate-image", methods=["POST"])
def generate_image():
    try:
        payload = request.get_json(silent=True) or {}
        prompt = (payload.get("prompt") or "").strip()

        if not prompt:
            return jsonify(error="Andika maelezo ya picha unayotaka."), 400
        if len(prompt) > 1500:
            return jsonify(error="Maelezo ya picha ni marefu sana."), 400

        response = requests.post(
            f"{OPENROUTER_BASE_URL}/images",
            headers=api_headers(),
            json={
                "model": IMAGE_MODEL,
                "prompt": prompt,
                "size": "1024x1024",
            },
            timeout=180,
        )

        if not response.ok:
            try:
                error_data = response.json().get("error", {})
                detail = error_data.get("message", response.text)
            except Exception:
                detail = response.text
            raise RuntimeError(
                f"OpenRouter image error ({response.status_code}): {detail}"
            )

        data = response.json()
        items = data.get("data") or []
        item = items[0] if items else {}
        b64 = item.get("b64_json")

        if b64:
            image_url = "data:image/png;base64," + b64
            return jsonify(message="Picha imetengenezwa.", image=image_url)

        image_url = item.get("url")
        if image_url:
            return jsonify(message="Picha imetengenezwa.", image=image_url)

        # Some image-capable endpoints may return an image in a different shape.
        choices = data.get("choices") or []
        if choices:
            msg = choices[0].get("message") or {}
            images = msg.get("images") or []
            if images:
                first = images[0]
                if isinstance(first, dict):
                    image_url = first.get("image_url", {}).get("url")
                    if image_url:
                        return jsonify(message="Picha imetengenezwa.", image=image_url)

        raise RuntimeError(
            "Model haikurudisha picha inayoweza kuonyeshwa. "
            "Thibitisha IMAGE_MODEL na uwezo wa image generation wa model hiyo."
        )

    except Exception as exc:
        app.logger.exception("Image generation failed")
        return jsonify(error=str(exc)[:700]), 500


@app.errorhandler(413)
def file_too_large(_error):
    return jsonify(error="Faili ni kubwa mno. Tumia picha chini ya 6 MB."), 413


# Initialize database when the application starts.
try:
    init_db()
except Exception:
    app.logger.exception("Database initialization failed")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
