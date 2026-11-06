
import os
import io
import base64
import sqlite3
import uuid
from datetime import datetime, timezone

from flask import Flask, request, jsonify, render_template_string, send_file
from openai import OpenAI

APP_NAME = "RIGAN AGI V16"
DATA_DIR = "/var/data" if os.path.isdir("/var/data") else os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DATA_DIR, "rigan_v16.db")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024

CHAT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-sol")
IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")
TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")

SYSTEM_PROMPT = """
You are RIGAN AGI V16, a helpful AI assistant.
Answer clearly in Kiswahili or English.
Help with science, education, technology, history and general knowledge.
Analyze uploaded images when provided.
Be honest about uncertainty and never claim actions you did not perform.
"""

def get_client():
    key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY haijawekwa kwenye Render Environment.")
    return OpenAI(api_key=key)

def db():
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
        con.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_session
        ON messages(session_id, id)
        """)

def save_message(session_id, role, content):
    with db() as con:
        con.execute(
            "INSERT INTO messages(session_id,role,content,created_at) VALUES(?,?,?,?)",
            (session_id, role, content, datetime.now(timezone.utc).isoformat())
        )

def get_history(session_id, limit=12):
    with db() as con:
        rows = con.execute(
            "SELECT role,content FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

def image_data_url(upload):
    if not upload or not upload.filename:
        return None
    mime = (upload.mimetype or "").lower()
    if mime not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        raise ValueError("Tuma picha ya JPG, PNG, WEBP au GIF.")
    raw = upload.read()
    if not raw:
        raise ValueError("Picha haina data.")
    return "data:" + mime + ";base64," + base64.b64encode(raw).decode("ascii")

@app.get("/")
def home():
    return render_template_string(PAGE, app_name=APP_NAME)

@app.get("/health")
def health():
    return jsonify({"status": "ok", "app": APP_NAME})

@app.post("/api/chat")
def chat():
    try:
        message = (request.form.get("message") or "").strip()
        session_id = (request.form.get("session_id") or str(uuid.uuid4()))[:100]

        if not message:
            return jsonify({"error": "Andika swali kwanza."}), 400

        image_url = image_data_url(request.files.get("image"))
        history = get_history(session_id)

        inputs = [
            {"role": item["role"], "content": item["content"]}
            for item in history
        ]

        if image_url:
            user_content = [
                {"type": "input_text", "text": message},
                {"type": "input_image", "image_url": image_url}
            ]
        else:
            user_content = message

        inputs.append({"role": "user", "content": user_content})

        result = get_client().responses.create(
            model=CHAT_MODEL,
            instructions=SYSTEM_PROMPT,
            input=inputs,
            max_output_tokens=1200
        )

        answer = (result.output_text or "").strip()
        if not answer:
            answer = "Samahani, jaribu tena."

        save_message(session_id, "user", message + (" [Picha ilitumwa]" if image_url else ""))
        save_message(session_id, "assistant", answer)

        return jsonify({"answer": answer, "session_id": session_id})

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        app.logger.exception("Chat error")
        return jsonify({"error": "RIGAN CHAT ERROR: " + str(e)[:500]}), 500

@app.post("/api/image")
def generate_image():
    try:
        prompt = (request.form.get("prompt") or "").strip()
        if not prompt:
            return jsonify({"error": "Eleza picha unayotaka."}), 400

        result = get_client().images.generate(
            model=IMAGE_MODEL,
            prompt=prompt,
            size="1024x1024"
        )

        return jsonify({
            "image": "data:image/png;base64," + result.data[0].b64_json
        })

    except Exception as e:
        app.logger.exception("Image error")
        return jsonify({"error": "IMAGE ERROR: " + str(e)[:500]}), 500

@app.post("/api/transcribe")
def transcribe():
    try:
        audio = request.files.get("audio")
        if not audio:
            return jsonify({"error": "Tuma sauti kwanza."}), 400

        content = audio.read()
        if not content:
            return jsonify({"error": "Sauti haina data."}), 400

        result = get_client().audio.transcriptions.create(
            model=TRANSCRIBE_MODEL,
            file=(audio.filename or "recording.webm",
                  io.BytesIO(content),
                  audio.mimetype or "audio/webm")
        )

        return jsonify({"text": result.text})

    except Exception as e:
        app.logger.exception("Transcription error")
        return jsonify({"error": "VOICE INPUT ERROR: " + str(e)[:500]}), 500

@app.post("/api/speak")
def speak():
    try:
        text = (request.form.get("text") or "").strip()
        if not text:
            return jsonify({"error": "Hakuna maandishi."}), 400

        result = get_client().audio.speech.create(
            model=TTS_MODEL,
            voice="alloy",
            input=text[:4000],
            response_format="mp3"
        )

        return send_file(
            io.BytesIO(result.read()),
            mimetype="audio/mpeg",
            download_name="rigan-response.mp3"
        )

    except Exception as e:
        app.logger.exception("Speech error")
        return jsonify({"error": "SPEECH ERROR: " + str(e)[:500]}), 500

@app.get("/api/history")
def history():
    session_id = (request.args.get("session_id") or "")[:100]
    return jsonify({"messages": get_history(session_id, 50)})

PAGE = r"""
<!DOCTYPE html>
<html lang="sw">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ app_name }}</title>
<style>
body{margin:0;background:#101522;color:white;font-family:Arial}
header{text-align:center;padding:18px;background:#192235}
main{max-width:850px;margin:auto;padding:15px}
.panel{background:#192235;padding:15px;border-radius:14px}
.tabs,.controls{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
button{padding:12px;border:0;border-radius:9px;background:#607fff;color:white;font-weight:bold}
textarea{width:100%;box-sizing:border-box;background:#101522;color:white;padding:13px;border-radius:10px;min-height:75px}
#chatlog{height:45vh;overflow:auto}
.msg{padding:12px;margin:9px 0;border-radius:10px;white-space:pre-wrap}
.user{background:#30466d}.bot{background:#27334a}
input{max-width:100%}
img{max-width:100%;border-radius:12px;margin-top:12px}
.status{color:#ffcc80;white-space:pre-wrap}
.hidden{display:none}
</style>
</head>
<body>
<header>
<h2>🤖 RIGAN AGI V16</h2>
<p>Smart AI Assistant</p>
</header>
<main>
<div class="tabs">
<button onclick="tab('chat')">💬 Chat</button>
<button onclick="tab('draw')">🎨 Chora picha</button>
</div>
<section class="panel" id="chatPanel">
<div id="chatlog">
<div class="msg bot">Karibu RIGAN AGI V16! Niulize swali.</div>
</div>
<textarea id="message" placeholder="Andika swali hapa..."></textarea>
<div class="controls">
<input type="file" id="photo" accept="image/*">
<button onclick="sendChat()">Tuma</button>
<button onclick="recordAudio()">🎙️ Rekodi</button>
</div>
<div id="chatStatus" class="status"></div>
</section>
<section class="panel hidden" id="drawPanel">
<h3>Tengeneza picha</h3>
<textarea id="prompt" placeholder="Eleza picha unayotaka RIGAN ichore..."></textarea>
<button onclick="drawImage()">Tengeneza picha</button>
<div id="imageStatus" class="status"></div>
<div id="imageResult"></div>
</section>
</main>
<script>
const sid=localStorage.getItem('rigan_session') || String(Date.now());
localStorage.setItem('rigan_session',sid);

function tab(name){
 document.getElementById('chatPanel').classList.toggle('hidden',name!=='chat');
 document.getElementById('drawPanel').classList.toggle('hidden',name!=='draw');
}
function addMessage(text,who){
 const log=document.getElementById('chatlog');
 const div=document.createElement('div');
 div.className='msg '+who;
 const body=document.createElement('div');
 body.textContent=text;
 div.appendChild(body);
 if(who==='bot'){
  const btn=document.createElement('button');
  btn.textContent='🔊 Sikiliza jibu';
  btn.onclick=()=>speakText(text,btn);
  div.appendChild(btn);
 }
 log.appendChild(div);
 log.scrollTop=log.scrollHeight;
}
async function speakText(text,btn){
 btn.disabled=true;
 try{
  const f=new FormData();f.append('text',text);
  const r=await fetch('/api/speak',{method:'POST',body:f});
  if(!r.ok){const d=await r.json();throw Error(d.error||'Sauti error');}
  const blob=await r.blob();
  const url=URL.createObjectURL(blob);
  const audio=new Audio(url);
  audio.onended=()=>URL.revokeObjectURL(url);
  await audio.play();
 }catch(e){document.getElementById('chatStatus').textContent=e.message;}
 finally{btn.disabled=false;}
}
async function sendChat(){
 const msg=document.getElementById('message');
 const photo=document.getElementById('photo');
 const status=document.getElementById('chatStatus');
 if(!msg.value.trim()&&!photo.files.length)return;
 const f=new FormData();
 f.append('message',msg.value.trim()||'Eleza picha hii.');
 f.append('session_id',sid);
 if(photo.files.length)f.append('image',photo.files[0]);
 addMessage(msg.value.trim()||'Eleza picha hii.','user');
 msg.value='';photo.value='';
 status.textContent='RIGAN inafikiria...';
 try{
  const r=await fetch('/api/chat',{method:'POST',body:f});
  const d=await r.json();
  if(!r.ok)throw Error(d.error||'Hitilafu');
  addMessage(d.answer,'bot');status.textContent='';
 }catch(e){status.textContent=e.message;}
}
async function drawImage(){
 const prompt=document.getElementById('prompt').value.trim();
 const status=document.getElementById('imageStatus');
 if(!prompt)return;
 status.textContent='RIGAN inachora picha...';
 document.getElementById('imageResult').innerHTML='';
 try{
  const f=new FormData();f.append('prompt',prompt);
  const r=await fetch('/api/image',{method:'POST',body:f});
  const d=await r.json();
  if(!r.ok)throw Error(d.error||'Image error');
  const img=document.createElement('img');
  img.src=d.image;
  document.getElementById('imageResult').appendChild(img);
  status.textContent='Picha imetengenezwa.';
 }catch(e){status.textContent=e.message;}
}
async function recordAudio(){
 const status=document.getElementById('chatStatus');
 try{
  const stream=await navigator.mediaDevices.getUserMedia({audio:true});
  const rec=new MediaRecorder(stream);
  const chunks=[];
  rec.ondataavailable=e=>chunks.push(e.data);
  rec.onstop=async()=>{
   stream.getTracks().forEach(t=>t.stop());
   const f=new FormData();
   f.append('audio',new Blob(chunks,{type:rec.mimeType||'audio/webm'}),'recording.webm');
   status.textContent='Inatambua sauti...';
   try{
    const r=await fetch('/api/transcribe',{method:'POST',body:f});
    const d=await r.json();
    if(!r.ok)throw Error(d.error||'Sauti error');
    document.getElementById('message').value=d.text;
    status.textContent='Sauti imegeuzwa kuwa maandishi. Bonyeza Tuma.';
   }catch(e){status.textContent=e.message;}
  };
  rec.start();
  status.textContent='Inarekodi kwa sekunde 8...';
  setTimeout(()=>{if(rec.state!=='inactive')rec.stop();},8000);
 }catch(e){status.textContent='Ruhusu microphone: '+e.message;}
}
document.getElementById('message').addEventListener('keydown',e=>{
 if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChat();}
});
</script>
</body>
</html>
"""

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
