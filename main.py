from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import os
import requests
from dotenv import load_dotenv
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta

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
user_states = defaultdict(lambda: {"waiting_for_slot": False, "doctor": None, "date": None, "staff_id": None, "service": None})

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
            staff_id = state["staff_id"]
            url = f"{BOOKLY_API_BASE}/disponibilidad-doctor-{staff_id}?api_key={BOOKLY_API_KEY}"
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                logging.info(f"📅 Datos de API para verificación: {data}")
                current_slots = []
                target_date = f"2025-{state['date'].split('/')[1]}-{state['date'].split('/')[0]}"
                for day in data:
                    if day["date"] == target_date:
                        current_slots.extend(day["available_slots"])
                selected_slot_full = f"{target_date} {selected_slot[:5]}:00"
                if any(slot["start_date"] == selected_slot_full for slot in current_slots):
                    reply = f"¡Cita confirmada con {state['doctor']} el {state['date']} a las {selected_slot} (simulación). Gracias!"
                else:
                    slots_text = "\n".join([f"- {slot['start_date'][11:16]}-{slot['end_date'][11:16]}" for slot in current_slots])
                    reply = f"El horario {selected_slot} ya no está disponible. Elige otro de:\n{slots_text}"
            except requests.RequestException as e:
                logging.error(f"❌ Error al verificar disponibilidad: {e}")
                reply = "Error al verificar disponibilidad. Intenta más tarde."
            except Exception as e:
                logging.error(f"❌ Error inesperado: {e}")
                reply = "Error interno. Contacta al soporte."
            state["waiting_for_slot"] = False
            state["doctor"] = None
            state["date"] = None
            state["staff_id"] = None
            state["service"] = None
        else:
            reply = "Formato de horario incorrecto. Usa 'HH:MM-HH:MM' (ej. '08:30-09:00')."
        twilio_resp.message(reply)
        return str(twilio_resp)

    # Patrón para detectar "agendar [servicio] el [fecha]"
    match = re.match(r"agendar\s+(.+?)\s+el\s+(\d{1,2}/\d{1,2})", incoming_msg)
    if match:
        service = match.group(1).strip()
        date_str = match.group(2)
        try:
            day, month = map(int, date_str.split('/'))
            today = datetime(2025, 7, 10)  # Fecha actual según el sistema
            target_date = datetime(2025, month, day)
            max_date = today + timedelta(days=14)
            if target_date < today or target_date > max_date:
                reply = f"Fecha inválida. Elige una fecha entre {today.strftime('%d/%m')} y {max_date.strftime('%d/%m')}."
            elif service in SERVICES:
                staff_id = SERVICES[service]["staff_id"]
                doctor = SERVICES[service]["doctor"]
                url = f"{BOOKLY_API_BASE}/disponibilidad-doctor-{staff_id}?api_key={BOOKLY_API_KEY}"
                try:
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    logging.info(f"📅 Datos de API iniciales: {data}")
                    available_slots = []
                    target_date_str = target_date.strftime("%Y-%m-%d")
                    for day in data:
                        if day["date"] == target_date_str:
                            available_slots.extend(day["available_slots"])
                    if available_slots:
                        slots_text = "\n".join([f"- {slot['start_date'][11:16]}-{slot['end_date'][11:16]}" for slot in available_slots])
                        note = "(Solo 08:00-12:00)" if target_date.weekday() == 6 else ""  # Domingo
                        reply = f"Horarios disponibles con {doctor} el {date_str} {note}:\n{slots_text}\nElige un horario (ej. '08:30-09:00')."
                        state["waiting_for_slot"] = True
                        state["doctor"] = doctor
                        state["date"] = date_str
                        state["staff_id"] = staff_id
                        state["service"] = service
                    else:
                        reply = f"No hay horarios disponibles con {doctor} el {date_str}. Intenta otra fecha."
                except requests.RequestException as e:
                    logging.error(f"❌ Error al consultar Bookly API: {e}")
                    reply = "Error al obtener horarios. Intenta más tarde."
            else:
                reply = "Servicio no reconocido. Servicios disponibles:\n" + "\n".join(SERVICES.keys())
        except ValueError:
            reply = "Formato de fecha incorrecto. Usa 'dd/mm' (ej. '15/07')."
    else:
        reply = "Por favor, usa el formato: 'Agendar [servicio] el [dd/mm]' (ej. 'Agendar Pediatría el 15/07')."

    twilio_resp.message(reply)
    return str(twilio_resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
