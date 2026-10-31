
from flask import Flask, request, jsonify
import os
import json
import base64
from openai import OpenAI

app = Flask(__name__)

# OpenAI connection
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Memory file
DB_FILE = "akili.json"

def load_memory():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_memory(memory):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

memory = load_memory()

SYSTEM_PROMPT = """
Wewe ni RIGAN AI V15, msaidizi mwenye akili.
Jibu kwa Kiswahili au Kiingereza kulingana na lugha ya mtumiaji.
Una ujuzi wa sayansi, elimu, teknolojia na mambo ya dunia.
Toa majibu sahihi, ya kueleweka na yenye msaada.
Usibuni taarifa usizozijua.
Kama hujui jambo, sema wazi.
Kumbuka taarifa ambazo mtumiaji amekufundisha.
"""

@app.route("/")
def home():
    return """
    <h1>RIGAN AI V15</h1>
    <p>SMART INTELLIGENCE</p>
    <form id="chat">
      <input id="message" placeholder="Andika ujumbe..." required>
      <button>Send</button>
    </form>
    <pre id="answer"></pre>
    <script>
    document.getElementById("chat").onsubmit = async function(e) {
      e.preventDefault();
      let message = document.getElementById("message").value;
      let result = await fetch("/chat", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({message:message})
      });
      let data = await result.json();
      document.getElementById("answer").innerText =
        data.answer || data.error;
    };
    </script>
    """

@app.route("/chat", methods=["POST"])
@app.route("/ask", methods=["POST"])
def chat():
    global memory

    try:
        data = request.get_json(silent=True) or {}
        message = str(data.get("message", "")).strip()

        if not message:
            return jsonify({"error": "Andika ujumbe kwanza."}), 400

        # Teaching mode
        if message.lower().startswith("nifundishe:"):
            knowledge = message.split(":", 1)[1].strip()

            if not knowledge:
                return jsonify({"answer": "Niambie unataka kunifundisha nini."})

            memory.append({
                "type": "knowledge",
                "content": knowledge
            })
            save_memory(memory)

            return jsonify({
                "answer": "Asante! RIGAN AI imehifadhi ulichoifundisha."
            })

        # Build memory context
        saved_knowledge = "\n".join(
            item["content"] for item in memory[-50:]
            if item.get("type") == "knowledge"
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT +
                    "\n\nMaarifa yaliyohifadhiwa:\n" + saved_knowledge
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            max_tokens=1200
        )

        answer = response.choices[0].message.content

        memory.append({
            "type": "conversation",
            "question": message,
            "answer": answer
        })
        save_memory(memory)

        return jsonify({"answer": answer})

    except Exception as e:
        return jsonify({"error": "RIGAN AI imepata tatizo: " + str(e)}), 500

@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "name": "RIGAN AI V15"
    })

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
)
                  
