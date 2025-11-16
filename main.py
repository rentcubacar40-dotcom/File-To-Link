import os
import logging
from flask import Flask, request, jsonify
from telegram import Bot, Update
import hmac
import hashlib

# Configuración
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHOREO_URL = os.getenv("CHOREO_BASE_URL")  # Tu URL de Choreo
PORT = int(os.getenv("PORT", "8000"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "default_secret")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)

# Verificar que el token esté configurado
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN no configurado")

@app.route('/')
def home():
    return "🤖 Bot activo - Usa /start en Telegram"

@app.route('/health')
def health():
    return "✅ OK"

@app.route('/set_webhook')
def set_webhook():
    """Configurar webhook manualmente"""
    try:
        webhook_url = f"{CHOREO_URL}/webhook"
        result = bot.set_webhook(webhook_url)
        return f"✅ Webhook configurado: {webhook_url}"
    except Exception as e:
        return f"❌ Error: {e}"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint para recibir updates de Telegram"""
    try:
        # Verificar signature (opcional pero recomendado)
        if not verify_signature(request):
            return "❌ Signature inválida", 401
        
        # Procesar update
        update = Update.de_json(request.get_json(), bot)
        process_update(update)
        
        return "✅ OK"
    
    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        return "❌ Error", 500

def verify_signature(request):
    """Verificar que el webhook viene de Telegram"""
    # Para producción, implementar verificación
    return True

def process_update(update):
    """Procesar el update recibido"""
    try:
        if update.message:
            message = update.message
            chat_id = message.chat.id
            text = message.text or ""
            
            logger.info(f"Mensaje recibido: {text} de {chat_id}")
            
            if text.startswith('/start'):
                bot.send_message(
                    chat_id=chat_id,
                    text="¡🤖 Bot activo! ✅\n\nFuncionando con webhooks en Choreo.\nEnvía /help para más opciones."
                )
            
            elif text.startswith('/help'):
                bot.send_message(
                    chat_id=chat_id,
                    text="📋 **Comandos:**\n/start - Iniciar\n/help - Ayuda\n/test - Probar"
                )
            
            elif text.startswith('/test'):
                bot.send_message(
                    chat_id=chat_id,
                    text="✅ **Test exitoso**\nWebhook funcionando correctamente en Choreo!"
                )
            
            else:
                bot.send_message(
                    chat_id=chat_id,
                    text="❌ Comando no reconocido. Usa /help para ver comandos disponibles."
                )
    
    except Exception as e:
        logger.error(f"Error procesando update: {e}")

@app.route('/test_message')
def test_message():
    """Endpoint para probar envío de mensajes"""
    try:
        # Enviar mensaje de prueba (cambia el chat_id)
        test_chat_id = "123456789"  # Cambia por tu chat_id
        bot.send_message(
            chat_id=test_chat_id,
            text="🔔 Mensaje de prueba desde Choreo"
        )
        return "✅ Mensaje enviado"
    except Exception as e:
        return f"❌ Error: {e}"

if __name__ == '__main__':
    logger.info(f"🚀 Iniciando bot con webhooks en puerto {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
