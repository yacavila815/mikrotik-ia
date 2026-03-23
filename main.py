from flask import Flask, request, jsonify
import requests, os, json
from groq import Groq

app = Flask(__name__)

GROQ_KEY   = os.environ.get("GROQ_KEY")
TG_TOKEN   = os.environ.get("TG_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")

client = Groq(api_key=GROQ_KEY)

def alerta_telegram(msg):
    if TG_TOKEN and TG_CHAT_ID:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TG_CHAT_ID, "text": msg})

def preguntar_ia(contexto, pregunta):
    resp = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "system", "content": "Eres experto en redes MikroTik RouterOS. Analiza datos y responde SIEMPRE en español. Si hay problemas, dilo claramente."},
            {"role": "user", "content": f"Contexto: {contexto}\n\nPregunta: {pregunta}"}
        ],
        max_tokens=500
    )
    return resp.choices[0].message.content

@app.route("/monitor", methods=["POST"])
def monitor():
    datos = request.json or {}
    analisis = preguntar_ia(json.dumps(datos), "Analiza estas métricas de red. ¿Hay algo anormal o alguna alerta?")
    palabras_alerta = ["alerta", "problema", "caída", "alto", "crítico", "error"]
    if any(p in analisis.lower() for p in palabras_alerta):
        alerta_telegram(f"🔴 ALERTA RED:\n{analisis}")
    else:
        alerta_telegram(f"✅ Red estable:\n{analisis}")
    return jsonify({"ok": True, "analisis": analisis})

@app.route("/orden", methods=["POST"])
def orden():
    texto = request.json.get("texto", "") if request.json else ""
    respuesta = preguntar_ia("Sistema MikroTik RouterOS", f"El usuario pide: {texto}. Dame el comando RouterOS exacto.")
    alerta_telegram(f"📋 Orden: {texto}\n\nIA responde:\n{respuesta}")
    return jsonify({"respuesta": respuesta})

@app.route("/ping")
def ping():
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
```

- Baja hasta el final → clic en **"Commit changes"** → **"Commit changes"** (el botón verde)

---

**3. Crear requirements.txt**

Mismo proceso → **"Add file"** → **"Create new file"**
- Nombre: `requirements.txt`
- Contenido:
```
flask
groq
requests
```
- Clic en **"Commit changes"**

---

**4. Crear Procfile**

Mismo proceso → **"Add file"** → **"Create new file"**
- Nombre: `Procfile` (exactamente así, con P mayúscula, sin extensión)
- Contenido:
```
web: python main.py
