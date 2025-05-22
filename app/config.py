import os
from datetime import timedelta

class Config:
    SECRET_KEY = 'tu_clave_secreta'  # En producción, usar variables de entorno
    SESSION_PERMANENT = False
    SESSION_TYPE = "filesystem"
    DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "library.db")
    
    # Configuración de correo electrónico
    MAIL_SERVER = 'smtp.gmail.com'  # Cambia según tu proveedor
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'aamendoza201@gmail.com'  # Cambia por tu correo
    MAIL_PASSWORD = 'tdeo aeyf jelg fwph'  # Usa contraseñas de aplicación para Gmail
    MAIL_DEFAULT_SENDER = ('Librería Indiana', 'aamendoza201@gmail.com')
    
    # Configuración de tokens
    TOKEN_EXPIRY = timedelta(hours=24)  # Tokens de recuperación válidos por 24 horas

