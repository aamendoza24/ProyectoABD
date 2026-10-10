from app.repositories.usuario_repository import UsuarioRepository
from app.utils.email import generate_token, send_password_reset_email
import bcrypt
from datetime import datetime, timedelta

class AuthService:
    """Maneja la lógica de validación de autenticación y seguridad de usuarios"""

    @staticmethod
    def verificar_login(username, password_no_hasheado):
        """
        Devuelve un tupla: (boolean_success, string_message, dict_user_data)
        """
        user = UsuarioRepository.obtener_usuario_por_username(username)
        
        if not user:
            return False, "Usuario no encontrado.", None
            
        if not user.get('is_active'):
            return False, "Esta cuenta ha sido desactivada. Contacta al administrador.", None
        
        # Verificar estado de bloqueo temporal
        if user.get('account_locked'):
            locked_until_str = user.get('locked_until')
            if locked_until_str:
                locked_until_dt = datetime.strptime(locked_until_str, '%Y-%m-%d %H:%M:%S')
                if datetime.now() > locked_until_dt:
                    # Desbloquear porque expiró el castigo
                    UsuarioRepository.actualizar_estado_bloqueo(user['id'], 0, False, None)
                else:
                    remaining = max(0, int((locked_until_dt - datetime.now()).total_seconds() / 60))
                    return False, f"Tu cuenta está bloqueada debido a múltiples intentos fallidos. Intenta nuevamente en {remaining} minutos.", None
            else:
                return False, "Tu cuenta está bloqueada debido a múltiples intentos fallidos. Contacta al administrador.", None
        
        stored_hash = user["contrasena"]
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode('utf-8')
            
        if bcrypt.checkpw(password_no_hasheado.encode('utf-8'), stored_hash):
            UsuarioRepository.actualizar_logeo_exitoso(user['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            session_data = {
                'user_id': user['id'],
                'username': user['user'],
                'email': user['email'],
                'role': user['role']
            }
            return True, "Inicio de sesión exitoso.", session_data
        else:
            intentos_fallidos = (user.get('failed_login_attempts') or 0) + 1
            max_attempts = 5
            
            if intentos_fallidos >= max_attempts:
                lock_duration = 30 # minutos
                locked_until = (datetime.now() + timedelta(minutes=lock_duration)).strftime('%Y-%m-%d %H:%M:%S')
                UsuarioRepository.actualizar_estado_bloqueo(user['id'], intentos_fallidos, True, locked_until)
                return False, f"Tu cuenta ha sido bloqueada por {lock_duration} minutos por intentos fallidos.", None
            else:
                UsuarioRepository.actualizar_estado_bloqueo(user['id'], intentos_fallidos, False, user.get('locked_until'))
                return False, f"Contraseña incorrecta. Te quedan {max_attempts - intentos_fallidos} intentos.", None

    @staticmethod
    def iniciar_recuperacion_contrasena(email):
        user = UsuarioRepository.obtener_usuario_por_email(email)
        if not user:
            # Por seguridad, no decimos si existe o no existe, solo lanzamos success abstract
            return True, "Si tu correo está registrado, recibirás un enlace de restablecimiento."
            
        token = generate_token()
        expiry = datetime.now() + timedelta(hours=24)
        UsuarioRepository.actualizar_token_recuperacion(user['id'], token, expiry.strftime('%Y-%m-%d %H:%M:%S'))
        
        try:
            send_password_reset_email(user['email'], token)
            return True, "Se ha enviado un enlace de recuperación a tu correo electrónico."
        except Exception as e:
            raise Exception(f"No se pudo enviar el correo: {str(e)}")

    @staticmethod
    def procesar_reseteo_contrasena(token, password, confirm_password):
        if not token:
            return False, "Enlace inválido."
            
        user = UsuarioRepository.obtener_usuario_por_token(token)
        if not user:
            return False, "Enlace expirado o inválido."
            
        expiry = datetime.strptime(user['reset_token_expiry'], '%Y-%m-%d %H:%M:%S')
        if datetime.now() > expiry:
            return False, "El enlace de recuperación ha expirado. Solicita uno nuevo."
            
        if not password or not confirm_password:
            return False, "Completa todos los campos."
            
        if password != confirm_password:
            return False, "Las contraseñas no coinciden."
            
        if len(password) < 8:
            return False, "La contraseña debe tener al menos 8 caracteres."
            
        if not (any(c.islower() for c in password) and 
                any(c.isupper() for c in password) and 
                any(c.isdigit() for c in password) and 
                any(not c.isalnum() for c in password)):
            return False, "La contraseña debe contener al menos minúscula, maxúscula, número y símbolo."
            
        hashed_pass = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        UsuarioRepository.actualizar_contrasena(user['id'], hashed_pass)
        return True, "Tu contraseña ha sido restablecida correctamente."
