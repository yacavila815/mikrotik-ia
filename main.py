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

client = Groq(api_key=GROQ_API_KEY)

CONTEXTO_RED = (
    "Eres experto en redes MikroTik RouterOS para un ISP. "
    "La red tiene IP publica 202.78.170.14, tuneles IPIP hacia "
    "152.206.118.19, 152.206.177.49, 181.225.255.106 y GRE hacia "
    "200.55.147.237, 152.206.201.65, WireGuard con Cloudflare y Surfshark, "
    "firewall con bloqueo de torrents y P2P, DNS con NextDNS y DoH activo. "
    "REST API activa en puerto 443. SSH en puerto 3025. Winbox en puerto 58291. "
    "Responde SIEMPRE en espanol. Se claro y directo. "
    "Cuando des comandos RouterOS ponlos entre comillas invertidas triples."
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

def mk_get(path):
    try:
        url = "https://" + MK_HOST + "/rest" + path
        resp = requests.get(
            url,
            auth=(MK_USER, MK_PASS),
            verify=False,
            timeout=10
        )
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def mk_post(path, data):
    try:
        url = "https://" + MK_HOST + "/rest" + path
        resp = requests.post(
            url,
            auth=(MK_USER, MK_PASS),
            json=data,
            verify=False,
            timeout=10
        )
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def mk_cmd(path):
    try:
        url = "https://" + MK_HOST + "/rest" + path
        resp = requests.post(
            url,
            auth=(MK_USER, MK_PASS),
            verify=False,
            timeout=10
        )
        if resp.text:
            return resp.json()
        return {"resultado": "Ejecutado correctamente"}
    except Exception as e:
        return {"error": str(e)}

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
            "/firewall - Reglas de firewall\n"
            "/analizar - Analisis completo\n"
            "/recursos - CPU y memoria\n\n"
            "O escribe cualquier orden en espanol.\n"
            "La IA te dira que va a hacer y pedira tu confirmacion antes de ejecutar.",
            chat_id
        )
        return

    if texto.lower() in ["si", "sí", "confirmar", "confirmo", "ok", "ejecutar"]:
        if chat_id in pendiente:
            accion = pendiente[chat_id]
            enviar_telegram("Ejecutando en el router...", chat_id)
            resultado = mk_cmd(accion["path"])
            enviar_telegram("Resultado:\n" + json.dumps(resultado, indent=2, ensure_ascii=False)[:1000], chat_id)
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

    if texto == "/recursos":
        datos = mk_get("/system/resource")
        respuesta = preguntar_ia("Analiza estos recursos del router y dame un resumen claro: " + json.dumps(datos))
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/estado":
        enviar_telegram("Consultando estado de la red...", chat_id)
        recursos = mk_get("/system/resource")
        interfaces = mk_get("/interface")
        datos = "Recursos: " + json.dumps(recursos) + "\nInterfaces: " + json.dumps(interfaces[:8])
        respuesta = preguntar_ia("Analiza estos datos del router ISP y dame un resumen del estado general: " + datos)
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/tuneles":
        enviar_telegram("Analizando tuneles...", chat_id)
        interfaces = mk_get("/interface")
        tuneles = [i for i in interfaces if isinstance(i, dict) and i.get("type") in ["ipip", "gre", "wireguard"]]
        respuesta = preguntar_ia("Analiza el estado de estos tuneles IPIP, GRE y WireGuard y dame un resumen: " + json.dumps(tuneles))
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/clientes":
        enviar_telegram("Consultando clientes conectados...", chat_id)
        arp = mk_get("/ip/arp")
        respuesta = preguntar_ia("Lista y analiza estos clientes conectados al router ISP. Identifica IPs sospechosas o inusuales: " + json.dumps(arp))
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/firewall":
        enviar_telegram("Consultando reglas de firewall...", chat_id)
        reglas = mk_get("/ip/firewall/filter")
        respuesta = preguntar_ia("Analiza estas reglas de firewall de este ISP MikroTik y dame un resumen con sugerencias de mejora: " + json.dumps(reglas[:15]))
        enviar_telegram(respuesta, chat_id)
        return

    if texto == "/analizar":
        enviar_telegram("Analizando red completa, espera un momento...", chat_id)
        recursos = mk_get("/system/resource")
        interfaces = mk_get("/interface")
        arp = mk_get("/ip/arp")
        firewall = mk_get("/ip/firewall/filter")
        rutas = mk_get("/ip/route")
        datos = (
            "Recursos: " + json.dumps(recursos) +
            "\nInterfaces: " + json.dumps(interfaces[:10]) +
            "\nClientes ARP: " + json.dumps(arp[:10]) +
            "\nFirewall: " + json.dumps(firewall[:10]) +
            "\nRutas: " + json.dumps(rutas[:10])
        )
        respuesta = preguntar_ia(
            "Haz un analisis completo y profesional de esta red ISP MikroTik basado en datos reales: " +
            datos +
            "\nIdentifica: 1) Problemas actuales 2) Vulnerabilidades de seguridad "
            "3) Mejoras recomendadas segun documentacion oficial de MikroTik "
            "4) Optimizaciones de rendimiento"
        )
        enviar_telegram(respuesta, chat_id)
        return

    enviar_telegram("Analizando tu orden...", chat_id)
    respuesta_ia = preguntar_ia(
        texto + "\n\n"
        "Si esta orden requiere ejecutar una accion en el router MikroTik via REST API, "
        "al final de tu respuesta agrega exactamente esta linea:\n"
        "REST_PATH: /la/ruta/rest/del/comando\n"
        "Ejemplos de rutas REST validas:\n"
        "/ip/firewall/filter/add para agregar regla\n"
        "/ip/address para ver IPs\n"
        "/interface para ver interfaces\n"
        "/system/reboot para reiniciar\n"
        "Si solo es informacion, no agregues REST_PATH."
    )

    if "REST_PATH:" in respuesta_ia:
        partes = respuesta_ia.split("REST_PATH:")
        explicacion = partes[0].strip()
        path = partes[1].strip().split("\n")[0].strip()
        pendiente[chat_id] = {"path": path, "orden": texto}
        enviar_telegram(explicacion, chat_id)
        enviar_telegram(
            "Accion a ejecutar en el router:\n" + path +
            "\n\nEscribe SI para confirmar o NO para cancelar.",
            chat_id
        )
    else:
        enviar_telegram(respuesta_ia, chat_id)

def leer_telegram():
    offset = 0
    enviar_telegram("Sistema IA MikroTik iniciado correctamente.\nEscribe /inicio para ver los comandos disponibles.")
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
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    t = threading.Thread(target=leer_telegram, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
