import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Configuración
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Logging simple
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start simple"""
    user = update.effective_user
    logger.info(f"Usuario {user.id} ejecutó /start")
    
    await update.message.reply_text(
        "¡🤖 Bot activo! ✅\n\n"
        "Funciona correctamente en Choreo.\n"
        "Envía /help para más opciones."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help"""
    await update.message.reply_text(
        "📋 **Comandos disponibles:**\n"
        "/start - Iniciar bot\n"
        "/help - Esta ayuda\n"
        "/test - Probar funcionamiento\n\n"
        "Próximamente: subir archivos 📁"
    )

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /test"""
    await update.message.reply_text(
        "✅ **Test exitoso**\n"
        "El bot está funcionando correctamente.\n"
        "Hora del servidor: funcionando\n"
        "Conexión: estable"
    )

def main():
    """Función principal SIMPLE"""
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN no configurado")
        return
    
    try:
        # Crear aplicación
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Solo 3 comandos básicos
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("test", test))
        
        # Iniciar bot
        logger.info("🤖 Iniciando bot SIMPLE...")
        application.run_polling(
            drop_pending_updates=True,
            timeout=30,
            pool_timeout=30
        )
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")

if __name__ == '__main__':
    main()
