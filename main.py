from flask import Flask, request, jsonify
import requests, os, json, threading, time
from groq import Groq
import librouteros
from librouteros import connect
from librouteros.query import Key

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
    "Eres un asistente experto en MikroTik RouterOS para un ISP. "
    "Conoces toda la documentacion oficial de MikroTik wiki. "
    "La red tiene: IP publica 202.78.170.14, tuneles IPIP hacia "
    "152.206.118.19, 152.206.177.49, 181.225.255.106 y GRE hacia "
    "200.55.147.237, 152.206.201.65, WireGuard con Cloudflare y Surfshark, "
    "firewall con bloqueo de torrents y P2P, DNS con NextDNS y DoH, "
    "API en puerto 13589, SSH en puerto 3025, Winbox en puerto 58291. "
    "Puedes gestionar: firewall, rutas, interfaces, tuneles, usuarios, "
    "DHCP, DNS, QoS, bandwidth, PPPoE, Hotspot, VPN, scripts, scheduler, "
    "logs, certificados, y cualquier funcion de RouterOS. "
    "Responde SIEMPRE en espanol. Se claro, preciso y profesional. "
    "Para acciones en el router usa el formato exacto al final: "
    "MK_ACTION: {\"path\": \"/ruta/api\", \"cmd\": \"comando\", \"params\": {}}"
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

def mk_conectar():
    return connect(
        host=MK_HOST,
        username=MK_USER,
        password=MK_PASS,
        port=MK_PORT,
        timeout=15
    )

def mk_ejecutar(path, cmd="print", params=None):
    try:
        api = mk_conectar()
        ruta = path + "/" + cmd
        if params:
            resultado = list(api(ruta, **params))
        else:
            resultado = list(api(ruta))
        api.close()
        return resultado
    except Exception as e:
        return [{"error": str(e)}]

def mk_datos_red():
    try:
        api = mk_conectar()
        recursos = list(api("/system/resource/print"))
        interfaces = list(api("/interface/print"))
        arp = list(api("/ip/arp/print"))
        rutas = list(api("/ip/route/print"))
        api.close()
        return {
            "recursos": recursos,
            "interfaces": interfaces[:15],
            "clientes_arp": arp[:20],
            "rutas": rutas[:10]
        }
    except Exception as e:
        return {"error": str(e)}

def preguntar_ia(pregunta):
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": CONTEXTO_RED},
            {"role": "user", "content": pregunta}
        ],
        max_tokens=1500
    )
    return resp.choices[0].message.content

