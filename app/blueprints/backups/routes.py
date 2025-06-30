import os
from datetime import datetime
from flask import render_template, jsonify, send_file, current_app
from werkzeug.utils import secure_filename
from app.blueprints.backups import backup_bp
import sqlite3
#from .services import create_backup_service, list_backups_service, restore_backup_service


# Helper functions
def get_db_path():
    """Obtiene la ruta absoluta de la base de datos SQLite"""
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    print(db_uri)
    if not db_uri.startswith('sqlite:///'):
        raise ValueError("Solo se soportan backups para SQLite")
    
    db_path = db_uri.replace('sqlite:///', '')
    if not os.path.isabs(db_path):
        db_path = os.path.join(current_app.root_path, db_path)
    
    return db_path

def get_backup_dir():
    """Obtiene el directorio de backups con validación adicional"""
    backup_dir = current_app.config.get('BACKUP_FOLDER')
    if not backup_dir:
        backup_dir = os.path.join(current_app.root_path, 'backups')
    
    # Crear directorio si no existe con permisos seguros
    os.makedirs(backup_dir, mode=0o755, exist_ok=True)
    
    # Verificar que es un directorio válido y escribible
    if not os.access(backup_dir, os.W_OK):
        raise PermissionError(f"No se puede escribir en el directorio de backups: {backup_dir}")
    
    return backup_dir

def api_response(success, message, data=None, status_code=200):
    """Formato estándar para respuestas API"""
    response = {
        'success': success,
        'message': message,
        'data': data or {}
    }
    return jsonify(response), status_code

# Routes
@backup_bp.route('/')
def index():
    """Ruta principal para la interfaz web"""
    backups = []
    backup_dir = get_backup_dir()
    
    for filename in os.listdir(backup_dir):
        if filename.endswith('.db'):
            filepath = os.path.join(backup_dir, filename)
            stats = os.stat(filepath)
            backups.append({
                'filename': filename,
                'size': round(stats.st_size / (1024 * 1024), 2),  # MB
                'created': datetime.fromtimestamp(stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                'path': filepath
            })
    
    return render_template('backup.html', 
                         backups=sorted(backups, key=lambda x: x['created'], reverse=True))

@backup_bp.route('/api/list', methods=['GET'])
def list_backups():
    """API para listar backups disponibles"""
    try:
        backups = []
        backup_dir = get_backup_dir()
        
        for filename in os.listdir(backup_dir):
            if filename.endswith('.db'):
                filepath = os.path.join(backup_dir, filename)
                stats = os.stat(filepath)
                backups.append({
                    'filename': filename,
                    'size': round(stats.st_size / (1024 * 1024), 2),
                    'created': datetime.fromtimestamp(stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                    'path': filepath
                })
        
        return api_response(True, 'Backups listados', 
                          sorted(backups, key=lambda x: x['created'], reverse=True))
    except Exception as e:
        return api_response(False, f'Error al listar backups: {str(e)}', status_code=500)

#ruta para la creacion de backups
@backup_bp.route('/api/create', methods=['POST'])
def create_backup():
    try:
        db_path = get_db_path()
        backup_dir = current_app.config.get('BACKUP_FOLDER')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Limitar número de backups
        if current_app.config.get('MAX_BACKUPS', 0) > 0:
            existing_backups = sorted(
                [f for f in os.listdir(backup_dir) if f.endswith('.db')],
                key=lambda f: os.path.getmtime(os.path.join(backup_dir, f))
            )
            while len(existing_backups) >= current_app.config['MAX_BACKUPS']:
                os.remove(os.path.join(backup_dir, existing_backups.pop(0)))
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Conexión y copia más robusta
        source = sqlite3.connect(db_path)
        backup = sqlite3.connect(backup_path)
        
        try:
            with backup:
                source.backup(backup)
            return api_response(True, 'Respaldo creado exitosamente', {
                'filename': backup_filename,
                'path': backup_path,
                'size': round(os.path.getsize(backup_path) / (1024 * 1024), 2)
            })
        finally:
            source.close()
            backup.close()
            
    except Exception as e:
        return api_response(False, f'Error al crear respaldo: {str(e)}', status_code=500)

@backup_bp.route('/api/download/<filename>', methods=['GET'])
def download_backup(filename):
    """API para descargar un backup"""
    try:
        backup_dir = get_backup_dir()
        filepath = os.path.join(backup_dir, secure_filename(filename))
        
        if not os.path.exists(filepath):
            return api_response(False, 'Archivo no encontrado', status_code=404)
            
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        return api_response(False, f'Error al descargar: {str(e)}', status_code=500)

@backup_bp.route('/api/restore/<filename>', methods=['POST'])
def restore_backup(filename):
    """API para restaurar un backup"""
    try:
        db_path = get_db_path()
        backup_dir = get_backup_dir()
        backup_path = os.path.join(backup_dir, secure_filename(filename))
        
        if not os.path.exists(backup_path):
            return api_response(False, 'Archivo de respaldo no encontrado', status_code=404)
        
        # Crear copia de seguridad preventiva
        preventive_filename = f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        preventive_path = os.path.join(backup_dir, preventive_filename)
        
        current_db = sqlite3.connect(db_path)
        preventive_db = sqlite3.connect(preventive_path)
        with preventive_db:
            current_db.backup(preventive_db)
        current_db.close()
        preventive_db.close()
        
        # Restaurar el backup solicitado
        backup_db = sqlite3.connect(backup_path)
        main_db = sqlite3.connect(db_path)
        with main_db:
            backup_db.backup(main_db)
        backup_db.close()
        main_db.close()
        
        return api_response(True, 'Base de datos restaurada exitosamente', {
            'preventive_backup': preventive_filename
        })
    except Exception as e:
        return api_response(False, f'Error al restaurar: {str(e)}', status_code=500)

@backup_bp.route('/api/delete/<filename>', methods=['DELETE'])
def delete_backup(filename):
    """API para eliminar un backup (opcional)"""
    try:
        backup_dir = get_backup_dir()
        filepath = os.path.join(backup_dir, secure_filename(filename))
        
        if not os.path.exists(filepath):
            return api_response(False, 'Archivo no encontrado', status_code=404)
            
        os.remove(filepath)
        return api_response(True, 'Respaldo eliminado exitosamente')
    except Exception as e:
        return api_response(False, f'Error al eliminar: {str(e)}', status_code=500)