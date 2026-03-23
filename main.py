from flask import Flask, request, jsonify
import requests, os, json, threading, time
from groq import Groq

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
TG_TOKEN     = os.environ.get("TG_TOKEN")
TG_CHAT_ID   = os.environ.get("TG_CHAT_ID")
MK_HOST      = os.environ.get("MK_HOST", "202.78.170.14")
MK_USER      = os.environ.get("MK_USER", "ia-bot")
MK_PASS      = os.environ.get("MK_PASS", "IaBot2026")
MK_PORT      = int(os.environ.get("MK_PORT", "13589"))

client = Groq(api_key=GROQ_API_KEY)

CONTEXTO_RED = (
    "Eres experto en redes MikroTik RouterOS para un ISP. "
    "Conoces toda la documentacion oficial de MikroTik. "
    "La red tiene: IP publica 202.78.170.14, tuneles IPIP hacia "
    "152.206.118.19, 152.206.177.49, 181.225.255.106 y GRE hacia "
    "200.55.147.237, 152.206.201.65, WireGuard con Cloudflare y Surfshark, "
    "firewall con bloqueo de torrents y P2P, DNS con NextDNS y DoH. "
    "API en puerto 13589, SSH en puerto 3025, Winbox en puerto 58291. "
    "Responde SIEMPRE en espanol. Se claro y profesional."
)

datos_red = {}
pendiente = {}
cola_comandos = []

def enviar_telegram(msg, chat_id=None):
    if not TG_TOKEN:
        return
    cid = chat_id or TG_CHAT_ID
    url = "https://api.telegram.org/bot" + TG_TOKEN + "/sendMessage"
    try:
        requests.post(url, json={"chat_id": cid, "text": msg}, timeout=10)
    except Exception:
        pass

def mk_ejecutar_via_fetch(comando_routeros):
    try:
        url = "https://web-production-14c6d.up.railway.app/cmd"
        cola_comandos.append({"cmd": comando_routeros, "ts": time.time()})
        return "Comando enviado al router. Espera la confirmacion."
    except Exception as e:
        return "Error: " + str(e)

def preguntar_ia(pregunta, contexto_datos=""):
    contenido = CONTEXTO_RED
    if contexto_datos:
        contenido += "\n\nDatos actuales de la red:\n" + contexto_datos
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": contenido},
            {"role": "user", "content": pregunta}
        ],
        max_tokens=1500
    )
    return resp.choices[0].message.content

def get_datos_actuales():
    if not datos_red:
        return "No hay datos del router todavia. Espera 30 segundos."
    return json.dumps(datos_red, ensure_ascii=False)

