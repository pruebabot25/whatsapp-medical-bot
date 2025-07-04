from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import os
import requests
from dotenv import load_dotenv
import logging

# Configuración de logs
logging.basicConfig(level=logging.INFO)

# Cargar variables de entorno desde .env (si estás local) o Render
load_dotenv()

# Inicializar Flask
app = Flask(__name__)

# Variables de entorno
OR_API_KEY = os.getenv("OPENROUTER_API_KEY")
OR_BASE_URL = "https://openrouter.ai/api/v1"

# 🔍 Logs para depuración de variables
logging.info(f"🔍 OPENROUTER_API_KEY cargada: {bool(OR_API_KEY)}")

# Lista de servicios médicos
SERVICES = [
    "Medicina Familiar (Dr. Jhonny Calahorrano)",
    "Diabetología (Dr. Jhonny Calahorrano)",
    "Geriatría (Dr. Jhonny Calahorrano)",
    "Cuidados Paliativos (Dr. Jhonny Calahorrano)",
    "Inmunología y Reumatología (Dr. Jhonny Calahorrano)",
    "Alergología (Dr. Jhonny Calahorrano)",
    "Pediatría (Dra. Lizbeth Díaz)",
    "Ginecología (Dra. Lizbeth Díaz)",
    "Nutrición Clínica (Dra. Lizbeth Díaz)",
    "Nutrición Pediátrica (Dra. Lizbeth Díaz)",
    "Cosmetología (Cosm. Jessica Gavilanes)",
    "Cosmeatría (Cosm. Jessica Gavilanes)",
    "Medicina Estética (Cosm. Jessica Gavilanes)"
]

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.form.get("Body", "").strip()
    sender = request.form.get("From")
    logging.info(f"📩 Mensaje recibido de {sender}: {incoming_msg}")

    if not incoming_msg:
        logging.warning("⚠️ Mensaje vacío recibido")
        twilio_resp = MessagingResponse()
        twilio_resp.message("Por favor, envía un mensaje válido.")
        return str(twilio_resp)

    # Verificar que la clave esté presente
    if not OR_API_KEY:
        logging.error("❌ OPENROUTER_API_KEY no está configurada")
        twilio_resp = MessagingResponse()
        twilio_resp.message("Error de configuración del bot. Contacta al administrador.")
        return str(twilio_resp)

    # Cabeceras para OpenRouter (sin HTTP-Referer)
    headers = {
        "Authorization": f"Bearer {OR_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "Asistente Médico"
    }

    # Construcción del mensaje para el sistema (sin booking_url)
    service_list = "\n".join([f"- {service}" for service in SERVICES])

    payload = {
        "model": "openrouter/cypher-alpha:free",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres un asistente médico que ayuda a agendar citas médicas de manera amable, clara y profesional.\n"
                    "No puedes agendar directamente, pero puedes dar orientación.\n"
                    "Pide al usuario que indique el servicio, fecha y hora deseados.\n"
                    f"Servicios disponibles:\n{service_list}"
                )
            },
            {"role": "user", "content": incoming_msg}
        ],
        "max_tokens": 300
    }

    try:
        logging.info("🚀 Enviando solicitud a OpenRouter...")
        response = requests.post(f"{OR_BASE_URL}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        reply = data["choices"][0]["message"]["content"].strip()
        logging.info(f"✅ Respuesta del bot: {reply}")
    except Exception as e:
        logging.error(f"❌ Error con OpenRouter: {e}")
        if 'response' in locals():
            logging.error(f"📨 Respuesta del servidor: {response.text}")
        reply = "Lo siento, hubo un problema. Intenta más tarde."

    # Enviar respuesta a WhatsApp
    twilio_resp = MessagingResponse()
    twilio_resp.message(reply)
    return str(twilio_resp)

# Ejecutar la app en Render
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
