from flask import Flask, request, jsonify
import requests, os, json, threading, time
from groq import Groq
import librouteros

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
TG_TOKEN     = os.environ.get("TG_TOKEN")
TG_CHAT_ID   = os.environ.get("TG_CHAT_ID")
MK_HOST      = os.environ.get("MK_HOST", "202.78.170.14")
MK_USER      = os.environ.get("MK_USER", "ia-bot")
MK_PASS      = os.environ.get("MK_PASS", "IaBot2026Secure!")
MK_PORT      = int(os.environ.get("MK_PORT", "13589"))

client = Groq(api_key=GROQ_API_KEY)

CONTEXTO_RED = (
    "Eres experto en redes MikroTik RouterOS para un ISP. "
    "La red tiene IP publica 202.78.170.14, tuneles IPIP hacia "
    "152.206.118.19, 152.206.177.49, 181.225.255.106 y GRE hacia "
    "200.55.147.237, 152.206.201.65, WireGuard con Cloudflare y Surfshark, "
    "firewall con bloqueo de torrents y P2P, DNS con NextDNS y DoH activo. "
    "API activa en puerto 13589. SSH en puerto 3025. Winbox en puerto 58291. "
    "Responde SIEMPRE en espanol. Cuando des comandos RouterOS ponlos entre "
    "comillas invertidas triples. Se claro y directo."
)

pendiente = {}

def enviar_telegram(msg, chat_id=None):
    if not TG_TOKEN:
        return
    cid = chat_id or TG_CHAT_ID
    url = "https://api.telegram.org/bot" + TG_TOKEN + "/sendMessage"
    try:
        requests.post(url, json={"chat_id": cid, "text": msg}, timeout=10)
    except Exception:
        pass

def conectar_mikrotik():
    return librouteros.connect(
        host=MK_HOST,
        username=MK_USER,
        password=MK_PASS,
        port=MK_PORT
    )

