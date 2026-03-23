from flask import Flask, request, jsonify
import requests, os, json, threading, time
from groq import Groq
import socket

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
TG_TOKEN     = os.environ.get("TG_TOKEN")
TG_CHAT_ID   = os.environ.get("TG_CHAT_ID")
MK_HOST      = os.environ.get("MK_HOST", "202.78.170.14")
MK_USER      = os.environ.get("MK_USER", "ia-bot")
MK_PASS      = os.environ.get("MK_PASS", "IaBot2026Secure!")
MK_PORT      = int(os.environ.get("MK_PORT", "13589"))

client = Groq(api_key=GROQ_API_KEY)

CONTEXTO_RED = """
Eres un experto en redes MikroTik RouterOS para un ISP pequeño.
La red tiene:
- Router principal CHR con IP publica 202.78.170.14
- Tuneles IPIP hacia clientes: 118.19, 177.49, 255.106
- Tuneles GRE: 147.237, 201.65
- WireGuard: Cloudflare (3 interfaces), Surfshark (3 interfaces), SERVER para clientes
- Firewall con bloqueo de torrents y P2P
- API activa en puerto 13589
- SSH en puerto 3025
- Winbox en puerto 58291
- DNS con NextDNS y DoH activo
Responde SIEMPRE en español. Se claro, directo y profesional.
Cuando des comandos RouterOS ponlos entre ``` para que se vean claramente.
"""

def enviar_telegram(msg, chat_id=None):
    if not TG_TOKEN:
        return
    cid = chat_id or TG_CHAT_ID
    url = "https://api.telegram.org/bot" + TG_TOKEN + "/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": cid,
            "text": msg,
            "parse_mode": "Markdown"
        }, timeout=10)
    except:
        pass

def ejecutar_en_mikrotik(comando):
    try:
        import librouteros
        api = librouteros.connect(
            host=MK_HOST,
            username=MK_USER,
            password=MK_PASS,
            port=MK_PORT
        )
        partes = comando.strip("/").split(" ")
        path = "/" + "/".join(partes[:-1])
        cmd = partes[-1]
        resultado = list(api(path + "/" + cmd))
        api.close()
        return str(resultado[:5])
    except Exception as e:
        return "Error conectando al router: " + str(e)

def preguntar_ia(pregunta, historial=[]):
    mensajes = [{"role": "system", "content": CONTEXTO_RED}]
    for h in historial[-6:]:
        mensajes.append(h)
    mensajes.append({"role": "user", "content": pregunta})
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=mensajes,
        max_tokens=1000
    )
    return resp.choices[0].message.content

historial_chat = []

def procesar_mensaje(texto, chat_id):
    global historial_chat
    texto_lower = texto.lower()

    if texto == "/start" or texto == "/inicio":
        enviar_telegram(
            "*Sistema IA MikroTik activo*\n\n"
            "Puedes pedirme:\n"
            "- Ver dispositivos conectados\n"
            "- Bloquear una IP\n"
            "- Ver estado de tuneles\n"
            "- Analizar la red\n"
            "- Ejecutar cualquier comando\n\n"
            "Escribe tu orden en español y la proceso.", chat_id)
        return

    if texto == "/estado":
        enviar_telegram("Consultando estado de la red...", chat_id)
        resultado = ejecutar_en_mikrotik("/interface print")
        respuesta = preguntar_ia(
            "Analiza estas interfaces y dame un resumen del estado: " + resultado)
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/tuneles":
        enviar_telegram("Verificando tuneles...", chat_id)
        resultado = ejecutar_en_mikrotik("/interface print")
        respuesta = preguntar_ia(
            "Analiza el estado de los tuneles IPIP, GRE y WireGuard: " + resultado)
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/clientes":
        enviar_telegram("Consultando clientes conectados...", chat_id)
        resultado = ejecutar_en_mikrotik("/ip arp print")
        respuesta = preguntar_ia(
            "Lista y analiza los clientes conectados: " + resultado)
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/analizar":
        enviar_telegram("Analizando red completa, espera un momento...", chat_id)
        respuesta = preguntar_ia(
            "Haz un analisis completo de esta red ISP basandote en la configuracion que conoces. "
            "Identifica posibles problemas, vulnerabilidades y sugerencias de mejora segun "
            "las mejores practicas de MikroTik RouterOS.")
        enviar_telegram(respuesta, chat_id)
        return

    enviar_telegram("Procesando tu orden...", chat_id)
    historial_chat.append({"role": "user", "content": texto})
    respuesta = preguntar_ia(texto, historial_chat)
    historial_chat.append({"role": "assistant", "content": respuesta})
    if len(historial_chat) > 20:
        historial_chat = historial_chat[-20:]
    enviar_telegram(respuesta, chat_id)

def leer_telegram():
    offset = 0
    enviar_telegram(
        "*Sistema IA MikroTik iniciado*\n"
        "Escribe /inicio para ver los comandos disponibles.")
    while True:
        try:
            url = ("https://api.telegram.org/bot" + TG_TOKEN +
                   "/getUpdates?offset=" + str(offset) + "&timeout=30")
            resp = requests.get(url, timeout=35)
            data = resp.json()
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                texto = msg.get("text", "")
                if texto and chat_id == TG_CHAT_ID:
                    threading.Thread(
                        target=procesar_mensaje,
                        args=(texto, chat_id),
                        daemon=True
                    ).start()
        except Exception as e:
            time.sleep(5)

@app.route("/monitor", methods=["POST"])
def monitor():
    datos = request.json or {}
    cpu = int(str(datos.get("cpu", "0")).replace("%", ""))
    mem = datos.get("mem", "0")
    uptime = datos.get("uptime", "?")
    if cpu > 80:
        enviar_telegram(
            "*ALERTA CRITICA*\nCPU al " + str(cpu) +
            "% en tu router MikroTik\nUptime: " + str(uptime))
    elif cpu > 60:
        enviar_telegram(
            "*ALERTA*\nCPU elevada al " + str(cpu) + "%")
    return jsonify({"ok": True})

@app.route("/ping")
def ping():
    return "ok"

if __name__ == "__main__":
    t = threading.Thread(target=leer_telegram, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
```

→ Clic en **"Commit changes"** → **"Commit changes"**

---

Luego agrega esta variable en Railway → Variables:

| Nombre | Valor |
|---|---|
| `MK_HOST` | `202.78.170.14` |
| `MK_PORT` | `13589` |

---

También necesitamos agregar `librouteros` al requirements.txt.

**En GitHub → requirements.txt → lápiz ✏️**

Borra todo y pega:
```
flask
groq
requests
librouteros
```

→ Commit changes

---

Espera 2 minutos que Railway reinicie y escríbele a tu bot en Telegram:
```
/inicio