def procesar_mensaje(texto, chat_id):
    global pendiente, cola_comandos

    if texto in ["/start", "/inicio"]:
        enviar_telegram(
            "Sistema IA MikroTik activo.\n\n"
            "Comandos disponibles:\n"
            "/estado - Estado general de la red\n"
            "/clientes - Dispositivos conectados\n"
            "/interfaces - Estado de interfaces\n"
            "/tuneles - Estado de tuneles\n"
            "/analizar - Analisis completo\n"
            "/recursos - CPU y memoria\n\n"
            "O escribe cualquier orden en espanol.\n"
            "Ejemplos:\n"
            "- bloquea la ip 1.2.3.4\n"
            "- muestra el uso de cpu\n"
            "- hay algun problema en la red\n"
            "- analiza mis clientes conectados",
            chat_id
        )
        return

    if texto.lower() in ["si", "sí", "confirmar", "confirmo", "ejecutar"]:
        if chat_id in pendiente:
            accion = pendiente[chat_id]
            cmd = accion.get("cmd", "")
            enviar_telegram("Enviando comando al router:\n" + cmd, chat_id)
            cola_comandos.append({"cmd": cmd, "ts": time.time()})
            enviar_telegram("Comando en cola. El router lo ejecutara en el proximo ciclo de 30 segundos.", chat_id)
            del pendiente[chat_id]
        else:
            enviar_telegram("No hay ninguna accion pendiente.", chat_id)
        return

    if texto.lower() in ["no", "cancelar"]:
        if chat_id in pendiente:
            del pendiente[chat_id]
            enviar_telegram("Accion cancelada.", chat_id)
        else:
            enviar_telegram("No hay ninguna accion pendiente.", chat_id)
        return

    if texto == "/recursos":
        datos = get_datos_actuales()
        respuesta = preguntar_ia("Dame un resumen de CPU, memoria y uptime del router.", datos)
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/estado":
        datos = get_datos_actuales()
        respuesta = preguntar_ia(
            "Dame un resumen completo del estado actual de la red ISP "
            "incluyendo interfaces, clientes y recursos.", datos)
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/clientes":
        datos = get_datos_actuales()
        respuesta = preguntar_ia(
            "Lista y analiza todos los clientes conectados actualmente. "
            "Identifica IPs sospechosas o inusuales.", datos)
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/interfaces":
        datos = get_datos_actuales()
        respuesta = preguntar_ia(
            "Muestra el estado de todas las interfaces del router. "
            "Indica cuales estan activas y cuales caidas.", datos)
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/tuneles":
        datos = get_datos_actuales()
        respuesta = preguntar_ia(
            "Analiza el estado de los tuneles IPIP, GRE y WireGuard. "
            "Indica cuales estan activos y si hay alguno caido.", datos)
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/analizar":
        enviar_telegram("Analizando red completa...", chat_id)
        datos = get_datos_actuales()
        respuesta = preguntar_ia(
            "Haz un analisis profesional completo de esta red ISP. "
            "Incluye: estado actual, problemas detectados, "
            "vulnerabilidades de seguridad y mejoras recomendadas "
            "segun la documentacion oficial de MikroTik.", datos)
        enviar_telegram(respuesta, chat_id)
        return

    enviar_telegram("Procesando tu orden...", chat_id)
    datos = get_datos_actuales()
    respuesta_ia = preguntar_ia(
        "El administrador del ISP pide: " + texto + "\n\n"
        "1. Explica que vas a hacer\n"
        "2. Si requiere ejecutar un comando RouterOS en el router, "
        "al final agrega EXACTAMENTE esta linea:\n"
        "MK_CMD: /comando/routeros/completo\n"
        "Ejemplos de comandos validos:\n"
        "/ip firewall filter add chain=input src-address=1.2.3.4 action=drop\n"
        "/ip address add address=192.168.1.1/24 interface=ether2\n"
        "/interface set ether1 disabled=yes\n"
        "/ip dhcp-server lease remove [find address=192.168.1.50]\n"
        "Si solo es informacion no agregues MK_CMD.",
        datos
    )

    if "MK_CMD:" in respuesta_ia:
        partes = respuesta_ia.split("MK_CMD:")
        explicacion = partes[0].strip()
        cmd = partes[1].strip().split("\n")[0].strip()
        pendiente[chat_id] = {"cmd": cmd}
        enviar_telegram(explicacion, chat_id)
        enviar_telegram(
            "Comando a ejecutar en el router:\n" + cmd +
            "\n\nEscribe SI para confirmar o NO para cancelar.",
            chat_id
        )
    else:
        enviar_telegram(respuesta_ia, chat_id)

def leer_telegram():
    offset = 0
    enviar_telegram(
        "Sistema IA MikroTik iniciado.\n"
        "Escribe /inicio para ver los comandos disponibles."
    )
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

@app.route("/datos", methods=["POST"])
def recibir_datos():
    global datos_red, cola_comandos
    try:
        datos_red = request.json or {}
        datos_red["ultima_actualizacion"] = time.strftime("%Y-%m-%d %H:%M:%S")
        cpu = int(str(datos_red.get("cpu", "0")).replace("%", ""))
        if cpu > 80:
            enviar_telegram("ALERTA: CPU al " + str(cpu) + "% en el router")
        if cola_comandos:
            cmd_pendiente = cola_comandos.pop(0)
            edad = time.time() - cmd_pendiente.get("ts", 0)
            if edad < 300:
                return jsonify({"ok": True, "ejecutar": cmd_pendiente["cmd"]})
    except Exception:
        pass
    return jsonify({"ok": True, "ejecutar": ""})

@app.route("/monitor", methods=["POST"])
def monitor():
    return recibir_datos()

@app.route("/ping")
def ping():
    return "ok"

if __name__ == "__main__":
    t = threading.Thread(target=leer_telegram, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
