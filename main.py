from flask import Flask, request, jsonify
import requests, os, json, threading, time
from groq import Groq

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
TG_TOKEN     = os.environ.get("TG_TOKEN")
TG_CHAT_ID   = os.environ.get("TG_CHAT_ID")
MK_HOST      = os.environ.get("MK_HOST", "202.78.170.14")
MK_USER      = os.environ.get("MK_USER", "ia-bot")
MK_PASS      = os.environ.get("MK_PASS", "IaBot2026Secure!")
MK_PORT      = int(os.environ.get("MK_PORT", "13589"))

client = Groq(api_key=GROQ_API_KEY)

CONTEXTO_RED = "Eres experto en redes MikroTik RouterOS para un ISP. La red tiene IP publica 202.78.170.14, tuneles IPIP hacia 152.206.118.19, 152.206.177.49, 181.225.255.106 y GRE hacia 200.55.147.237, 152.206.201.65, WireGuard con Cloudflare y Surfshark, firewall con bloqueo de torrents y P2P, DNS con NextDNS y DoH activo. Responde SIEMPRE en español. Cuando des comandos RouterOS ponlos entre comillas invertidas."

def enviar_telegram(msg, chat_id=None):
    if not TG_TOKEN:
        return
    cid = chat_id or TG_CHAT_ID
    url = "https://api.telegram.org/bot" + TG_TOKEN + "/sendMessage"
    try:
        requests.post(url, json={"chat_id": cid, "text": msg}, timeout=10)
    except Exception:
        pass

def preguntar_ia(pregunta):
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": CONTEXTO_RED},
            {"role": "user", "content": pregunta}
        ],
        max_tokens=1000
    )
    return resp.choices[0].message.content

def procesar_mensaje(texto, chat_id):
    if texto in ["/start", "/inicio"]:
        enviar_telegram(
            "Sistema IA MikroTik activo.\n\n"
            "Comandos disponibles:\n"
            "/estado - Ver estado de la red\n"
            "/tuneles - Ver estado de tuneles\n"
            "/clientes - Ver clientes conectados\n"
            "/analizar - Analisis completo de la red\n\n"
            "O escribe cualquier orden en espanol y la proceso.",
            chat_id
        )
        return

    if texto == "/estado":
        enviar_telegram("Consultando estado de la red...", chat_id)
        respuesta = preguntar_ia("Dame un resumen del estado general de la red ISP con IP publica 202.78.170.14 y sus tuneles activos")
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/tuneles":
        enviar_telegram("Analizando tuneles...", chat_id)
        respuesta = preguntar_ia("Analiza los tuneles IPIP y GRE de esta red. Dame su estado esperado y como verificarlos desde RouterOS")
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/clientes":
        enviar_telegram("Consultando clientes...", chat_id)
        respuesta = preguntar_ia("Lista los clientes conocidos de esta red ISP y como verificar su conectividad desde MikroTik RouterOS")
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/analizar":
        enviar_telegram("Analizando red completa, espera un momento...", chat_id)
        respuesta = preguntar_ia(
            "Haz un analisis completo de esta red ISP MikroTik. "
            "Identifica posibles problemas, vulnerabilidades y mejoras "
            "segun las mejores practicas de MikroTik RouterOS y documentacion oficial."
        )
        enviar_telegram(respuesta, chat_id)
        return

    enviar_telegram("Procesando tu orden...", chat_id)
    respuesta = preguntar_ia(texto)
    enviar_telegram(respuesta, chat_id)

def leer_telegram():
    offset = 0
    enviar_telegram("Sistema IA MikroTik iniciado correctamente. Escribe /inicio para ver los comandos disponibles.")
    while True:
        try:
            url = "https://api.telegram.org/bot" + TG_TOKEN + "/getUpdates?offset=" + str(offset) + "&timeout=30"
            resp = requests.get(url, timeout=35)
            data = resp.json()
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                texto = msg.get("text", "")
                if texto and chat_id == TG_CHAT_ID:
                    threading.Thread(target=procesar_mensaje, args=(texto, chat_id), daemon=True).start()
        except Exception:
            time.sleep(5)

@app.route("/monitor", methods=["POST"])
def monitor():
    datos = request.json or {}
    cpu = datos.get("cpu", "0")
    try:
        if int(str(cpu).replace("%", "")) > 80:
            enviar_telegram("ALERTA: CPU al " + str(cpu) + "% en tu router MikroTik")
    except Exception:
        pass
    return jsonify({"ok": True})

@app.route("/ping")
def ping():
    return "ok"

if __name__ == "__main__":
    t = threading.Thread(target=leer_telegram, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