def procesar_mensaje(texto, chat_id):
    global pendiente

    if texto in ["/start", "/inicio"]:
        enviar_telegram(
            "Sistema IA MikroTik activo.\n\n"
            "Comandos rapidos:\n"
            "/estado - Estado general\n"
            "/tuneles - Estado de tuneles\n"
            "/clientes - Clientes conectados\n"
            "/firewall - Reglas de firewall\n"
            "/rutas - Tabla de rutas\n"
            "/analizar - Analisis completo\n"
            "/recursos - CPU y memoria\n"
            "/dns - Configuracion DNS\n"
            "/usuarios - Usuarios del sistema\n\n"
            "O escribe cualquier orden en espanol.\n"
            "Ejemplos:\n"
            "- bloquea la ip 1.2.3.4\n"
            "- muestra el ancho de banda por interfaz\n"
            "- agrega una ruta estatica\n"
            "- reinicia la interfaz ether1\n"
            "- crea un usuario nuevo\n"
            "- analiza mi firewall y sugiere mejoras",
            chat_id
        )
        return

    if texto.lower() in ["si", "sí", "confirmar", "confirmo", "ejecutar"]:
        if chat_id in pendiente:
            accion = pendiente[chat_id]
            enviar_telegram("Ejecutando en el router...", chat_id)
            resultado = mk_ejecutar(
                accion.get("path", "/system/resource"),
                accion.get("cmd", "print"),
                accion.get("params", None)
            )
            texto_resultado = json.dumps(resultado[:5], indent=2, ensure_ascii=False)
            respuesta = preguntar_ia("Interpreta este resultado del router en espanol simple: " + texto_resultado)
            enviar_telegram(respuesta, chat_id)
            del pendiente[chat_id]
        else:
            enviar_telegram("No hay ninguna accion pendiente.", chat_id)
        return

    if texto.lower() in ["no", "cancelar"]:
        if chat_id in pendiente:
            del pendiente[chat_id]
            enviar_telegram("Accion cancelada. No se hizo ningun cambio.", chat_id)
        else:
            enviar_telegram("No hay ninguna accion pendiente.", chat_id)
        return

    if texto == "/recursos":
        enviar_telegram("Consultando recursos...", chat_id)
        datos = mk_ejecutar("/system/resource")
        respuesta = preguntar_ia("Analiza estos recursos del router y dame resumen: " + json.dumps(datos))
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/estado":
        enviar_telegram("Consultando estado completo...", chat_id)
        datos = mk_datos_red()
        respuesta = preguntar_ia(
            "Analiza estos datos reales del router ISP y dame un resumen completo del estado: " +
            json.dumps(datos)
        )
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/tuneles":
        enviar_telegram("Analizando tuneles...", chat_id)
        datos = mk_ejecutar("/interface")
        respuesta = preguntar_ia(
            "Analiza el estado de los tuneles IPIP, GRE y WireGuard en estos datos: " +
            json.dumps(datos)
        )
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/clientes":
        enviar_telegram("Consultando clientes...", chat_id)
        datos = mk_ejecutar("/ip/arp")
        respuesta = preguntar_ia(
            "Lista y analiza estos clientes conectados. Identifica IPs sospechosas: " +
            json.dumps(datos)
        )
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/firewall":
        enviar_telegram("Consultando firewall...", chat_id)
        datos = mk_ejecutar("/ip/firewall/filter")
        respuesta = preguntar_ia(
            "Analiza estas reglas de firewall del ISP y dame resumen con sugerencias: " +
            json.dumps(datos[:20])
        )
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/rutas":
        enviar_telegram("Consultando rutas...", chat_id)
        datos = mk_ejecutar("/ip/route")
        respuesta = preguntar_ia(
            "Analiza la tabla de rutas de este ISP MikroTik: " +
            json.dumps(datos[:15])
        )
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/dns":
        enviar_telegram("Consultando DNS...", chat_id)
        datos = mk_ejecutar("/ip/dns")
        respuesta = preguntar_ia(
            "Analiza la configuracion DNS de este router y sugiere mejoras: " +
            json.dumps(datos)
        )
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/usuarios":
        enviar_telegram("Consultando usuarios...", chat_id)
        datos = mk_ejecutar("/user")
        respuesta = preguntar_ia(
            "Analiza los usuarios del sistema MikroTik y detecta posibles problemas de seguridad: " +
            json.dumps(datos)
        )
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/analizar":
        enviar_telegram("Analizando red completa, espera un momento...", chat_id)
        datos = mk_datos_red()
        firewall = mk_ejecutar("/ip/firewall/filter")
        dns = mk_ejecutar("/ip/dns")
        datos["firewall"] = firewall[:15]
        datos["dns"] = dns
        respuesta = preguntar_ia(
            "Haz un analisis profesional completo de esta red ISP MikroTik basado en datos reales:\n" +
            json.dumps(datos) +
            "\n\nIncluye:\n"
            "1. Estado actual de la red\n"
            "2. Problemas detectados\n"
            "3. Vulnerabilidades de seguridad\n"
            "4. Mejoras recomendadas segun wiki oficial de MikroTik\n"
            "5. Optimizaciones de rendimiento para ISP"
        )
        enviar_telegram(respuesta, chat_id)
        return

    enviar_telegram("Procesando tu orden...", chat_id)
    respuesta_ia = preguntar_ia(
        "El usuario de un ISP MikroTik pide: " + texto + "\n\n"
        "1. Explica que vas a hacer\n"
        "2. Dame el comando o accion necesaria\n"
        "3. Si requiere ejecutar algo en el router, al final agrega EXACTAMENTE:\n"
        "MK_ACTION: {\"path\": \"/ruta/api\", \"cmd\": \"add o set o remove o print\", \"params\": {\"parametro\": \"valor\"}}\n"
        "Ejemplos de paths validos:\n"
        "/ip/firewall/filter, /ip/address, /interface, /ip/route,\n"
        "/user, /ip/dns, /system/reboot, /ip/dhcp-server/lease,\n"
        "/queue/simple, /ip/firewall/address-list\n"
        "Si solo es informacion no agregues MK_ACTION."
    )

    if "MK_ACTION:" in respuesta_ia:
        partes = respuesta_ia.split("MK_ACTION:")
        explicacion = partes[0].strip()
        try:
            accion_str = partes[1].strip().split("\n")[0].strip()
            accion = json.loads(accion_str)
            pendiente[chat_id] = accion
            enviar_telegram(explicacion, chat_id)
            enviar_telegram(
                "Accion a ejecutar en el router:\n"
                "Ruta: " + accion.get("path", "") + "\n"
                "Comando: " + accion.get("cmd", "") + "\n"
                "Parametros: " + json.dumps(accion.get("params", {}), ensure_ascii=False) +
                "\n\nEscribe SI para confirmar o NO para cancelar.",
                chat_id
            )
        except Exception:
            enviar_telegram(respuesta_ia, chat_id)
    else:
        enviar_telegram(respuesta_ia, chat_id)

def leer_telegram():
    offset = 0
    enviar_telegram(
        "Sistema IA MikroTik iniciado.\n"
        "Escribe /inicio para ver todos los comandos disponibles."
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

@app.route("/monitor", methods=["POST"])
def monitor():
    datos = request.json or {}
    cpu = datos.get("cpu", "0")
    mem = datos.get("mem", "0")
    uptime = datos.get("uptime", "")
    try:
        cpu_val = int(str(cpu).replace("%", ""))
        if cpu_val > 80:
            enviar_telegram(
                "ALERTA CRITICA: CPU al " + str(cpu) +
                "% en el router\nUptime: " + str(uptime)
            )
        elif cpu_val > 60:
            enviar_telegram("Aviso: CPU elevada al " + str(cpu) + "%")
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
