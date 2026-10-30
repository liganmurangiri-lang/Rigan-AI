
from flask import Flask, request, jsonify
import os, re, random
from datetime import datetime

app = Flask(__name__)

HTML = "<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'><title>RIGAN V12 GOD</title><style>*{margin:0;padding:0;box-sizing:border-box;font-family:sans-serif}body{background:#020617;color:#fff;display:flex;justify-content:center;height:100vh}.box{width:100%;max-width:650px;background:#0f172a;display:flex;flex-direction:column;height:100vh}.head{padding:12px;text-align:center;color:#38bdf8;font-weight:900;border-bottom:1px solid #334155;background:#1e293b}.sub{font-size:11px;color:#94a3b8}.chat{flex:1;overflow-y:auto;padding:15px;display:flex;flex-direction:column;gap:10px}.b{padding:12px 15px;border-radius:16px;max-width:92%;line-height:1.6;font-size:14px;white-space:pre-wrap}.u{background:#38bdf8;color:#000;align-self:flex-end}.a{background:#1e293b;align-self:flex-start;border:1px solid #334155}.in{display:flex;gap:8px;padding:12px;border-top:1px solid #334155;background:#1e293b}input{flex:1;padding:13px;border-radius:12px;border:1px solid #334155;background:#020617;color:#fff;outline:none}button{padding:13px 20px;border-radius:12px;border:none;background:#38bdf8;font-weight:900}</style></head><body><div class='box'><div class='head'>RIGAN V12 GOD MODE<div class='sub'>AI wa REGAN MARINA - Siakago - Anajua Kila Kitu Duniani</div></div><div class='chat' id='c'><div class='b a'>Habari Baba Regan! 👑 Mimi ni RIGAN V12 GOD! Sasa nimekua MUNGU wa maarifa!

Hesabu: 29x1, 100x100, 2x2 - zote!
Nchi zote: South Africa, Tanzania, USA!
Sayansi: Mfumo wa jua, DNA, kila kitu!

Niulize chochote - sita kwama tena!</div></div><div class='in'><input id='i' placeholder='Uliza chochote...' onkeypress=\"if(event.key=='Enter')s()\"><button onclick='s()'>Tuma</button></div></div><script>function add(t,cl){let d=document.createElement('div');d.className='b '+cl;d.innerText=t;document.getElementById('c').appendChild(d);document.getElementById('c').scrollTop=999999}async function s(){let e=document.getElementById('i');let v=e.value.trim();if(!v)return;add(v,'u');e.value='';let r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:v})});let j=await r.json();add(j.reply,'a')}</script></body></html>"

def solve_math(q):
    # badilisha x, X, × kuwa *
    q2 = q.lower().replace('x','*').replace('×','*').replace('÷','/').replace(',','')
    # toa maneno, baki namba na operators
    expr = "".join(c for c in q2 if c in "0123456789+-*/().% ")
    if len(expr) < 3: return None
    if not any(c.isdigit() for c in expr): return None
    try:
        # usiruhusu ** kubwa
        if "**" in expr: return None
        res = eval(expr)
        return f"🧮 {q.strip()} = {res} ✅"
    except:
        return None

