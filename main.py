from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import os
import requests
from dotenv import load_dotenv
import logging
import re

# Configuración de logs
logging.basicConfig(level=logging.INFO)

# Cargar variables de entorno
load_dotenv()

# Inicializar Flask
app = Flask(__name__)

# Variables de entorno
TWILIO_API_KEY = os.getenv("TWILIO_API_KEY")  # Asegúrate de tener esto en .env
OR_API_KEY = os.getenv("OPENROUTER_API_KEY")
OR_BASE_URL = "https://openrouter.ai/api/v1"
BOOKLY_API_BASE = "https://affge.com/bot/wp-json/booklycustom/v1"
BOOKLY_API_KEY = "5bc2aa445c35047edb64414952eb53da"  # Usa la clave del plugin

# Mapeo de servicios a staff_id (corregido)
SERVICES = {
    "medicina familiar": {"doctor": "Dra. Lizbeth Díaz", "staff_id": 4},
    "diabetología": {"doctor": "Dr. Jhonny Calahorrano", "staff_id": 1},
    "geriatría": {"doctor": "Dr. Jhonny Calahorrano", "staff_id": 1},
    "cuidados paliativos": {"doctor": "Dr. Jhonny Calahorrano", "staff_id": 1},
    "inmunología y reumatología": {"doctor": "Dr. Jhonny Calahorrano", "staff_id": 1},
    "alergología": {"doctor": "Dr. Jhonny Calahorrano", "staff_id": 1},
    "pediatría": {"doctor": "Dra. Lizbeth Díaz", "staff_id": 4},
    "ginecología": {"doctor": "Dra. Lizbeth Díaz", "staff_id": 4},
    "nutrición clínica": {"doctor": "Dra. Lizbeth Díaz", "staff_id": 4},
    "nutrición pediátrica": {"doctor": "Dra. Lizbeth Díaz", "staff_id": 4},
    "cosmetología": {"doctor": "Cosm. Jessica Gavilanes", "staff_id": 3},
    "cosmeatría": {"doctor": "Cosm. Jessica Gavilanes", "staff_id": 3},
    "medicina estética": {"doctor": "Cosm. Jessica Gavilanes", "staff_id": 3}
}

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.form.get("Body", "").strip().lower()
    sender = request.form.get("From")
    logging.info(f"📩 Mensaje recibido de {sender}: {incoming_msg}")

    if not incoming_msg:
        logging.warning("⚠️ Mensaje vacío recibido")
        twilio_resp = MessagingResponse()
        twilio_resp.message("Por favor, envía un mensaje válido.")
        return str(twilio_resp)

    # Patrón para detectar "agendar [servicio] el [fecha]"
    match = re.match(r"agendar\s+(.+?)\s+el\s+(\d{1,2}/\d{1,2})", incoming_msg)
    if match:
        service = match.group(1).strip()
        date = match.group(2)  # Formato dd/mm (ej. 15/07)

        if service in SERVICES:
            staff_id = SERVICES[service]["staff_id"]
            doctor = SERVICES[service]["doctor"]
            # Consultar horarios disponibles
            url = f"{BOOKLY_API_BASE}/disponibilidad-doctor-{staff_id}?api_key={BOOKLY_API_KEY}"
            try:
                response = requests.get(url, headers={"Authorization": BOOKLY_API_KEY})
                response.raise_for_status()
                data = response.json()
                # Filtrar horarios para la fecha solicitada
                available_slots = []
                for day in data:
                    if day["date"] == f"2025-{date.split('/')[1]}-{date.split('/')[0]}":  # Convertir a YYYY-MM-DD
                        available_slots.extend(day["available_slots"])
                if available_slots:
                    slots_text = "\n".join([f"- {slot['start_date'][11:16]}-{slot['end_date'][11:16]}" for slot in available_slots])
                    reply = f"Horarios disponibles con {doctor} el {date}:\n{slots_text}\nPor favor, elige un horario (ej. '08:00-08:30')."
                else:
                    reply = f"No hay horarios disponibles con {doctor} el {date}. Intenta otra fecha."
            except Exception as e:
                logging.error(f"❌ Error al consultar Bookly API: {e}")
                reply = "Error al obtener horarios. Intenta más tarde."
        else:
            reply = "Servicio no reconocido. Servicios disponibles:\n" + "\n".join(SERVICES.keys())
    else:
        reply = "Por favor, usa el formato: 'Agendar [servicio] el [dd/mm]' (ej. 'Agendar Pediatría el 15/07')."

    # Enviar respuesta a WhatsApp
    twilio_resp = MessagingResponse()
    twilio_resp.message(reply)
    return str(twilio_resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
