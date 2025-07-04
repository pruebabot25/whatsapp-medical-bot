@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.form.get("Body", "").strip()
    sender = request.form.get("From")
    logging.info(f"📩 Mensaje recibido de {sender}: {incoming_msg}")

    if not incoming_msg:
        twilio_resp = MessagingResponse()
        twilio_resp.message("Por favor, envía un mensaje válido.")
        return str(twilio_resp)

    # Comentamos esto porque aún no usamos WordPress
    # if not OR_API_KEY or not WP_URL:
    #     logging.error("❌ OPENROUTER_API_KEY o WORDPRESS_URL no están configurados")
    #     twilio_resp = MessagingResponse()
    #     twilio_resp.message("Error de configuración del bot. Contacta al administrador.")
    #     return str(twilio_resp)

    headers = {
        "Authorization": f"Bearer {OR_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://tusitio.com",
        "X-Title": "Asistente Médico"
    }

    payload = {
        "model": "mistralai/mistral-7b-instruct:free",
        "messages": [
            {"role": "system", "content": "Eres un asistente médico que responde preguntas sobre citas médicas."},
            {"role": "user", "content": incoming_msg}
        ],
        "max_tokens": 300
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
