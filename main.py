from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import os
import requests
from dotenv import load_dotenv
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

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

def get_available_dates(staff_id):
    url = f"{BOOKLY_API_BASE}/disponibilidad-doctor-{staff_id}?api_key={BOOKLY_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        dates = [datetime.strptime(day["date"], "%Y-%m-%d").date() for day in data]
        return sorted(set(dates))[:14]  # Máximo 14 fechas únicas
    except requests.RequestException as e:
        logging.error(f"❌ Error al obtener fechas: {e}")
        return []

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
        logging.info(f"Procesando 'service_select' para {sender} con mensaje: {incoming_msg}")
        if incoming_msg in ["sí", "si"]:
            service_options = "\n".join([f"{i+1}. {service}" for i, service in enumerate(SERVICES.keys())])
            reply = f"Genial! Elige un servicio:\n{service_options}\nEscribe el número (1-{len(SERVICES)})."
            state["step"] = "service_confirm"
            logging.info(f"Transición a 'service_confirm' para {sender}")
        else:
            reply = "Por favor, responde 'sí' para agendar una cita."
            logging.info(f"Respuesta inválida en 'service_select' para {sender}")
    elif state["step"] == "service_confirm":
        logging.info(f"Procesando 'service_confirm' para {sender} con mensaje: {incoming_msg}")
        try:
            choice = int(incoming_msg) - 1
            services_list = list(SERVICES.keys())
            if 0 <= choice < len(services_list):
                state["service"] = services_list[choice]
                state["doctor"] = SERVICES[state["service"]]["doctor"]
                state["staff_id"] = SERVICES[state["service"]]["staff_id"]
                available_dates = get_available_dates(state["staff_id"])
                if available_dates:
                    date_options = "\n".join([f"{i+1}. {date.strftime('%d/%m/%Y')}" for i, date in enumerate(available_dates)])
                    reply = f"Has elegido {state['service']} con {state['doctor']}. Elige una fecha:\n{date_options}\nEscribe el número (1-{len(available_dates)})."
                else:
                    reply = f"No hay fechas disponibles para {state['doctor']}. Intenta con otro servicio."
                state["step"] = "date_confirm"
                logging.info(f"Transición a 'date_confirm' para {sender}")
            else:
                reply = f"Número inválido. Elige un número entre 1 y {len(SERVICES)}."
                logging.info(f"Número inválido en 'service_confirm' para {sender}")
        except ValueError:
            reply = "Por favor, escribe un número válido."
            logging.info(f"Valor no numérico en 'service_confirm' para {sender}")
    elif state["step"] == "date_confirm":
        logging.info(f"Procesando 'date_confirm' para {sender} con mensaje: {incoming_msg}")
        try:
            choice = int(incoming_msg) - 1
            available_dates = get_available_dates(state["staff_id"])
            if 0 <= choice < len(available_dates):
                state["date"] = available_dates[choice].strftime("%d/%m/%Y")
                url = f"{BOOKLY_API_BASE}/disponibilidad-doctor-{state['staff_id']}?api_key={BOOKLY_API_KEY}"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                logging.info(f"📅 Datos de API para {state['date']}: {data}")
                target_date = available_dates[choice].strftime("%Y-%m-%d")
                available_slots = []
                for day in data:
                    if day["date"] == target_date:
                        available_slots.extend(day["available_slots"])
                if available_slots:
                    slots_text = "\n".join([f"{i+1}. {slot['start_date'][11:16]}-{slot['end_date'][11:16]}" for i, slot in enumerate(available_slots)])
                    reply = f"Horarios disponibles el {state['date']}:\n{slots_text}\nElige un horario escribiendo el número (1-{len(available_slots)})."
                    state["step"] = "slot_confirm"
                    logging.info(f"Transición a 'slot_confirm' para {sender}")
                else:
                    reply = f"No hay horarios disponibles el {state['date']}. Elige otra fecha."
                    logging.info(f"Sin horarios disponibles el {state['date']} para {sender}")
                    state["step"] = "date_confirm"
            else:
                reply = f"Número inválido. Elige un número entre 1 y {len(available_dates)}."
                logging.info(f"Número inválido en 'date_confirm' para {sender}")
        except (ValueError, requests.RequestException) as e:
            logging.error(f"❌ Error al obtener horarios: {e}")
            reply = "Error al obtener horarios. Intenta de nuevo."
    elif state["step"] == "slot_confirm":
        logging.info(f"Procesando 'slot_confirm' para {sender} con mensaje: {incoming_msg}")
        try:
            choice = int(incoming_msg) - 1
            url = f"{BOOKLY_API_BASE}/disponibilidad-doctor-{state['staff_id']}?api_key={BOOKLY_API_KEY}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            logging.info(f"📅 Datos de API en slot_confirm: {data}")
            target_date = datetime.strptime(state["date"], "%d/%m/%Y").strftime("%Y-%m-%d")
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
                logging.info(f"Cita confirmada para {sender}")
            else:
                reply = f"Número inválido. Elige un número entre 1 y {len(available_slots)}."
                logging.info(f"Número inválido en 'slot_confirm' para {sender}")
        except (ValueError, requests.RequestException) as e:
            logging.error(f"❌ Error al confirmar cita: {e}")
            reply = "Error al confirmar la cita. Intenta de nuevo."
    else:
        reply = "Algo salió mal. Escribe 'sí' para empezar de nuevo."
        state["step"] = "start"
        logging.info(f"Estado inválido reseteado para {sender}")

    twilio_resp.message(reply)
    logging.info(f"📤 Mensaje enviado a {sender}: {reply[:50]}... (longitud: {len(reply)})")
    return str(twilio_resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
