
import os
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI

app = Flask(__name__)

OWNER_NAME = os.getenv("OWNER_NAME", "RIGAN")
AI_NAME = "RIGAN AGI V3"
API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=API_KEY) if API_KEY else None

DB_FILE = "rigan_memory.json"

def load_memory():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_memory(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route("/")
def home():
    return render_template_string("""
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>RIGAN AGI V3</title>
    <style>
    body {background:#101827;color:white;font-family:Arial;
    text-align:center;padding:20px}
    h1 {color:#00e5ff}
    #chat {max-width:650px;margin:auto}
    #messages {height:55vh;overflow:auto;background:#1c293b;
    padding:15px;border-radius:12px;text-align:left}
    input {width:70%;padding:14px;border-radius:8px;border:0}
    button {padding:14px;background:#00c8df;border:0;
    border-radius:8px;font-weight:bold}
    </style>
    </head>
    <body>
    <h1>RIGAN AGI V3</h1>
    <p>Personal Artificial Intelligence</p>
    <div id="chat">
    <div id="messages">RIGAN: Habari! Mimi ni RIGAN AGI V3.
    Niko tayari kukusaidia.</div><br>
    <input id="question" placeholder="Uliza RIGAN swali...">
    <button onclick="send()">Tuma</button>
    </div>
    <script>
    async function send(){
      let q=document.getElementById("question").value;
      if(!q)return;
      let m=document.getElementById("messages");
      m.innerHTML += "<p><b>Wewe:</b> "+q.replace(/</g,"&lt;")+"</p>";
      document.getElementById("question").value="";
      let p=document.createElement("p");
      p.innerHTML="RIGAN: Inafikiri...";
      m.appendChild(p);
      try{
        let r=await fetch("/chat",{method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({message:q})});
        let d=await r.json();
        p.textContent="RIGAN: "+(d.reply||d.error);
      }catch(e){p.textContent="RIGAN: Tatizo la mtandao."}
      m.scrollTop=m.scrollHeight;
    }
    </script>
    </body>
    </html>
    """)

@app.route("/chat", methods=["POST"])
def chat():
    if not client:
        return jsonify({"error":"OPENAI_API_KEY haijawekwa kwenye Render."}), 500

    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify({"error":"Andika swali kwanza."}), 400

    memory = load_memory()
    history = memory.get("history", [])

    history.append({
        "role": "user",
        "content": message
    })

    history = history[-20:]

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            messages=[
                {
                    "role": "system",
                    "content": f"""
                    Wewe ni {AI_NAME}, AI binafsi iliyoundwa na {OWNER_NAME}.
                    Jibu kwa lugha anayotumia mtumiaji.
                    Una ujuzi wa sayansi, elimu, teknolojia,
                    historia, biashara na masuala ya dunia.
                    Toa majibu sahihi, yaeleweke na yenye manufaa.
                    Usidai kuwa unajua kitu usichokijua.
                    Mtengenezaji wako ni {OWNER_NAME}.
                    """
                }
            ] + history
        )

        reply = response.choices[0].message.content

        history.append({
            "role": "assistant",
            "content": reply
        })

        memory["history"] = history
        memory["owner"] = OWNER_NAME
        memory["updated"] = datetime.now().isoformat()
        save_memory(memory)

        return jsonify({
            "ai": AI_NAME,
            "owner": OWNER_NAME,
            "reply": reply
        })

    except Exception as e:
        app.logger.exception("RIGAN API error")
        return jsonify({"error":"Kuna tatizo la AI API. Angalia Render Logs."}), 500

@app.route("/health")
def health():
    return jsonify({
        "status":"online",
        "ai":AI_NAME,
        "owner":OWNER_NAME
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
  
