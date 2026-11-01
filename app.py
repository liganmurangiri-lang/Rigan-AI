
from flask import Flask, request, jsonify
import os, json, urllib.parse, urllib.request, random
from datetime import datetime, timedelta

app = Flask(__name__)
DB_FILE = "/tmp/akili_v58.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE,"r",encoding="utf-8") as f: return json.load(f)
        except: return {"lessons":{}}
    return {"lessons":{}}

def save_db(db):
    try:
        with open(DB_FILE,"w",encoding="utf-8") as f: json.dump(db,f,ensure_ascii=False,indent=2)
    except: pass

brain = load_db()
if "lessons" not in brain: brain["lessons"]={}

def get_direct_answer(query):
    try:
        q = query.lower().strip()
        clean = q
        for b in ["inapatikana nchi gani","inapatikana wapi","ni wapi","ni nini","iko wapi","?","nani","ni","ya"]:
            clean = clean.replace(b,"")
        clean = clean.strip()
        if len(clean) < 2: clean = query

        # Wikipedia direct
        wiki_q = urllib.parse.quote(clean.replace(" ","_"))
        for lang in ["en","sw"]:
            try:
                url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{wiki_q}"
                req = urllib.request.Request(url, headers={'User-Agent':'RiganV58Direct'})
                with urllib.request.urlopen(req, timeout=4) as res:
                    data = json.loads(res.read().decode('utf-8'))
                    if "extract" in data and len(data["extract"]) > 20:
                        txt = data["extract"][:800]
                        brain["lessons"][query.lower()] = txt
                        save_db(brain)
                        return txt
            except: continue
    except: pass
    return None

# DATABASE SAHIHI 100%
BASE = {
    "safaricom inapatikana nchi gani": "Safaricom inapatikana KENYA.",
    "safaricom": "Safaricom inapatikana KENYA.",
    "airtel inapatikana nchi gani": "Airtel inapatikana KENYA na INDIA.",
    "airtel": "Airtel inapatikana KENYA na INDIA.",
    "tesla inapatikana nchi gani": "Tesla inapatikana USA.",
    "tesla": "Tesla ni kampuni ya magari ya umeme kutoka USA, CEO ni Elon Musk.",
    "bitcoin ni nini": "Bitcoin ni pesa ya kidigitali (cryptocurrency) ilianzishwa 2009 na Satoshi Nakamoto.",
    "bitcoin": "Bitcoin ni pesa ya kidigitali ilianzishwa 2009.",
    "meru ni wapi": "Meru iko Eastern Kenya.",
    "meru": "Meru iko Eastern Kenya, mji mkuu ni Meru Town, watu ni Ameru 1.5M.",
    "kenya iko wapi": "Kenya iko East Africa.",
    "kenya": "Kenya iko East Africa, capital ni Nairobi.",
    "embu ni wapi": "Embu iko Eastern Kenya.",
    "siakago ni wapi": "Siakago iko Embu County, Mbeere North, Kenya.",
    "eldoret ni wapi": "Eldoret iko Uasin Gishu County, Rift Valley, Kenya.",
    "nairobi ni wapi": "Nairobi iko Kenya na ndio capital city ya Kenya.",
    "elon musk ni nani": "Elon Musk ni bilionea kutoka USA, CEO wa Tesla na SpaceX.",
    "uhuru kenyatta ni nani": "Uhuru Kenyatta ni Rais wa 4 wa Kenya.",
    "william ruto ni nani": "William Ruto ni Rais wa 5 wa Kenya.",
    "m-pesa ni nini": "M-Pesa ni huduma ya kutuma pesa kwa simu kutoka Safaricom Kenya.",
}

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "RIGAN AI DIRECT", "short_name": "RIGAN",
        "start_url": "/", "display": "standalone",
        "background_color": "#020617", "theme_color": "#38bdf8",
        "icons": [{"src": "https://cdn-icons-png.flaticon.com/512/4712/4712109.png", "sizes": "512x512", "type": "image/png"}]
    })

@app.route('/sw.js')
def sw():
    return "self.addEventListener('install', e => self.skipWaiting());", 200, {'Content-Type': 'application/javascript'}

