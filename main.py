from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import os
import requests
from dotenv import load_dotenv
import logging

# Configura logging
logging.basicConfig(filename='app.log', level=logging.INFO)

load_dotenv()
app = Flask(__name__)

OR_API_KEY = os.getenv("OPENROUTER_API_KEY")
WP_URL = os.getenv("WORDPRESS_URL")
OR_BASE_URL = "https://openrouter.ai/api/v1"

# Lista de servicios disponibles (hardcoded para Amelia Lite)
SERVICES = [
    "Medicina Familiar (Dr. Jhonny Calahorrano)",
    "Diabetología (Dr. Jhonny Calahorrano)",
    "Geriatría (Dr. Jhonny Calahorrano)",
    "Cuidados Paliativos (Dr. Jhonny Calahorrano)",
    "Inmunología y Reumatología (Dr. Jhonny Calahorrano)",
    "Alergología (Dr. Jhonny Calahorrano)"
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

    headers = {
        "Authorization": f"Bearer {OR_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": f"{WP_URL}",
        "X-Title": "Asistente Médico"
    }

    # Preparar lista de servicios para el prompt
    service_list = "\n".join([f"- {service}" for service in SERVICES])
    booking_url = f"{WP_URL}/reservas"

    payload = {
        "model": "openrouter/cypher-alpha:free",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres un asistente médico que ayuda a agendar citas de manera amable, clara y profesional. "
                    "No puedes crear citas directamente, así que redirige a los usuarios al formulario de reservas. "
                    "Pide detalles como servicio, fecha y hora si no los proporcionan. "
                    "No almacenes datos personales sensibles. "
                    f"Servicios disponibles:\n{service_list}\n"
                    f"Formulario de reservas: {booking_url}"
                )
            },
            {"role": "user", "content": incoming_msg}
        ],
        "max_tokens": 150
    }

    try:
        response = requests.post(f"{OR_BASE_URL}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        reply = data["choices"][0]["message"]["content"].strip()
        logging.info(f"✅ Respuesta de OpenRouter: {reply}")
    except Exception as e:
        logging.error(f"❌ Error con OpenRouter: {e}")
        if 'response' in locals():
            logging.error(f"📨 Respuesta del servidor: {response.text}")
        reply = "Lo siento, hubo un error con el bot. Intenta más tarde."

    twilio_resp = MessagingResponse()
    twilio_resp.message(reply)
    return str(twilio_resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))