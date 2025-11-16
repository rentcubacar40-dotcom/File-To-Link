import os
import logging
import uuid
import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask, send_file

# Configuración con puerto 8000
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHOREO_BASE_URL = os.getenv("CHOREO_BASE_URL")
PORT = int(os.getenv("PORT", "8000"))  # ✅ Puerto 8000 por defecto

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Almacenamiento en memoria
file_storage = {}

# Inicializar Flask para las descargas
flask_app = Flask(__name__)

@flask_app.route('/download/<file_id>')
def download_file(file_id):
    """Endpoint para descargar archivos"""
    try:
        if file_id not in file_storage:
            return "❌ Enlace no válido o expirado", 404
        
        file_info = file_storage[file_id]
        
        # Verificar expiración (24 horas)
        if datetime.now() - file_info['created_at'] > timedelta(hours=24):
            if os.path.exists(file_info['path']):
                os.remove(file_info['path'])
            del file_storage[file_id]
            return "⏰ El enlace ha expirado", 410
        
        return send_file(
            file_info['path'],
            as_attachment=True,
            download_name=file_info['filename']
        )
        
    except Exception as e:
        logger.error(f"Error descargando: {e}")
        return "❌ Error al descargar", 500

@flask_app.route('/health')
def health_check():
    return "✅ Bot funcionando"

# Funciones del Bot de Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = """
🤖 **File to Link Bot**

Envía cualquier archivo y recibirás un enlace de descarga temporal.

📁 **Soportado:** Documentos, imágenes, audio, video
⏰ **Válido por:** 24 horas

¡Envía un archivo para comenzar!
    """
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.message.from_user
        logger.info(f"Usuario {user.id} envió un archivo")
        
        if update.message.document:
            file_obj = update.message.document
        elif update.message.photo:
            file_obj = update.message.photo[-1]
        elif update.message.video:
            file_obj = update.message.video
        elif update.message.audio:
            file_obj = update.message.audio
        else:
            await update.message.reply_text("❌ Formato no soportado")
            return

        file = await file_obj.get_file()
        file_id = str(uuid.uuid4())
        file_path = f"files/{file_id}_{file_obj.file_name or 'file'}"
        
        os.makedirs("files", exist_ok=True)
        local_path = await file.download_to_drive(custom_path=file_path)
        
        file_storage[file_id] = {
            'path': local_path,
            'filename': file_obj.file_name or f"file_{file_id}",
            'mime_type': getattr(file_obj, 'mime_type', 'application/octet-stream'),
            'created_at': datetime.now(),
            'user_id': user.id
        }
        
        download_url = f"{CHOREO_BASE_URL}/download/{file_id}"
        
        response_text = f"""
✅ **Archivo procesado**

📄 **Nombre:** {file_storage[file_id]['filename']}
🔗 **Enlace:** {download_url}
⏰ **Válido por:** 24 horas
        """
        
        await update.message.reply_text(response_text)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Error al procesar el archivo")

async def cleanup_task():
    while True:
        try:
            current_time = datetime.now()
            expired_files = []
            
            for file_id, file_info in file_storage.items():
                if current_time - file_info['created_at'] > timedelta(hours=24):
                    expired_files.append(file_id)
            
            for file_id in expired_files:
                file_info = file_storage[file_id]
                if os.path.exists(file_info['path']):
                    os.remove(file_info['path'])
                del file_storage[file_id]
                logger.info(f"Archivo expirado eliminado: {file_id}")
            
        except Exception as e:
            logger.error(f"Error en cleanup: {e}")
        
        await asyncio.sleep(3600)

def run_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(
        filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO, 
        handle_file
    ))
    
    application.run_polling()

async def main():
    os.makedirs("files", exist_ok=True)
    asyncio.create_task(cleanup_task())
    await run_bot()

if __name__ == '__main__':
    import threading
    
    def run_flask():
        flask_app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)  # ✅ Puerto 8000
    
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    asyncio.run(main())
