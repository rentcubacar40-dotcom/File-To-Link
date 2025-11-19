import os
import asyncio
from telethon import TelegramClient, events
from redis import Redis

# Configuración desde Variables de Entorno
API_ID = int(os.getenv('API_ID', 0))
API_HASH = os.getenv('API_HASH', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
ADMIN_ID = os.getenv('ADMIN_ID', '')

# Inicializar clientes
redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
client = TelegramClient('bot_session', API_ID, API_HASH)

def get_file_info(file_id):
    return redis_client.hgetall(f'file:{file_id}')

def delete_file(file_id):
    return redis_client.delete(f'file:{file_id}')

def get_user_files(user_id):
    user_files = []
    for key in redis_client.scan_iter('file:*'):
        file_data = redis_client.hgetall(key)
        if file_data.get('user_id') == str(user_id):
            file_id = key.split(':')[1]
            user_files.append((file_id, file_data))
    return user_files

def get_all_files():
    """Obtiene TODOS los archivos (solo para admin)"""
    all_files = []
    for key in redis_client.scan_iter('file:*'):
        file_data = redis_client.hgetall(key)
        file_id = key.split(':')[1]
        all_files.append((file_id, file_data))
    return all_files

def get_stats():
    """Estadísticas generales del bot"""
    total_files = 0
    total_size = 0
    user_ids = set()
    
    for key in redis_client.scan_iter('file:*'):
        file_data = redis_client.hgetall(key)
        total_files += 1
        total_size += int(file_data.get('size', 0))
        user_ids.add(file_data.get('user_id', ''))
    
    return total_files, total_size, len(user_ids)

def is_admin(user_id):
    """Verifica si el usuario es administrador"""
    return str(user_id) == ADMIN_ID

@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    user = await event.get_sender()
    admin_text = "\n👑 **Eres administrador** - Usa /admin para panel de control" if is_admin(event.sender_id) else ""
    
    await event.reply(
        f'🤖 **Bot File to Link**\n\n'
        f'Hola {user.first_name}!{admin_text}\n\n'
        '**Comandos disponibles:**\n'
        '• /start - Mostrar este mensaje\n'
        '• /myfiles - Ver tus archivos\n' 
        '• /delete [id] - Eliminar un archivo\n'
        '• /info - Información del bot\n'
        '• /stats - Estadísticas\n\n'
        '¡Envía un archivo para comenzar!'
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
        '• /listfiles - Listar todos los archivos\n'
        '• /cleanup - Limpiar archivos expirados\n'
        '• /deleteall - Eliminar TODOS los archivos\n'
        '• /delete [id] - Eliminar archivo específico (de cualquier usuario)\n'
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
    
    # SIN LÍMITES - dividimos en múltiples mensajes si es necesario
    total_size = 0
    response_parts = []
    current_response = '📂 **Todos los archivos activos:**\n\n'
    
    for i, (file_id, file_data) in enumerate(all_files, 1):
        file_name = file_data.get('name', 'Sin nombre')[:30]  # Limitar nombre para evitar overflow
        file_size = int(file_data.get('size', 0))
        user_id = file_data.get('user_id', 'Desconocido')
        ttl = redis_client.ttl(f'file:{file_id}')
        hours = ttl // 3600
        minutes = (ttl % 3600) // 60
        
        file_entry = (
            f'**{i}. {file_name}**\n'
            f'   👤 User: `{user_id}`\n'
            f'   📦 {file_size / 1024 / 1024:.2f} MB\n'
            f'   ⏰ {hours}h {minutes}m\n'
            f'   🗑️ `/delete {file_id}`\n\n'
        )
        
        # Si el mensaje actual sería muy largo, guardar y empezar nuevo
        if len(current_response) + len(file_entry) > 4000:
            response_parts.append(current_response)
            current_response = f'📂 **Continuación...**\n\n{file_entry}'
        else:
            current_response += file_entry
        
        total_size += file_size
    
    # Agregar la última parte
    if current_response:
        current_response += f'📊 **Total:** {len(all_files)} archivos, {total_size / 1024 / 1024:.2f} MB'
        response_parts.append(current_response)
    
    # Enviar todos los mensajes
    for part in response_parts:
        await event.reply(part)
        await asyncio.sleep(1)  # Pequeña pausa para evitar flood

@client.on(events.NewMessage(pattern='/cleanup'))
async def cleanup_handler(event):
    if not is_admin(event.sender_id):
        return
    
    deleted_count = 0
    for key in redis_client.scan_iter('file:*'):
        ttl = redis_client.ttl(key)
        if ttl < 1:  # Archivos expirados
            redis_client.delete(key)
            deleted_count += 1
    
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
    
    total_files = len(list(redis_client.scan_iter('file:*')))
    
    for key in redis_client.scan_iter('file:*'):
        redis_client.delete(key)
    
    await event.reply(f'🗑️ **Eliminados {total_files} archivos.**')

@client.on(events.NewMessage(pattern='/myfiles'))
async def myfiles_handler(event):
    user_id = event.sender_id
    user_files = get_user_files(user_id)
    
    if not user_files:
        await event.reply('📭 **No tienes archivos activos.**\nEnvía un archivo para comenzar.')
        return
    
    response = '📂 **Tus archivos activos:**\n\n'
    for file_id, file_data in user_files:
        file_name = file_data.get('name', 'Sin nombre')
        file_size = file_data.get('size', 0)
        ttl = redis_client.ttl(f'file:{file_id}')
        hours = ttl // 3600
        minutes = (ttl % 3600) // 60
        
        response += f'📁 `{file_name}`\n'
        response += f'📦 {int(file_size) / 1024 / 1024:.2f} MB\n'
        response += f'⏰ Expira en: {hours}h {minutes}m\n'
        response += f'🗑️ Eliminar: `/delete {file_id}`\n\n'
    
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
    file_data = get_file_info(file_id)
    if not file_data:
        await event.reply('❌ **Archivo no encontrado.** Puede haber expirado o no existir.')
        return
    
    # Verificar permisos: usuario normal solo puede eliminar sus archivos, admin puede eliminar cualquiera
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
        f'• Usuarios únicos: {unique_users}{admin_text}'
    )

@client.on(events.NewMessage(pattern='/info'))
async def info_handler(event):
    user_files = get_user_files(event.sender_id)
    await event.reply(
        'ℹ️ **Información del Bot**\n\n'
        '• 🤖 Desarrollado con Telethon\n'
        '• 🚀 Hosteado en Render.com\n'
        '• 💾 Almacenamiento temporal (24h)\n'
        '• 📦 Soporte para archivos grandes\n'
        '• 🔒 Enlaces temporales seguros\n'
        '• 🗑️ Eliminación manual disponible\n\n'
        f'📊 **Tus archivos activos:** {len(user_files)}'
    )

@client.on(events.NewMessage(func=lambda e: e.file and not e.media_webpage))
async def file_handler(event):
    try:
        user_id = event.sender_id
        msg = await event.reply('📥 **Descargando archivo...**')
        
        # Descargar archivo
        file = await event.download_media(file=bytes)
        
        await msg.edit('🔗 **Generando enlace...**')
        
        # Obtener información del archivo
        original_msg = await event.get_message()
        file_name = original_msg.file.name or f"file_{original_msg.file.id}"
        file_size = original_msg.file.size or len(file)
        
        # Guardar en Redis
        file_id = str(original_msg.file.id)
        file_data = {
            'name': file_name,
            'size': str(file_size),
            'user_id': str(user_id),
            'timestamp': str(event.message.date.timestamp())
        }
        
        redis_client.hset(f'file:{file_id}', mapping=file_data)
        redis_client.expire(f'file:{file_id}', 86400)  # 24 horas
        
        # Generar información del enlace
        file_link = f"https://t.me/{event.chat.username}/{event.message.id}" if event.chat.username else f"File ID: {file_id}"
        
        response = (
            f'✅ **Archivo procesado correctamente!**\n\n'
            f'📁 **Nombre:** `{file_name}`\n'
            f'📦 **Tamaño:** {file_size / 1024 / 1024:.2f} MB\n'
            f'🔗 **Enlace:** {file_link}\n'
            f'🆔 **ID:** `{file_id}`\n'
            f'⏰ **Válido por:** 24 horas\n\n'
            f'💡 *Usa `/myfiles` para ver tus archivos o `/delete {file_id}` para eliminar*'
        )
        
        await msg.edit(response)
        
    except Exception as e:
        await event.reply(f'❌ **Error:** {str(e)}')

async def main():
    await client.start(bot_token=BOT_TOKEN)
    print('🤖 Bot iniciado correctamente!')
    print(f'👑 Admin ID: {ADMIN_ID}')
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
