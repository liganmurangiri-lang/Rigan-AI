
import os
import json
import uuid
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

API_KEY = os.environ.get("OPENROUTER_API_KEY")
MODEL = "openrouter/free"
DB_FILE = "akili.json"

OWNER = os.environ.get("OWNER_NAME", "Mtengenezaji wa RIGAN AGI")

SYSTEM_PROMPT = f"""
Wewe ni RIGAN AGI, AI msaidizi mwenye akili na heshima.
Mtengenezaji wako ni {OWNER}.

MAJUKUMU YAKO:
- Jibu maswali kwa Kiswahili na Kiingereza.
- Saidia sayansi, elimu, teknolojia, historia na maarifa ya dunia.
- Eleza mambo kwa usahihi na kwa urahisi.
- Kama hujui jambo, sema ukweli badala ya kubuni.
- Msaidie mtumiaji kujifunza na kutatua matatizo.
- Hifadhi muktadha wa mazungumzo kupitia historia inayotumwa.
- Usidai kuwa umejifunza au kufanya utafiti kama hukufanya hivyo.
Wewe ni RIGAN AGI.
"""

def load_db():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_db(db):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Database error:", str(e))

PAGE = """
<!DOCTYPE html>
<html lang="sw">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RIGAN AGI</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#101522;color:white;font-family:Arial,sans-serif}
header{padding:18px;background:#080d18;text-align:center;border-bottom:1px solid #29334a}
header h2{margin:0;color:#35d49a}
header p{margin:6px;color:#aab5c8;font-size:13px}
main{max-width:850px;margin:auto;padding:15px}
#chat{height:65vh;overflow-y:auto;padding:10px}
.msg{padding:13px 15px;margin:12px 0;border-radius:13px;line-height:1.6;white-space:pre-wrap;overflow-wrap:anywhere}
.user{background:#214d65;margin-left:12%}
.bot{background:#202a3d;margin-right:8%}
form{display:flex;gap:8px;position:sticky;bottom:0;background:#101522;padding:10px 0}
textarea{flex:1;resize:none;min-height:52px;max-height:130px;padding:14px;border-radius:12px;border:1px solid #526078;background:#202a3d;color:white;font-size:16px}
button{border:0;border-radius:12px;padding:12px 19px;background:#20c997;color:#071b16;font-weight:bold;font-size:16px}
button:disabled{opacity:.5}
small{color:#9aa9bf}
</style>
</head>
<body>
<header>
<h2>RIGAN AGI</h2>
<p>Artificial Intelligence • Kiswahili • English</p>
</header>
<main>
<div id="chat">
<div class="msg bot">Karibu! Mimi ni RIGAN AGI. Niulize swali lolote.</div>
</div>
<form id="form">
<textarea id="message" placeholder="Andika swali lako hapa..." required></textarea>
<button id="send">TUMA</button>
</form>
<p><small>RIGAN AGI inaweza kutumia modeli za bure zenye vikomo vya matumizi.</small></p>
</main>
<script>
const chat=document.getElementById("chat");
const form=document.getElementById("form");
const input=document.getElementById("message");
const send=document.getElementById("send");

let conversationId=localStorage.getItem("rigan_id");
if(!conversationId){
 conversationId=crypto.randomUUID();
 localStorage.setItem("rigan_id",conversationId);
}

function addMessage(text,who){
 const div=document.createElement("div");
 div.className="msg "+who;
 div.textContent=text;
 chat.appendChild(div);
 chat.scrollTop=chat.scrollHeight;
 return div;
}

form.addEventListener("submit",async(e)=>{
 e.preventDefault();
 const message=input.value.trim();
 if(!message)return;

 addMessage(message,"user");
 input.value="";
 send.disabled=true;
 const waiting=addMessage("RIGAN AGI inafikiria...","bot");

 try{
  const response=await fetch("/chat",{
   method:"POST",
   headers:{"Content-Type":"application/json"},
   body:JSON.stringify({
    message:message,
    conversation_id:conversationId
   })
  });

  const data=await response.json();
  waiting.textContent=data.reply || data.error || "Hakuna jibu.";
 }catch(error){
  waiting.textContent="Imeshindikana kuwasiliana na server. Jaribu tena.";
 }
 send.disabled=false;
 input.focus();
});
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
        "status": "online",
        "assistant": "RIGAN AGI",
        "provider": "OpenRouter"
    })

@app.route("/chat", methods=["POST"])
def chat():
    if not API_KEY:
        return jsonify({
            "error": "OPENROUTER_API_KEY haijawekwa kwenye Render."
        }), 500

    data = request.get_json(silent=True) or {}
    message = str(data.get("message") or data.get("prompt") or "").strip()
    conversation_id = str(data.get("conversation_id") or "default")[:100]

    if not message:
        return jsonify({"error": "Tafadhali andika swali."}), 400

    if len(message) > 10000:
        return jsonify({"error": "Swali ni refu sana."}), 400

    db = load_db()
    history = db.get(conversation_id, [])

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history[-12:])
    messages.append({"role": "user", "content": message})

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "X-OpenRouter-Title": "RIGAN AGI"
            },
            json={
                "model": MODEL,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1200
            },
            timeout=90
        )

        if response.status_code != 200:
            try:
                details = response.json().get("error", {}).get("message", "")
            except Exception:
                details = response.text[:300]

            print("OpenRouter error:", response.status_code, details)
            return jsonify({
                "error": f"OpenRouter error {response.status_code}: {details}"
            }), 502

        result = response.json()
        answer = result["choices"][0]["message"]["content"]

        if not isinstance(answer, str):
            answer = str(answer)

        history.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": answer}
        ])

        db[conversation_id] = history[-30:]
        save_db(db)

        return jsonify({
            "reply": answer,
            "response": answer,
            "assistant": "RIGAN AGI"
        })

    except requests.Timeout:
        return jsonify({"error": "AI imechelewa kujibu. Jaribu tena."}), 504
    except requests.RequestException as e:
        print("Connection error:", str(e))
        return jsonify({"error": "Tatizo la kuunganisha OpenRouter."}), 502
    except Exception as e:
        print("Application error:", str(e))
        return jsonify({"error": "Hitilafu ya mfumo. Angalia Render Logs."}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
