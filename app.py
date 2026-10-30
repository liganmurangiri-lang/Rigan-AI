
from flask import Flask, request, jsonify
import os, json
from datetime import datetime, timedelta

app = Flask(__name__)

DB_FILE = "akili.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_db(db):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except:
        pass

learned = load_db()

HTML = """
<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>RIGAN V16</title>
<style>*{margin:0;padding:0;box-sizing:border-box;font-family:sans-serif}
body{background:#020617;color:#fff;display:flex;justify-content:center;height:100vh}
.box{width:100%;max-width:680px;background:#0f172a;display:flex;flex-direction:column;height:100vh}
.head{padding:12px;text-align:center;color:#38bdf8;font-weight:900;background:#1e293b}
.sub{font-size:10px;color:#94a3b8}
.chat{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px}
.b{padding:11px 14px;border-radius:14px;max-width:93%;line-height:1.6;white-space:pre-wrap;font-size:14px}
.u{background:#38bdf8;color:#000;align-self:flex-end}
.a{background:#1e293b;align-self:flex-start;border:1px solid #334155}
.in{display:flex;gap:6px;padding:10px;background:#1e293b}
input{flex:1;padding:12px;border-radius:10px;border:1px solid #334155;background:#020617;color:#fff;outline:none}
button{padding:12px 16px;border-radius:10px;border:none;background:#38bdf8;font-weight:900}
</style></head><body>
<div class='box'>
<div class='head'>RIGAN V16 ULTIMATE<div class='sub'>Mtoto wa REGAN MARINA - Siakago - Kenya Yote + Dunia</div></div>
<div class='chat' id='c'><div class='b a'>Habari Baba Regan! V16 ULTIMATE iko LIVE! Najua Meru, Embu, Siakago, Nairobi, Dunia yote! Uliza chochote!</div></div>
<div class='in'><input id='i' placeholder='Uliza...' onkeypress="if(event.key=='Enter')s()"><button onclick='s()'>Tuma</button></div>
</div>
<script>
function add(t,cl){let d=document.createElement('div');d.className='b '+cl;d.innerText=t;let c=document.getElementById('c');c.appendChild(d);c.scrollTop=999999}
async function s(){let e=document.getElementById('i');let v=e.value.trim();if(!v)return;add(v,'u');e.value='';let r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:v})});let j=await r.json();add(j.reply,'a')}
</script></body></html>
"""

def math_solve(q):
    try:
        t = q.lower().replace('x','*').replace('X','*').replace('×','*').replace('÷','/').replace(',','').replace('=','')
        t2 = ''.join(c for c in t if c in '0123456789+-*/().% ')
        if len(t2) >= 3 and any(c.isdigit() for c in t2) and '**' not in t2:
            r = eval(t2)
            if isinstance(r, float) and r.is_integer():
                r = int(r)
            return f"{q.strip()} = {r}"
    except:
        return None