@app.route('/')
def home():
    return f"""<!DOCTYPE html><html><head>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>RIGAN V58 DIRECT</title>
<link rel="manifest" href="/manifest.json">
<script>if('serviceWorker' in navigator){{navigator.serviceWorker.register('/sw.js')}}</script>
<style>
body{{background:#020617;color:#fff;font-family:sans-serif;display:flex;justify-content:center;height:100vh;margin:0}}
.box{{width:100%;max-width:850px;background:#0f172a;display:flex;flex-direction:column;height:100vh}}
.head{{padding:10px;text-align:center;color:#38bdf8;font-weight:900;background:#1e293b;font-size:13px}} .sub{{font-size:9px;color:#22c55e}}
.direct{{background:#22c55e;color:#000;padding:6px;text-align:center;font-size:10px;font-weight:900}}
.chat{{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px}}
.b{{padding:10px 12px;border-radius:12px;max-width:92%;white-space:pre-wrap;line-height:1.5;font-size:14px}}
.u{{background:#38bdf8;color:#000;align-self:flex-end}} .a{{background:#1e293b;align-self:flex-start;border:1px solid #334155}}
.in{{display:flex;gap:6px;padding:10px;background:#1e293b}}
input{{flex:1;padding:12px;border-radius:12px;border:1px solid #334155;background:#020617;color:#fff;outline:none}}
button{{padding:12px 14px;border-radius:12px;border:none;background:#38bdf8;font-weight:900;cursor:pointer}}
</style></head><body>
<div class='box'>
<div class='head'>RIGAN V58 - DIRECT ANSWER<div class='sub'>Mtoto wa REGAN MARINA | Akili {len(brain["lessons"])} | Majibu Sahihi Hapo Hapo</div></div>
<div class='direct'>✅ DIRECT: Hakuna "karibu" - Jibu sahihi moja kwa moja!</div>
<div class='chat' id='c'><div class='b a'>Uliza swali - Nitajibu moja kwa moja sahihi.

Mfano: Safaricom inapatikana nchi gani?</div></div>
<div class='in'>
<input id='i' placeholder='Uliza swali...' onkeypress="if(event.key=='Enter')s()">
<button onclick='s()'>Tuma</button>
</div>
</div>
<script>
function add(t,c){{let d=document.createElement('div'); d.className='b '+c; d.innerText=t; let chat=document.getElementById('c'); chat.appendChild(d); chat.scrollTop=999999;}}
async function s(){{let e=document.getElementById('i');let v=e.value.trim();if(!v)return; add(v,'u'); e.value=''; let r=await fetch('/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{message:v}})}}); let j=await r.json(); add(j.reply,'a');}}
</script></body></html>
"""

@app.route('/chat', methods=['POST'])
def chat():
    data=request.get_json() or {}
    q=data.get('message','').strip()
    m=q.lower().strip()

    # 1. Tafuta jibu sahihi moja kwa moja
    if m in BASE:
        return jsonify(reply=BASE[m])
    
    for k in BASE:
        if k in m or m in k:
            if len(k) > 2:
                return jsonify(reply=BASE[k])
    
    # 2. Lessons zilizojifunza
    for k in brain["lessons"]:
        if k in m and len(k)>2:
            return jsonify(reply=brain["lessons"][k])

    # 3. Auto learn kutoka internet DIRECT
    direct = get_direct_answer(q)
    if direct:
        return jsonify(reply=direct)

    # 4. Hesabu
    try:
        t=m.replace('x','*').replace('×','*').replace('÷','/'); t2=''.join(c for c in t if c in '0123456789+-*/(). ')
        if len(t2)>=3 and any(c.isdigit() for c in t2) and '**' not in t2:
            r=eval(t2)
            if isinstance(r,float) and r.is_integer(): r=int(r)
            return jsonify(reply=f"{q} = {r}")
    except: pass

    return jsonify(reply=f"Sijapata jibu sahihi la '{q}'. Jaribu: Safaricom inapatikana nchi gani, Meru ni wapi, Tesla ni nini.")

if __name__ == '__main__':
    port=int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
