from flask import Flask, request, jsonify
import os, datetime, requests, json

app = Flask(__name__)

HTML = """<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><title>RiganAI - ChatGPT Style</title><style>
*{margin:0;padding:0;box-sizing:border-box;font-family:Inter,sans-serif}
body{background:#212121;color:#ececec;display:flex;height:100vh}
.sidebar{width:260px;background:#171717;padding:12px;display:flex;flex-direction:column;gap:10px}
.newchat{background:#212121;padding:12px;border-radius:10px;cursor:pointer;border:1px solid #333;text-align:center}
.newchat:hover{background:#2f2f2f}
.side-foot{margin-top:auto;font-size:12px;color:#888;padding:10px}
.main{flex:1;display:flex;flex-direction:column;background:#212121}
header{padding:16px;text-align:center;border-bottom:1px solid #2f2f2f;font-weight:600}
header span{color:#ab68ff}
.chat{flex:1;overflow-y:auto;padding:0}
.row{padding:24px 0;border-bottom:1px solid #2f2f2f0d}
.row-inner{max-width:750px;margin:0 auto;display:flex;gap:20px;padding:0 20px}
.avatar{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0}
.user-av{background:#5436DA} .ai-av{background:#000;border:1px solid #333}
.text{line-height:1.7;white-space:pre-wrap;font-size:15px}
.input-area{padding:20px;background:linear-gradient(#21212100,#212121 40%)}
.input-box{max-width:750px;margin:0 auto;background:#2f2f2f;border-radius:24px;display:flex;align-items:center;padding:8px 12px;gap:10px}
input{flex:1;background:transparent;border:none;color:#fff;outline:none;padding:10px;font-size:16px}
button{background:#fff;color:#000;border:none;width:32px;height:32px;border-radius:50%;font-weight:bold;cursor:pointer}
.welcome{max-width:750px;margin:60px auto;text-align:center}
.welcome h1{font-size:32px;margin-bottom:10px}
.welcome p{color:#888}
.typing{opacity:0.6;font-style:italic}
@media(max-width:700px){.sidebar{display:none}}
</style></head><body>
<div class="sidebar"><div class="newchat" onclick="location.reload()">+ New chat</div><div style="padding:10px;font-size:14px;color:#ccc">RiganAI History</div><div class="side-foot">RIGAN MARINA V5<br>● ONLINE • ChatGPT Mode</div></div>
<div class="main"><header>RIGAN <span>MARINA</span> V5</header>
<div class="chat" id="chat"><div class="welcome" id="welcome"><h1>Mambo Regan? 🔥</h1><p>Mimi ni RiganAI, toleo kama ChatGPT. Niulize chochote!</p></div></div>
<div class="input-area"><div class="input-box"><input id="inp" placeholder="Message RiganAI..." onkeypress="if(event.key==='Enter')send()"><button onclick="send()">↑</button></div></div>
</div>
<script>
function addRow(role, txt){
 let welcome=document.getElementById('welcome');if(welcome)welcome.style.display='none';
 let chat=document.getElementById('chat');
 let row=document.createElement('div');row.className='row';
 let inner=document.createElement('div');inner.className='row-inner';
 let av=document.createElement('div');av.className='avatar '+(role==='user'?'user-av':'ai-av');av.innerText=role==='user'?'R':'AI';
 let t=document.createElement('div');t.className='text';t.innerText=txt;
 inner.appendChild(av);inner.appendChild(t);row.appendChild(inner);chat.appendChild(row);chat.scrollTop=chat.scrollHeight;return t;
}
async function send(){
 let i=document.getElementById('inp');let txt=i.value.trim();if(!txt)return;
 addRow('user',txt);i.value='';
 let aiDiv=addRow('ai','');aiDiv.className+=' typing';aiDiv.innerText='RiganAI inaandika...';
 let r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:txt})});
 let d=await r.json();aiDiv.classList.remove('typing');aiDiv.innerText=d.reply;
}
</script></body></html>"""

def get_ai_reply(user_msg):
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        try:
            resp = requests.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type":"application/json"},
                json={"model":"gpt-3.5-turbo","messages":[{"role":"system","content":"Wewe ni RiganAI, AI ya RIGAN MARINA. Ongea Swahili Sheng, uwe mcheshi na msaada."},{"role":"user","content":user_msg}]},
                timeout=25)
            return resp.json()['choices'][0]['message']['content']
        except Exception as e:
            print(e)
    m=user_msg.lower()
    if 'habari' in m or 'mambo' in m or 'poa' in m:
        return "Poa sana Regan! 🔥 Mimi RiganAI V5 - sasa niko kama ChatGPT! Niko fiti sana. Unataka nikusaidie nini leo? Coding? Biashara? Au idea mpya?"
    elif 'nani wewe' in m or 'wewe ni nani' in m:
        return "Mimi ni RiganAI V5, AI ya RIGAN MARINA 🚀. Nimetengenezwa na wewe Regan, na lengo langu ni kuwa kama ChatGPT lakini na style yako! Niko tayari kukusaidia chochote."
    elif 'tengeneza' in m or 'code' in m or 'jenga' in m:
        return f"Naweza kukutengenezea! Umeomba: '{user_msg}'. Niambie undani zaidi - unataka website, app, au bot? Mimi RiganAI niko tayari kuku-code sai hii! 💻"
    elif 'mapenzi' in m or 'mrembo' in m:
        return "Hehe 😅 mambo ya mapenzi Regan? RiganAI iko hapa kukupa advice kali. Niambie shida iko wapi?"
    else:
        return f"Sawa Regan, nimekuelewa: '{user_msg}'\n\nHii ni RiganAI V5 ChatGPT mode! 🧠\n\nNaweza:\n• Kukuandikia code yoyote\n• Kukupa ideas za biashara\n• Kuandika barua, CV, captions\n• Kukufundisha kitu chochote\n\nNiambie tu unataka nini next, nikupe jibu kali kama ChatGPT!"

@app.route('/')
def home(): return HTML

@app.route('/chat', methods=['POST'])
def chat():
    msg = request.get_json().get('message','')
    reply = get_ai_reply(msg)
    return jsonify({"reply": reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000)))