def get_answer(q):
    global learned
    m = q.lower().strip()
    nairobi_time = (datetime.utcnow() + timedelta(hours=3)).strftime("%d/%m/%Y %I:%M %p EAT")

    if (m.startswith("fundisha:") or m.startswith("jifunze:")) and "|" in q:
        try:
            clean = q.split(":",1)[1].strip()
            swali, jibu = clean.split("|", 1)
            swali = swali.strip().lower()
            jibu = jibu.strip()
            if len(swali) > 2 and len(jibu) > 2:
                learned[swali] = jibu
                save_db(learned)
                return f"✅ Nimejifunza! Swali: {swali} | Jibu: {jibu} | Total: {len(learned)}"
        except:
            pass

    if m in ["habari","habar","jambo","mambo","niaje","sasa","poa","freshi","hello","hi","hey"]:
        return f"Habari Baba Regan! Poa sana! Mimi niko fiti! Saa ni {nairobi_time}. Uliza chochote!"
    
    if any(x in m for x in ["wewe ni nani","nani wewe","who are you","jina lako nani","unaitwa nani"]):
        return f"👑 Mimi ni RIGAN V16 ULTIMATE! Mtoto wa REGAN MARINA kutoka Siakago, Embu, Kenya! Developer wa riganai.onrender.com! Najua hesabu, miji yote Kenya, nchi zote! Saa ni {nairobi_time}"

    if any(x in m for x in ["saa yako ni mbaya","saa mbaya","time wrong"]):
        return f"Samahani Baba! 🙏 Sasa nimefix timezone! Saa sahihi Nairobi ni: {nairobi_time} - EAT UTC+3"

    ms = math_solve(q)
    if ms:
        return ms

    for key in learned:
        if key in m and len(key) > 3:
            return f"{learned[key]}"

    if "meru" in m:
        return f"MERU 🇰🇪:\n• County ya Meru, Eastern Kenya\n• Mji: Meru Town\n• Watu: ~1.5M\n• Maarufu: Miraa, Mlima Kenya, chai, kahawa\n• Jirani: Isiolo, Tharaka Nithi, Embu\nSaa ni {nairobi_time}"
    if "embu" in m:
        return f"EMBU 🇰🇪:\n• County ya Embu, kwenu Baba Regan!\n• Mji: Embu Town\n• Watu: ~600k\n• Kahawa, chai, macadamia\n• Siakago ni town kubwa Embu!\nSaa ni {nairobi_time}"
    if "siakago" in m:
        return f"SIAKAGO 🇰🇪:\n• Town kubwa Embu County, Mbeere North\n• Kwenu Baba REGAN MARINA! 👑\n• Barabara Embu-Thika\n• Miraa, mahindi\nSaa ni {nairobi_time}"
    if "nairobi" in m:
        return f"NAIROBI 🇰🇪: Capital ya Kenya, 4.5M, Green City in the Sun, KICC, National Park. Saa {nairobi_time}"
    if "mombasa" in m:
        return f"MOMBASA 🇰🇪: Mji wa pili, pwani, 1.2M, Port kubwa East Africa, Fort Jesus"
    if "kisumu" in m:
        return f"KISUMU 🇰🇪: Kando ya Ziwa Victoria, 400k, Luo community"
    if "nakuru" in m:
        return f"NAKURU 🇰🇪: Rift Valley, Ziwa Nakuru flamingo, Menengai Crater"

    if any(x in m for x in ["kenya iko wapi","kenya inapatikana wapi","kenya iko sehemu gani","kenya location"]):
        return f"KENYA IKO WAPI? 🇰🇪🌍:\n• EAST AFRICA, katikati ya Africa\n• Majirani: Tanzania, Uganda, Ethiopia, Somalia, South Sudan\n• Pwani: Indian Ocean 536km\n• Eneo: 580,367 km²\n• Capital Nairobi\n• Timezone EAT UTC+3 - Saa ni {nairobi_time}"

    if 'south africa' in m: return "SOUTH AFRICA 🇿🇦: Capital Pretoria/Cape Town/Bloemfontein, Johannesburg kubwa, 60M, Rand, Mandela, Table Mountain"
    if 'tanzania' in m: return "TANZANIA 🇹🇿: Dodoma capital, Dar kubwa, Kilimanjaro 5,895m, Serengeti, Zanzibar, 65M"
    if 'uganda' in m: return "UGANDA 🇺🇬: Kampala capital, Pearl of Africa, Ziwa Victoria, 48M"
    if 'ethiopia' in m: return "ETHIOPIA 🇪🇹: Addis Ababa, 120M, Lalibela, Coffee origin"
    if 'rwanda' in m: return "RWANDA 🇷🇼: Kigali, 13M, Land of 1000 Hills"
    if 'usa' in m or 'marekani' in m or 'america' in m: return "USA 🇺🇸: 50 States, Washington DC, New York kubwa, 340M, Dollar"
    if 'mfumo wa jua' in m or 'solar' in m or 'sayari' in m: return "MFUMO WA JUA ☀️: Jua katikati, sayari 8 - Mercury, Venus, Earth, Mars, Jupiter kubwa, Saturn pete, Uranus, Neptune"
    if 'sayansi' in m or 'science' in m: return "SAYANSI 🔬: Physics F=ma E=mc2, Chemistry H2O 118 elements, Biology DNA Photosynthesis"
    if 'jibu' in m and len(m) < 6: return "Ndio Baba! Niulize swali lolote - Meru, Embu, Siakago, hesabu, nchi!"
    if 'fundisha' in m and '|' not in m: return "Andika hivi: fundisha: swali | jibu"

    return f"Poa Baba! Uliuliza '{q}' - Najua miji yote Kenya, nchi zote, hesabu zote! Saa ni {nairobi_time}"

@app.route('/')
def home(): return HTML

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    msg = data.get('message','') if data else ''
    return jsonify(reply=get_answer(msg))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
