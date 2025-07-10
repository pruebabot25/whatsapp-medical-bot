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
user_states = defaultdict(lambda: {"step": "start", "service": None, "doctor": None, "staff_id": None, "date": None})

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

    # Flujo guiado por pasos
    if state["step"] == "start":
        reply = "¡Hola! ¿Te gustaría agendar una cita? Responde con 'sí' para continuar."
        state["step"] = "service_select"
    elif state["step"] == "service_select":
        if incoming_msg in ["sí", "si"]:
            service_options = "\n".join([f"{i+1}. {service}" for i, service in enumerate(SERVICES.keys())])
            reply = f"Genial! Elige un servicio:\n{service_options}\nEscribe el número (1-{len(SERVICES)})."
            state["step"] = "service_confirm"
        else:
            reply = "Por favor, responde 'sí' para agendar una cita."
    elif state["step"] == "service_confirm":
        try:
            choice = int(incoming_msg) - 1
            services_list = list(SERVICES.keys())
            if 0 <= choice < len(services_list):
                state["service"] = services_list[choice]
                state["doctor"] = SERVICES[state["service"]]["doctor"]
                state["staff_id"] = SERVICES[state["service"]]["staff_id"]
                dates = [datetime(2025, 7, 10) + timedelta(days=i) for i in range(15)]
                date_options = "\n".join([f"{i+1}. {date.strftime('%d/%m')}" for i, date in enumerate(dates)])
                reply = f"Has elegido {state['service']} con {state['doctor']}. Elige una fecha:\n{date_options}\nEscribe el número (1-15)."
                state["step"] = "date_confirm"
            else:
                reply = f"Número inválido. Elige un número entre 1 y {len(SERVICES)}."
        except ValueError:
            reply = "Por favor, escribe un número válido."
    elif state["step"] == "date_confirm":
        try:
            choice = int(incoming_msg) - 1
            dates = [datetime(2025, 7, 10) + timedelta(days=i) for i in range(15)]
            if 0 <= choice < len(dates):
                state["date"] = dates[choice].strftime("%d/%m")
                url = f"{BOOKLY_API_BASE}/disponibilidad-doctor-{state['staff_id']}?api_key={BOOKLY_API_KEY}"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                logging.info(f"📅 Datos de API para {state['date']}: {data}")
                target_date = dates[choice].strftime("%Y-%m-%d")
                available_slots = []
                for day in data:
                    if day["date"] == target_date:
                        available_slots.extend(day["available_slots"])
                if available_slots:
                    slots_text = "\n".join([f"{i+1}. {slot['start_date'][11:16]}-{slot['end_date'][11:16]}" for i, slot in enumerate(available_slots)])
                    note = "(Solo 08:00-12:00)" if dates[choice].weekday() == 6 else ""
                    reply = f"Horarios disponibles el {state['date']} {note}:\n{slots_text}\nElige un horario escribiendo el número (1-{len(available_slots)})."
                    state["step"] = "slot_confirm"
                else:
                    reply = f"No hay horarios disponibles el {state['date']}. Elige otra fecha."
                    state["step"] = "date_confirm"
            else:
                reply = "Número inválido. Elige un número entre 1 y 15."
        except (ValueError, requests.RequestException) as e:
            logging.error(f"❌ Error al obtener horarios: {e}")
            reply = "Error al obtener horarios. Intenta de nuevo."
    elif state["step"] == "slot_confirm":
        try:
            choice = int(incoming_msg) - 1
            url = f"{BOOKLY_API_BASE}/disponibilidad-doctor-{state['staff_id']}?api_key={BOOKLY_API_KEY}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            logging.info(f"📅 Datos de API en slot_confirm: {data}")
            target_date = datetime.strptime(state["date"], "%d/%m").replace(2025).strftime("%Y-%m-%d")
            available_slots = []
            for day in data:
                if day["date"] == target_date:
                    available_slots.extend(day["available_slots"])
            logging.info(f"📅 Slots disponibles: {available_slots}")
            if 0 <= choice < len(available_slots):
                selected_slot = f"{available_slots[choice]['start_date'][11:16]}-{available_slots[choice]['end_date'][11:16]}"
                reply = f"¡Cita confirmada con {state['doctor']} el {state['date']} a las {selected_slot} (simulación). ¡Gracias!"
                state["step"] = "start"
                state["service"] = None
                state["doctor"] = None
                state["staff_id"] = None
                state["date"] = None
            else:
                reply = f"Número inválido. Elige un número entre 1 y {len(available_slots)}."
        except (ValueError, requests.RequestException) as e:
            logging.error(f"❌ Error al confirmar cita: {e}")
            reply = "Error al confirmar la cita. Intenta de nuevo."
    else:
        reply = "Algo salió mal. Escribe 'sí' para empezar de nuevo."
        state["step"] = "start"

    twilio_resp.message(reply)
    return str(twilio_resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
