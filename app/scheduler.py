import os
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import sqlite3
from app import create_app
from app.blueprints.backups.routes import get_db_path, get_backup_dir

def create_daily_backup():
    """Función que crea un backup diario"""
    app = create_app()
    with app.app_context():
        try:
            db_path = get_db_path()
            backup_dir = get_backup_dir()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"auto_backup_{timestamp}.db"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            # Crear copia de la base de datos
            source = sqlite3.connect(db_path)
            backup = sqlite3.connect(backup_path)
            
            with backup:
                source.backup(backup)
            
            source.close()
            backup.close()
            
            print(f"Backup automático creado: {backup_filename}")
            app.logger.info(f"Backup automático creado: {backup_filename}")

            
            # Limitar número de backups (opcional)
            clean_old_backups(backup_dir)
            
        except Exception as e:
            print(f"Error al crear backup automático: {str(e)}")

def clean_old_backups(backup_dir, max_backups=10):
    """Mantener solo los últimos X backups"""
    backups = []
    for filename in os.listdir(backup_dir):
        if filename.startswith('auto_backup_') and filename.endswith('.db'):
            filepath = os.path.join(backup_dir, filename)
            backups.append({
                'filename': filename,
                'ctime': os.path.getctime(filepath)
            })
    
    # Ordenar por fecha (más antiguos primero)
    backups.sort(key=lambda x: x['ctime'])
    
    # Eliminar los más antiguos si superamos el límite
    while len(backups) > max_backups:
        old_backup = backups.pop(0)
        try:
            os.remove(os.path.join(backup_dir, old_backup['filename']))
            print(f"Eliminado backup antiguo: {old_backup['filename']}")
        except Exception as e:
            print(f"Error al eliminar backup {old_backup['filename']}: {str(e)}")

def start_scheduler(app=None):
    """Versión mejorada que maneja tanto llamada autónoma como integrada"""
    if app is None:
        from app import create_app
        app = create_app()
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        create_daily_backup,
        'cron',
        hour=12,  # 12 PM
        minute=00,
        timezone='America/Managua'  # Ajusta a tu zona horaria
    )
    scheduler.start()
    print("Programador de backups iniciado. Se ejecutará diariamente a las 12 PM")