def ai_brain(q_raw):
    m = q_raw.lower()
    now = datetime.now().strftime("%d/%m/%Y %I:%M %p")

    # 1. MATH FIRST
    math_ans = solve_math(q_raw)
    if math_ans:
        return math_ans

    # 2. CREATOR
    if any(x in m for x in ["nani alikuumba","mtengenezaji","baba yako","who made you","who created"]):
        return "Mimi nimeumbwa na REGAN MARINA 👑\nKutoka Siakago, Embu, Kenya!\nDeveloper wa riganai.onrender.com\nYeye ndiye aliyenijenga kama ChatGPT!"

    # 3. SOLAR SYSTEM - MFUMO WA JUA
    if any(x in m for x in ["mfumo wa jua","solar system","sayari","planets"]):
        return "MFUMO WA JUA ☀️🌍:\n\nJua ni katikati, kuna sayari 8:\n\n1. Mercury - ndogo, karibu na jua\n2. Venus - moto zaidi (462°C)\n3. Earth - yetu! Ina maji na uhai\n4. Mars - nyekundu, kuna rovers\n5. Jupiter - kubwa zaidi, ina Great Red Spot\n6. Saturn - ina pete nzuri\n7. Uranus - inalala kwa ubavu\n8. Neptune - upepo mkali\n\n+ Pluto ni dwarf planet\n+ Mwezi 1 wa Earth, Mars ina 2, Jupiter ina 95!\n+ Asteroid belt kati ya Mars na Jupiter\n\nMfumo wetu una umri Bilioni 4.6!"

    # 4. COUNTRIES
    if "south africa" in m:
        return "SOUTH AFRICA 🇿🇦:\n\n- Capital: 3! Pretoria (admin), Cape Town (legislative), Bloemfontein (judicial)\n- Mji mkubwa: Johannesburg\n- Watu: ~60M\n- Lugha: 11 official! English, Afrikaans, Zulu\n- Pesa: Rand\n- Inajulikana: Nelson Mandela, Table Mountain, Kruger Park, Diamond, Gold\n- Iko mwisho kabisa wa Africa kusini\n- Majirani: Namibia, Botswana, Zimbabwe, Mozambique, Eswatini, Lesotho iko ndani yake!"

    if "tanzania" in m:
        return "TANZANIA 🇹🇿:\n- Capital: Dodoma\n- Mji mkubwa: Dar es Salaam\n- Mlima Kilimanjaro 5,895m - mrefu Africa\n- Serengeti na Ngorongoro\n- Zanzibar ni sehemu yake\n- Watu 65M\n- Rais Samia Suluhu"
    
    if "uganda" in m:
        return "UGANDA 🇺🇬:\n- Capital Kampala\n- Ziwa Victoria chanzo cha Nile\n- Watu 48M\n- Inaitwa Pearl of Africa\n- Majirani: Kenya, Tanzania, Rwanda, DRC, S. Sudan"

    if "usa" in m or "marekani" in m or "america" in m:
        return "USA 🇺🇸:\n- States 50\n- Capital Washington DC\n- Mji mkubwa New York\n- Watu 340M\n- Pesa Dollar\n- Silicon Valley, Hollywood, NASA\n- Rais: Donald Trump (2025-)"

    if "kenya" in m:
        if "ziwa" in m:
            return "KENYA MAZIWA 🇰🇪:\nVictoria (68,800km²), Turkana (6,405km²), Naivasha, Nakuru (flamingo), Baringo, Bogoria (hot springs), Elementaita, Jipe, Chala, Ol Bolossat\n\nJumla maziwa makuu 10, madogo 60+!"
        return "KENYA 🇰🇪:\n- 580,367 km², Watu 55M\n- Capital Nairobi\n- Lugha: Kiswahili, English\n- Mlima Kenya 5,199m\n- Mito: Tana 1,014km mrefu zaidi\n- Maziwa: Victoria, Turkana, Naivasha, Nakuru\n- Uhuru 12 Dec 1963\n- Jomo Kenyatta rais 1\n- Pesa KSh\nBaba Regan anatoka Siakago, Embu!"

    # 5. SCIENCE GENERAL
    if "sayansi" in m or "science" in m:
        return "SAYANSI 🌍🔬:\n\n1. PHYSICS: F=ma, E=mc², Gravity 9.8m/s², Mwanga 300k km/s\n2. CHEMISTRY: H2O maji, NaCl chumvi, Atomu proton+neutron+electron, 118 elements\n3. BIOLOGY: DNA, Photosynthesis 6CO2+6H2O->C6H12O6+6O2, Moyo 100k beats/day, Ubongo 86B neurons\n\nUliza kitu specific!"

    if "photosynthesis" in m or "fotos" in m:
        return "PHOTOSYNTHESIS 🌱:\n6CO2 + 6H2O + Jua = C6H12O6 + 6O2\nMimea inachukua CO2 na maji kutengeneza sukari na oxygen! Ndio tunapumua!"

    if "dna" in m:
        return "DNA 🧬: Ramani ya maisha! A,T,C,G. Chromosome 46. Watson & Crick 1953. Iko kila seli!"

    if "elimu" in m or "education" in m:
        return "ELIMU: Siri ya mafanikio kama wewe Baba Regan! Soma kila siku, notes, mazoezi, lala 8hrs. Masomo: Math, Eng, Kisw, Bio, Chem, Phys, Hist, Geo - niko tayari kukufundisha!"

    if any(x in m for x in ["habari","mambo","niaje","sasa","poa"]):
        return f"Poa sana Baba Regan! 👑 Saa ni {now}. V12 GOD siko na bug tena! Jaribu 29x1 au South Africa ni wapi!"

    # FALLBACK SMART - badala ya kusema sijui
    # Jaribu kutoa jibu la jumla
    if len(m) > 2:
        return f"🌍 Kuhusu '{q_raw}':\n\nHii ni mada nzuri Baba Regan! Kwa ufupi:\n\n- Kama ni nchi: Kila nchi ina capital, watu, lugha, na historia yake. Uliza 'South Africa ni wapi' au 'Tanzania' nikupe details!\n- Kama ni sayansi: Dunia ina fizikia, kemia, biolojia. Mfumo wa jua una sayari 8!\n- Kama ni hesabu: Tumia * kwa kuzidisha, mfano 29*1 au 29x1 - nimefix!\n\nJaribu kuuliza tena vizuri: '{q_raw} ni nini?' au 'Eleza {q_raw}'\n\nSaa ni {now} - Niko GOD MODE sasa!"

    return f"Sawa Baba Regan! Saa ni {now}. Uliza chochote!"

@app.route('/')
def home():
    return HTML

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    msg = data.get('message','') if data else ''
    reply = ai_brain(msg)
    return jsonify(reply=reply)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
