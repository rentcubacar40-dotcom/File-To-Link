import os
import asyncio
import time
from flask import Flask, send_file
from telethon import TelegramClient, events
from threading import Thread

# 🔥 VARIABLES - REEMPLAZA CON TUS DATOS
API_ID = 20534584  # De my.telegram.org
API_HASH = "6d5b13261d2c92a9a00afc1fd613b9df"  # De my.telegram.org  
BOT_TOKEN = "8172167976:AAHGIvygDZVcEi1z7yghxp8IGR1RPm87waY"  # De @BotFather
ADMIN_ID = "7363341763"  # De @userinfobot
RENDER_URL = "https://filetolink-eliel.onrender.com"  # Tu URL de Render

# Almacenamiento en memoria
file_registry = {}
client = TelegramClient('bot_session', API_ID, API_HASH)
app = Flask(__name__)

# Crear directorios
os.makedirs('static/files', exist_ok=True)

def cleanup_expired_files():
    """Limpia archivos expirados (24 horas)"""
    current_time = time.time()
    expired_files = []
    
    for file_id, file_data in file_registry.items():
        if current_time - file_data['timestamp'] > 86400:  # 24 horas
            expired_files.append(file_id)
    
    for file_id in expired_files:
        delete_file(file_id)
    
    if expired_files:
        print(f"🧹 Limpiados {len(expired_files)} archivos expirados")

def delete_file(file_id):
    """Eliminar archivo del sistema"""
    file_path = f"static/files/{file_id}"
    if os.path.exists(file_path):
        os.remove(file_path)
    if file_id in file_registry:
        del file_registry[file_id]
    return True

def get_user_files(user_id):
    """Obtener archivos de un usuario"""
    return {fid: data for fid, data in file_registry.items() 
            if data.get('user_id') == str(user_id)}

def get_all_files():
    """Obtener todos los archivos"""
    return file_registry

def get_stats():
    """Estadísticas del sistema"""
    total_files = len(file_registry)
    total_size = sum(data.get('size', 0) for data in file_registry.values())
    unique_users = len(set(data.get('user_id') for data in file_registry.values()))
    return total_files, total_size, unique_users

def is_admin(user_id):
    """Verificar si es administrador"""
    return str(user_id) == ADMIN_ID

# RUTAS WEB
@app.route('/')
def home():
    total_files, total_size, unique_users = get_stats()
    return f"""
    <h1>🤖 File to Link Bot</h1>
    <p><strong>Estado:</strong> Online</p>
    <p><strong>Archivos activos:</strong> {total_files}</p>
    <p><strong>Espacio usado:</strong> {total_size / 1024 / 1024:.2f} MB</p>
    <p><strong>Usuarios únicos:</strong> {unique_users}</p>
    <hr>
    <p><em>Usa el bot de Telegram para subir archivos</em></p>
    """

@app.route('/static/<file_id>/downloads/<filename>')
def download_file(file_id, filename):
    """Servir archivo para descarga directa"""
    if file_id not in file_registry:
        return "❌ Archivo no encontrado o expirado", 404
    
    file_path = f"static/files/{file_id}"
    if not os.path.exists(file_path):
        return "❌ Archivo no disponible", 404
    
    file_data = file_registry[file_id]
    
    # Verificar expiración (24 horas)
    if time.time() - file_data['timestamp'] > 86400:
        delete_file(file_id)
        return "❌ Archivo expirado", 410
    
    original_name = file_data.get('name', 'file')
    return send_file(file_path, as_attachment=True, download_name=original_name)

@app.route('/api/stats')
def api_stats():
    """API de estadísticas"""
    total_files, total_size, unique_users = get_stats()
    return {
        "status": "online",
        "total_files": total_files,
        "total_size_mb": round(total_size / 1024 / 1024, 2),
        "unique_users": unique_users
    }

# HANDLERS DE TELEGRAM
@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    user = await event.get_sender()
    admin_text = "\n👑 **Eres administrador** - Usa /admin" if is_admin(event.sender_id) else ""
    
    await event.reply(
        f'🤖 **File to Link Bot**\n\n'
        f'Hola {user.first_name}!{admin_text}\n\n'
        '**Envía cualquier archivo y recibirás:**\n'
        f'• 🔗 Enlace directo formato: `{RENDER_URL}/static/123456/downloads/archivo.ext`\n'
        '• 📱 Compatible con navegadores\n'
        '• ⏰ Válido por 24 horas\n'
        '• 💾 Sin base de datos externa\n\n'
        '**Comandos:** /myfiles, /stats, /info\n\n'
        '¡Envía un archivo ahora!'
    )