def ejecutar_comando(comando):
    try:
        api = conectar_mikrotik()
        partes = comando.strip().strip("/").split(" ")
        path = "/" + "/".join(partes[:-1])
        cmd = partes[-1]
        resultado = list(api(path + "/" + cmd))
        api.close()
        if resultado:
            return str(resultado[:10])
        return "Comando ejecutado correctamente."
    except Exception as e:
        return "Error al ejecutar: " + str(e)

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
    global pendiente

    if texto in ["/start", "/inicio"]:
        enviar_telegram(
            "Sistema IA MikroTik activo.\n\n"
            "Comandos rapidos:\n"
            "/estado - Estado de la red\n"
            "/tuneles - Estado de tuneles\n"
            "/clientes - Clientes conectados\n"
            "/analizar - Analisis completo\n"
            "/firewall - Ver reglas de firewall\n\n"
            "O escribe cualquier orden en espanol.\n"
            "La IA te dira que va a hacer y te pedira confirmacion antes de ejecutar.",
            chat_id
        )
        return

    if texto.lower() in ["si", "si", "confirmar", "confirmo", "ok", "ejecutar"]:
        if chat_id in pendiente:
            orden_pendiente = pendiente[chat_id]
            enviar_telegram("Ejecutando en el router...", chat_id)
            resultado = ejecutar_comando(orden_pendiente["comando"])
            enviar_telegram("Resultado:\n" + resultado, chat_id)
            del pendiente[chat_id]
        else:
            enviar_telegram("No hay ninguna accion pendiente de confirmar.", chat_id)
        return

    if texto.lower() in ["no", "cancelar", "cancel"]:
        if chat_id in pendiente:
            del pendiente[chat_id]
            enviar_telegram("Accion cancelada. No se hizo ningun cambio en el router.", chat_id)
        else:
            enviar_telegram("No hay ninguna accion pendiente.", chat_id)
        return

    if texto == "/estado":
        enviar_telegram("Consultando estado...", chat_id)
        try:
            api = conectar_mikrotik()
            recursos = list(api("/system/resource/print"))
            interfaces = list(api("/interface/print"))
            api.close()
            info = "Recursos: " + str(recursos[:2]) + "\nInterfaces: " + str(interfaces[:5])
            respuesta = preguntar_ia("Analiza estos datos del router y dame un resumen: " + info)
        except Exception as e:
            respuesta = preguntar_ia("Dame un resumen del estado esperado de esta red ISP MikroTik")
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/tuneles":
        enviar_telegram("Analizando tuneles...", chat_id)
        try:
            api = conectar_mikrotik()
            interfaces = list(api("/interface/print"))
            api.close()
            info = str(interfaces)
            respuesta = preguntar_ia("Analiza el estado de los tuneles IPIP, GRE y WireGuard en estos datos: " + info)
        except Exception as e:
            respuesta = preguntar_ia("Explica como verificar tuneles IPIP, GRE y WireGuard en MikroTik RouterOS")
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/clientes":
        enviar_telegram("Consultando clientes conectados...", chat_id)
        try:
            api = conectar_mikrotik()
            arp = list(api("/ip/arp/print"))
            api.close()
            respuesta = preguntar_ia("Lista y analiza estos clientes conectados al router ISP: " + str(arp))
        except Exception as e:
            respuesta = preguntar_ia("Como ver clientes conectados en MikroTik RouterOS para un ISP")
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/firewall":
        enviar_telegram("Consultando reglas de firewall...", chat_id)
        try:
            api = conectar_mikrotik()
            reglas = list(api("/ip/firewall/filter/print"))
            api.close()
            respuesta = preguntar_ia("Analiza estas reglas de firewall y dame un resumen: " + str(reglas[:10]))
        except Exception as e:
            respuesta = preguntar_ia("Analiza el firewall de esta red ISP MikroTik con bloqueo de torrents y P2P y sugiere mejoras")
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/analizar":
        enviar_telegram("Analizando red completa, espera un momento...", chat_id)
        try:
            api = conectar_mikrotik()
            recursos = list(api("/system/resource/print"))
            interfaces = list(api("/interface/print"))
            firewall = list(api("/ip/firewall/filter/print"))
            api.close()
            datos = "Recursos: " + str(recursos) + "\nInterfaces: " + str(interfaces[:10]) + "\nFirewall: " + str(firewall[:10])
            respuesta = preguntar_ia(
                "Haz un analisis completo de esta red ISP MikroTik basado en estos datos reales: " + datos +
                ". Identifica problemas, vulnerabilidades y mejoras segun mejores practicas de MikroTik."
            )
        except Exception as e:
            respuesta = preguntar_ia(
                "Haz un analisis completo de esta red ISP MikroTik con IP publica 202.78.170.14, "
                "tuneles IPIP y GRE, WireGuard con Cloudflare y Surfshark, firewall con bloqueo "
                "de torrents. Identifica problemas y mejoras segun mejores practicas de MikroTik."
            )
        enviar_telegram(respuesta, chat_id)
        return

    enviar_telegram("Analizando tu orden...", chat_id)
    respuesta_ia = preguntar_ia(
        texto + "\n\nSi esta orden requiere ejecutar un comando en el router, "
        "al final de tu respuesta agrega una linea que diga exactamente:\n"
        "COMANDO_ROUTEROS: /el/comando/a/ejecutar\n"
        "Si no requiere ejecutar nada, no agregues esa linea."
    )

    if "COMANDO_ROUTEROS:" in respuesta_ia:
        partes = respuesta_ia.split("COMANDO_ROUTEROS:")
        explicacion = partes[0].strip()
        comando = partes[1].strip().split("\n")[0].strip()
        pendiente[chat_id] = {"comando": comando, "orden": texto}
        enviar_telegram(explicacion, chat_id)
        enviar_telegram(
            "Comando a ejecutar en tu router:\n" + comando +
            "\n\nEscribe SI para confirmar o NO para cancelar.",
            chat_id
        )
    else:
        enviar_telegram(respuesta_ia, chat_id)

def leer_telegram():
    offset = 0
    enviar_telegram("Sistema IA MikroTik iniciado. Escribe /inicio para ver los comandos.")
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
