from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import os
import requests
from dotenv import load_dotenv
import logging
import re
from collections import defaultdict

# Configuración de logs
logging.basicConfig(level=logging.INFO)

# Cargar variables de entorno
load_dotenv()

# Inicializar Flask
app = Flask(__name__)

# Variables de entorno
TWILIO_API_KEY = os.getenv("TWILIO_API_KEY")
OR_API_KEY = os.getenv("OPENROUTER_API_KEY")
OR_BASE_URL = "https://openrouter.ai/api/v1"
BOOKLY_API_BASE = "https://affge.com/bot/wp-json/booklycustom/v1"
BOOKLY_API_KEY = "5bc2aa445c35047edb64414952eb53da"

# Mapeo de servicios a staff_id
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

# Estado de los usuarios
user_states = defaultdict(lambda: {"waiting_for_slot": False, "doctor": None, "date": None, "available_slots": []})

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.form.get("Body", "").strip().lower()
    sender = request.form.get("From")
    state = user_states[sender]
    logging.info(f"📩 Mensaje recibido de {sender}: {incoming_msg}, Estado: {state}")

    if not incoming_msg:
        logging.warning("⚠️ Mensaje vacío recibido")
        twilio_resp = MessagingResponse()
        twilio_resp.message("Por favor, envía un mensaje válido.")
        return str(twilio_resp)

    twilio_resp = MessagingResponse()

    # Si está esperando un horario
    if state["waiting_for_slot"]:
        match = re.match(r"(\d{2}:\d{2}-\d{2}:\d{2})", incoming_msg)
        if match:
            selected_slot = match.group(1)
            # Verificar si el slot sigue disponible
            staff_id = SERVICES[state["service"]]["staff_id"] if "service" in state else state["staff_id"]
            url = f"{BOOKLY_API_BASE}/disponibilidad-doctor-{staff_id}?api_key={BOOKLY_API_KEY}"
            try:
                response = requests.get(url, headers={"Authorization": BOOKLY_API_KEY})
                response.raise_for_status()
                data = response.json()
                current_slots = []
                for day in data:
                    if day["date"] == f"2025-{state['date'].split('/')[1]}-{state['date'].split('/')[0]}":
                        current_slots.extend(day["available_slots"])
                if any(selected_slot == slot["start_date"][11:16] + "-" + slot["end_date"][11:16] for slot in current_slots):
                    reply = f"¡Cita confirmada con {state['doctor']} el {state['date']} a las {selected_slot} (simulación). Gracias!"
                else:
                    reply = f"El horario {selected_slot} ya no está disponible. Por favor, elige otro de: " + "\n".join([f"- {slot['start_date'][11:16]}-{slot['end_date'][11:16]}" for slot in current_slots])
            except Exception as e:
                logging.error(f"❌ Error al verificar disponibilidad: {e}")
                reply = "Error al verificar disponibilidad. Intenta más tarde."
            state["waiting_for_slot"] = False
            state["doctor"] = None
            state["date"] = None
            state["service"] = None
        else:
            reply = "Formato de horario incorrecto. Usa 'HH:MM-HH:MM' (ej. '08:30-09:00')."
        twilio_resp.message(reply)
        return str(twilio_resp)

    # Patrón para detectar "agendar [servicio] el [fecha]"
    match = re.match(r"agendar\s+(.+?)\s+el\s+(\d{1,2}/\d{1,2})", incoming_msg)
    if match:
        service = match.group(1).strip()
        date = match.group(2)

        if service in SERVICES:
            staff_id = SERVICES[service]["staff_id"]
            doctor = SERVICES[service]["doctor"]
            # Consultar horarios disponibles
            url = f"{BOOKLY_API_BASE}/disponibilidad-doctor-{staff_id}?api_key={BOOKLY_API_KEY}"
            try:
                response = requests.get(url, headers={"Authorization": BOOKLY_API_KEY})
                response.raise_for_status()
                data = response.json()
                available_slots = []
                for day in data:
                    if day["date"] == f"2025-{date.split('/')[1]}-{date.split('/')[0]}":
                        available_slots.extend(day["available_slots"])
                if available_slots:
                    slots_text = "\n".join([f"- {slot['start_date'][11:16]}-{slot['end_date'][11:16]}" for slot in available_slots])
                    reply = f"Horarios disponibles con {doctor} el {date}:\n{slots_text}\nPor favor, elige un horario (ej. '08:30-09:00')."
                    state["waiting_for_slot"] = True
                    state["doctor"] = doctor
                    state["date"] = date
                    state["staff_id"] = staff_id
                    state["service"] = service
                    state["available_slots"] = available_slots
                else:
                    reply = f"No hay horarios disponibles con {doctor} el {date}. Intenta otra fecha."
            except Exception as e:
                logging.error(f"❌ Error al consultar Bookly API: {e}")
                reply = "Error al obtener horarios. Intenta más tarde."
        else:
            reply = "Servicio no reconocido. Servicios disponibles:\n" + "\n".join(SERVICES.keys())
    else:
        reply = "Por favor, usa el formato: 'Agendar [servicio] el [dd/mm]' (ej. 'Agendar Pediatría el 15/07')."

    twilio_resp.message(reply)
    return str(twilio_resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