@client.on(events.NewMessage(pattern='/admin'))
async def admin_handler(event):
    if not is_admin(event.sender_id):
        await event.reply('❌ **Acceso denegado.** Solo para administradores.')
        return
    
    total_files, total_size, unique_users = get_stats()
    
    response = (
        '👑 **Panel de Administración**\n\n'
        f'📊 **Estadísticas:**\n'
        f'• Archivos activos: {total_files}\n'
        f'• Espacio usado: {total_size / 1024 / 1024:.2f} MB\n'
        f'• Usuarios únicos: {unique_users}\n\n'
        '**Comandos de Admin:**\n'
        '• /listfiles - Ver todos los archivos\n'
        '• /cleanup - Limpiar archivos expirados\n'
        '• /deleteall confirm - Eliminar TODOS los archivos\n'
        '• /delete [id] - Eliminar archivo específico\n'
    )
    
    await event.reply(response)

@client.on(events.NewMessage(pattern='/listfiles'))
async def listfiles_handler(event):
    if not is_admin(event.sender_id):
        await event.reply('❌ **Acceso denegado.**')
        return
    
    all_files = get_all_files()
    
    if not all_files:
        await event.reply('📭 **No hay archivos activos.**')
        return
    
    response = '📂 **Todos los archivos activos:**\n\n'
    total_size = 0
    
    for i, (file_id, file_data) in enumerate(list(all_files.items())[:15], 1):
        file_name = file_data.get('name', 'Sin nombre')[:30]
        file_size = file_data.get('size', 0)
        user_id = file_data.get('user_id', 'Desconocido')
        time_left = 86400 - (time.time() - file_data['timestamp'])
        hours = int(time_left // 3600)
        minutes = int((time_left % 3600) // 60)
        
        download_url = f"{RENDER_URL}/static/{file_id}/downloads/{file_data.get('name', 'file')}"
        
        response += f'**{i}. {file_name}**\n'
        response += f'   👤 User: `{user_id}`\n'
        response += f'   📦 {file_size / 1024 / 1024:.2f} MB\n'
        response += f'   ⏰ {hours}h {minutes}m\n'
        response += f'   🔗 `/delete {file_id}`\n\n'
        
        total_size += file_size
    
    response += f'📊 **Total:** {len(all_files)} archivos, {total_size / 1024 / 1024:.2f} MB'
    
    await event.reply(response)

@client.on(events.NewMessage(pattern='/cleanup'))
async def cleanup_handler(event):
    if not is_admin(event.sender_id):
        return
    
    initial_count = len(file_registry)
    cleanup_expired_files()
    final_count = len(file_registry)
    
    deleted_count = initial_count - final_count
    await event.reply(f'🧹 **Limpieza completada:** {deleted_count} archivos expirados eliminados.')

@client.on(events.NewMessage(pattern='/deleteall'))
async def deleteall_handler(event):
    if not is_admin(event.sender_id):
        return
    
    # Confirmación peligrosa
    if not event.message.text.endswith(' confirm'):
        await event.reply(
            '⚠️ **¡PELIGRO!** Esto eliminará TODOS los archivos.\n'
            'Escribe `/deleteall confirm` para proceder.'
        )
        return
    
    total_files = len(file_registry)
    
    # Eliminar todos los archivos
    for file_id in list(file_registry.keys()):
        delete_file(file_id)
    
    await event.reply(f'🗑️ **Eliminados {total_files} archivos.**')

@client.on(events.NewMessage(pattern='/myfiles'))
async def myfiles_handler(event):
    user_id = event.sender_id
    user_files = get_user_files(user_id)
    
    if not user_files:
        await event.reply('📭 **No tienes archivos activos.**\nEnvía un archivo para comenzar.')
        return
    
    response = '📂 **Tus archivos activos:**\n\n'
    for file_id, file_data in list(user_files.items())[:10]:
        file_name = file_data.get('name', 'Sin nombre')
        file_size = file_data.get('size', 0)
        time_left = 86400 - (time.time() - file_data['timestamp'])
        hours = int(time_left // 3600)
        minutes = int((time_left % 3600) // 60)
        
        download_url = f"{RENDER_URL}/static/{file_id}/downloads/{file_name}"
        
        response += f'📁 `{file_name}`\n'
        response += f'📦 {file_size / 1024 / 1024:.2f} MB\n'
        response += f'⏰ Expira en: {hours}h {minutes}m\n'
        response += f'🔗 `{download_url}`\n'
        response += f'🗑️ Eliminar: `/delete {file_id}`\n\n'
    
    if len(user_files) > 10:
        response += f'📋 ...y {len(user_files) - 10} archivos más\n'
    
    response += '💡 *Usa /delete [id] para eliminar un archivo*'
    
    await event.reply(response)

@client.on(events.NewMessage(pattern='/delete'))
async def delete_handler(event):
    user_id = event.sender_id
    args = event.message.text.split()
    
    if len(args) < 2:
        await event.reply(
            '❌ **Uso incorrecto:**\n'
            '`/delete [file_id]`\n\n'
            'Ejemplo: `/delete 123456789`\n'
            'Usa `/myfiles` para ver tus archivos y sus IDs.'
        )
        return
    
    file_id = args[1].strip()
    
    # Verificar que el archivo existe
    if file_id not in file_registry:
        await event.reply('❌ **Archivo no encontrado.** Puede haber expirado o no existir.')
        return
    
    file_data = file_registry[file_id]
    
    # Verificar permisos
    if not is_admin(user_id) and file_data.get('user_id') != str(user_id):
        await event.reply('❌ **No tienes permisos** para eliminar este archivo.')
        return
    
    # Eliminar el archivo
    deleted = delete_file(file_id)
    if deleted:
        file_name = file_data.get('name', 'Archivo')
        await event.reply(f'✅ **{file_name} eliminado correctamente.**')
    else:
        await event.reply('❌ **Error al eliminar el archivo.**')

@client.on(events.NewMessage(pattern='/stats'))
async def stats_handler(event):
    total_files, total_size, unique_users = get_stats()
    admin_text = "\n👑 Usa /admin para más controles" if is_admin(event.sender_id) else ""
    
    await event.reply(
        '📊 **Estadísticas del Bot:**\n\n'
        f'• Archivos activos: {total_files}\n'
        f'• Espacio total: {total_size / 1024 / 1024:.2f} MB\n'
        f'• Usuarios únicos: {unique_users}\n'
        f'• Estado: ✅ Online{admin_text}'
    )

@client.on(events.NewMessage(pattern='/info'))
async def info_handler(event):
    user_files = get_user_files(event.sender_id)
    await event.reply(
        'ℹ️ **Información del Bot**\n\n'
        '• 🤖 Desarrollado con Telethon + Flask\n'
        '• 🚀 Hosteado en Render.com\n'
        '• 💾 Almacenamiento en memoria (24h)\n'
        '• 📦 Soporte para archivos grandes\n'
        '• 🔗 Enlaces directos permanentes\n'
        '• 🗑️ Eliminación manual disponible\n\n'
        f'📊 **Tus archivos activos:** {len(user_files)}'
    )

@client.on(events.NewMessage(func=lambda e: e.file and not e.media_webpage))
async def file_handler(event):
    try:
        user_id = event.sender_id
        msg = await event.reply('📥 **Descargando archivo...**')
        
        # Descargar archivo
        file_id = str(event.file.id)
        file_path = f"static/files/{file_id}"
        await event.download_media(file=file_path)
        
        await msg.edit('🔗 **Generando enlace...**')
        
        # Información del archivo
        file_name = event.file.name or f"file_{file_id}"
        file_size = event.file.size or os.path.getsize(file_path)
        
        # Registrar en memoria
        file_registry[file_id] = {
            'name': file_name,
            'size': file_size,
            'user_id': str(user_id),
            'timestamp': time.time()
        }
        
        # Generar enlace directo
        download_url = f"{RENDER_URL}/static/{file_id}/downloads/{file_name}"
        
        response = (
            f'✅ **Archivo procesado correctamente!**\n\n'
            f'📁 **Nombre:** `{file_name}`\n'
            f'📦 **Tamaño:** {file_size / 1024 / 1024:.2f} MB\n'
            f'🔗 **Enlace directo:**\n`{download_url}`\n\n'
            f'🆔 **ID:** `{file_id}`\n'
            f'⏰ **Válido por:** 24 horas\n\n'
            f'💡 *Copia y comparte el enlace donde quieras*\n'
            f'📊 *Usa /myfiles para ver tus archivos*'
        )
        
        await msg.edit(response)
        
        # Limpiar archivos expirados
        cleanup_expired_files()
        
    except Exception as e:
        await event.reply(f'❌ **Error:** {str(e)}')

def run_flask():
    """Ejecutar servidor Flask"""
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

async def run_telegram():
    """Ejecutar bot de Telegram"""
    await client.start(bot_token=BOT_TOKEN)
    print('🤖 Bot de Telegram iniciado correctamente!')
    print(f'🌐 Servidor web: {RENDER_URL}')
    print(f'📊 Archivos en memoria: {len(file_registry)}')
    await client.run_until_disconnected()

def main():
    """Ejecutar ambos servicios"""
    print('🚀 Iniciando File to Link Bot (Sin Redis)...')
    
    # Limpiar archivos expirados al inicio
    cleanup_expired_files()
    
    # Iniciar Flask en hilo separado
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Iniciar Telegram en el hilo principal
    asyncio.run(run_telegram())

if __name__ == '__main__':
    main()
