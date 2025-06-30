import os
from datetime import timedelta

class Config:
    SECRET_KEY = 'tu_clave_secreta'  # En producción, usar variables de entorno
    SESSION_PERMANENT = False
    SESSION_TYPE = "filesystem"
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATABASE_PATH = os.path.join(BASE_DIR, 'library.db')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'  # Para compatibilidad con extensiones Flask
    
    # Configuración de backups
    BACKUP_FOLDER = os.path.join(BASE_DIR, 'backups')  # Carpeta donde se guardarán los backups
    MAX_BACKUPS = 10  # Número máximo de backups a mantener

    AUTO_BACKUP_ENABLED = True
    AUTO_BACKUP_TIME = '12:00'  # Formato HH:MM
    MAX_AUTO_BACKUPS = 10  # Número máximo de backups a conservar
    #BACKUP_FOLDER = os.path.join(os.path.dirname(__file__), 'backups')
    
    # Configuración de correo electrónico
    MAIL_SERVER = 'smtp.gmail.com'  # Cambia según tu proveedor
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'aamendoza201@gmail.com'  # Cambia por tu correo
    MAIL_PASSWORD = 'tdeo aeyf jelg fwph'  # Usa contraseñas de aplicación para Gmail
    MAIL_DEFAULT_SENDER = ('Librería Indiana', 'aamendoza201@gmail.com')
    
    # Configuración de tokens
    TOKEN_EXPIRY = timedelta(hours=24)  # Tokens de recuperación válidos por 24 horas
    
    # Configuración de optimización de rendimiento
    COMPRESS_MIMETYPES = [
        'text/html', 'text/css', 'text/xml', 'application/json', 'application/javascript',
        'text/javascript', 'application/xml+rss', 'text/plain'
    ]
    
    # Configuración de caché para archivos estáticos
    STATIC_CACHE_TIMEOUT = 31536000  # 1 año para fuentes
    CSS_JS_CACHE_TIMEOUT = 2592000   # 1 mes para CSS/JS
    IMAGE_CACHE_TIMEOUT = 604800     # 1 semana para imágenes
    
    # Configuración de compresión
    COMPRESS_LEVEL = 6  # Nivel de compresión (1-9)
    COMPRESS_MIN_SIZE = 500  # Tamaño mínimo para comprimir (bytes)

