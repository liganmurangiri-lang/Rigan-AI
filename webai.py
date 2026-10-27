from flask import Flask, request, render_template_string, session
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get("RIGAN_SECRET", "badilisha-secret-hii")

PAGE = """
<!doctype html>
<html lang="sw">
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta charset="utf-8">
<title>RIGAN AI - Marima V3</title>
<style>
body { background:#101522; color:white; font-family:Arial;
       max-width:600px; margin:25px auto; padding:15px; }
h2 { color:#55e6c1; }
#chat { background:#202a3b; padding:15px; border-radius:12px;
        min-height:220px; }
input { box-sizing:border-box; width:100%; padding:14px;
        margin:8px 0; border-radius:8px; }
button { padding:13px; background:#55e6c1; border:0;
         border-radius:8px; width:100%; font-weight:bold; }
</style>
</head>
<body>
<h2>🤖 RIGAN AI - Marima V3</h2>
<p>Karibu! Mimi ni Rigan AI yako.</p>
<div id="chat">
{% for m in messages %}
<p><b>{{ m[0] }}:</b> {{ m[1] }}</p>
{% endfor %}
</div>
<form method="post">
<input name="jina" placeholder="Jina lako" value="{{ jina }}">
<input name="ujumbe" placeholder="Andika ujumbe wako..." required>
<button type="submit">Tuma ujumbe</button>
</form>
</body>
</html>
"""

def jibu(ujumbe, jina):
    s = ujumbe.lower()
    if s in ["toka", "exit", "bye", "lala"]:
        return f"Baadaye {jina}! Tutaonana tena."
    if "habari" in s:
        return f"Poa sana {jina}! Marima mambo?"
    if "saa" in s:
        return "Saa ni " + datetime.now().strftime("%H:%M")
    if "wewe ni nani" in s:
        return "Mimi ni Rigan AI V3, niliyetengenezwa na wewe!"
    if "joke" in s or "vichekesho" in s:
        return "Mwalimu: Kwa nini umechelewa? Mwanafunzi: Barabara ilikuwa ndefu!"
    return f"Nimekuelewa {jina}. Umesema: {ujumbe}"

@app.route("/", methods=["GET", "POST"])
def nyumbani():
    jina = session.get("jina", "")
    messages = session.get("messages", [])
    if request.method == "POST":
        jina = request.form.get("jina", "").strip() or jina or "Rafiki"
        ujumbe = request.form.get("ujumbe", "").strip()
        session["jina"] = jina
        if ujumbe:
            messages.append(("Wewe", ujumbe))
            messages.append(("Rigan", jibu(ujumbe, jina)))
            session["messages"] = messages[-30:]
    return render_template_string(PAGE, jina=jina, messages=messages)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# 1. Kuunganisha Database ya SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///webai.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 2. Kutengeneza Jedwali (Model) la Database
class Ujumbe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    maudhui = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f'<Ujumbe {self.id}>'

# Kuhakikisha database inatengenezwa kabla ya app kuanza
with app.app_context():
    db.create_all()

# 3. Njia (Routes) za App yako
@app.route('/')
def index():
    # Kuchukua jumbe zote kutoka kwenye database
    jumbe_zote = Ujumbe.query.all()
    return f"<h1>Karibu kwenye WebAI!</h1><p>Jumbe zilizopo kwenye database ziko {len(jumbe_zote)}.</p>"

@app.route('/ongeza', methods=['POST'])
def ongeza():
    tekst = request.form.get('ujumbe')
    if tekst:
        mpya = Ujumbe(maudhui=tekst)
        db.session.add(mpya)
        db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

