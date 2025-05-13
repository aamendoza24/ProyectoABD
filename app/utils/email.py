import secrets
from datetime import datetime
from flask import render_template, current_app, request
from flask_mail import Message
from app.extensions import mail

def generate_token():
    """Genera un token seguro para recuperación de contraseña"""
    return secrets.token_urlsafe(32)

def send_password_reset_email(user_email, token):
    """Envía un correo electrónico con el enlace para restablecer la contraseña"""
    msg = Message(
        subject="Recuperación de Contraseña - Librería",
        recipients=[user_email]
    )
    
    # Crear la URL de recuperación
    reset_url = f"{request.host_url.rstrip('/')}/auth/reset-password/{token}"
    
    # Contenido HTML del correo
    msg.html = render_template(
        'auth/email/reset_password.html',
        reset_url=reset_url,
        user_email=user_email
    )
    
    # Contenido de texto plano como alternativa
    msg.body = f"""
    Hola,
    
    Has solicitado restablecer tu contraseña. Haz clic en el siguiente enlace para continuar:
    
    {reset_url}
    
    Este enlace expirará en 24 horas.
    
    Si no solicitaste este cambio, puedes ignorar este correo y tu contraseña permanecerá sin cambios.
    
    Saludos,
    Equipo de Librería Indiana
    """
    
    # Enviar el correo
    mail.send(msg)