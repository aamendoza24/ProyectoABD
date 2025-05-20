from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta
import bcrypt
import sqlite3
from app.utils.db import get_db_connection
from app.utils.email import generate_token, send_password_reset_email
from app.utils import login_required
from app.blueprints.auth import auth_bp



@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        # Si el usuario ya está autenticado, redirigir al dashboard
        if session.get('user_id'):
            return redirect(url_for('dashboard.index'))
        return render_template('auth/login.html', current_year=datetime.now().year)

    # Procesar el formulario de login
    username = request.form.get("username")
    password = request.form.get("password")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Buscar al usuario por nombre de usuario
        cursor.execute("""
            SELECT id, user, email, contrasena, role, is_active, 
                   failed_login_attempts, account_locked, locked_until 
            FROM usuarios 
            WHERE user = ?
        """, (username,))
        user = cursor.fetchone()
        
        # Si no se encuentra el usuario
        if not user:
            flash("Usuario no encontrado.", "danger")
            return render_template('auth/login.html', current_year=datetime.now().year)
        
        # Verificar si la cuenta está activa
        if not user['is_active']:
            flash("Esta cuenta ha sido desactivada. Contacta al administrador.", "danger")
            return render_template('auth/login.html', current_year=datetime.now().year)
        
        # Verificar si la cuenta está bloqueada
        if user['account_locked']:
            # Verificar si el tiempo de bloqueo ha expirado
            if user['locked_until'] and datetime.now() > datetime.strptime(user['locked_until'], '%Y-%m-%d %H:%M:%S'):
                # Desbloquear la cuenta
                cursor.execute("""
                    UPDATE usuarios 
                    SET account_locked = 0, failed_login_attempts = 0, locked_until = NULL 
                    WHERE id = ?
                """, (user['id'],))
                conn.commit()
            else:
                # Calcular tiempo restante de bloqueo
                if user['locked_until']:
                    lock_time = datetime.strptime(user['locked_until'], '%Y-%m-%d %H:%M:%S')
                    remaining_minutes = max(0, int((lock_time - datetime.now()).total_seconds() / 60))
                    flash(f"Tu cuenta está bloqueada debido a múltiples intentos fallidos. Intenta nuevamente en {remaining_minutes} minutos.", "danger")
                else:
                    flash("Tu cuenta está bloqueada debido a múltiples intentos fallidos. Contacta al administrador.", "danger")
                return render_template('auth/login.html', current_year=datetime.now().year)
        
        # Verificar la contraseña
        stored_hashed_password = user["contrasena"]
        if isinstance(stored_hashed_password, str):
            stored_hashed_password = stored_hashed_password.encode('utf-8')
        
        if bcrypt.checkpw(password.encode('utf-8'), stored_hashed_password):
            # Restablecer contador de intentos fallidos
            cursor.execute("""
                UPDATE usuarios 
                SET failed_login_attempts = 0, last_login = ? 
                WHERE id = ?
            """, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user['id']))
            conn.commit()
            
            # Establecer variables de sesión
            session['user_id'] = user['id']
            session['username'] = user['user']
            session['email'] = user['email']
            session['role'] = user['role']
            
            #flash("Inicio de sesión exitoso.", "success")
            return redirect(url_for('dashboard.index'))
        else:
            # Incrementar contador de intentos fallidos
            failed_attempts = user['failed_login_attempts'] + 1
            
            # Definir el número máximo de intentos permitidos
            max_attempts = 5
            
            if failed_attempts >= max_attempts:
                # Bloquear la cuenta por 30 minutos
                lock_duration = 30  # minutos
                locked_until = datetime.now() + timedelta(minutes=lock_duration)
                
                cursor.execute("""
                    UPDATE usuarios 
                    SET failed_login_attempts = ?, account_locked = 1, locked_until = ? 
                    WHERE id = ?
                """, (failed_attempts, locked_until.strftime('%Y-%m-%d %H:%M:%S'), user['id']))
                
                flash(f"Tu cuenta ha sido bloqueada por {lock_duration} minutos debido a múltiples intentos fallidos de inicio de sesión.", "danger")
            else:
                # Actualizar contador de intentos fallidos
                cursor.execute("""
                    UPDATE usuarios 
                    SET failed_login_attempts = ? 
                    WHERE id = ?
                """, (failed_attempts, user['id']))
                
                remaining_attempts = max_attempts - failed_attempts
                flash(f"Contraseña incorrecta. Te quedan {remaining_attempts} intentos antes de que tu cuenta sea bloqueada.", "danger")
            
            conn.commit()
            return render_template('auth/login.html', current_year=datetime.now().year)
    
    except Exception as e:
        flash(f"Error al procesar la solicitud: {str(e)}", "danger")
        return render_template('auth/login.html', current_year=datetime.now().year)
    finally:
        if conn:
            conn.close()


@auth_bp.route("/logout", methods=['POST'])
def logout():
    """Cerrar sesión de usuario"""
    session.clear()
    #flash("Has cerrado sesión correctamente.", "success")
    return redirect(url_for('auth.login'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        return render_template('auth/forgot_password.html', current_year=datetime.now().year)

    email = request.form.get('email')

    if not email:
        flash("Por favor, ingresa tu correo electrónico.", "danger")
        return render_template('auth/forgot_password.html', current_year=datetime.now().year)

    try:
        print("[INFO] Conectando a la base de datos...")
        conn = get_db_connection()
        cursor = conn.cursor()

        print(f"[INFO] Buscando usuario con email: {email}")
        cursor.execute("SELECT id, email FROM usuarios WHERE email = ?", (email,))
        user = cursor.fetchone()

        if not user:
            print("[INFO] Usuario no encontrado (correo no registrado o error tipográfico).")
            flash("Si tu correo está registrado, recibirás un enlace para restablecer tu contraseña.", "success")
            return render_template('auth/forgot_password.html', current_year=datetime.now().year)

        # Generar token
        token = generate_token()
        expiry = datetime.now() + timedelta(hours=24)
        print(f"[INFO] Token generado: {token}")
        print(f"[INFO] Token expirará el: {expiry}")

        # Guardar token en la base de datos
        print("[INFO] Guardando token en la base de datos...")
        cursor.execute("""
            UPDATE usuarios 
            SET reset_token = ?, reset_token_expiry = ? 
            WHERE id = ?
        """, (token, expiry.strftime('%Y-%m-%d %H:%M:%S'), user['id']))
        conn.commit()

        # Enviar correo
        print("[INFO] Enviando correo de recuperación...")
        send_password_reset_email(user['email'], token)
        print("[INFO] Correo enviado exitosamente.")

        flash("Se ha enviado un enlace de recuperación a tu correo electrónico.", "success")
        return redirect(url_for('auth.login'))

    except Exception as e:
        print(f"[ERROR] Falló el proceso de recuperación: {str(e)}")
        flash(f"Error al procesar la solicitud. Verifica que el servidor de correo esté funcionando y que haya conexión con la base de datos.", "danger")
        return render_template('auth/forgot_password.html', current_year=datetime.now().year)

    finally:
        if 'conn' in locals() and conn:
            conn.close()
            print("[INFO] Conexión cerrada.")


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if not token:
        flash("Enlace de recuperación inválido.", "danger")
        return redirect(url_for('auth.login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar si el token existe y no ha expirado
        cursor.execute("""
            SELECT id, reset_token_expiry 
            FROM usuarios 
            WHERE reset_token = ?
        """, (token,))
        user = cursor.fetchone()
        
        if not user:
            flash("Enlace de recuperación inválido o expirado.", "danger")
            return redirect(url_for('auth.login'))
        
        # Verificar si el token ha expirado
        expiry = datetime.strptime(user['reset_token_expiry'], '%Y-%m-%d %H:%M:%S')
        if datetime.now() > expiry:
            flash("El enlace de recuperación ha expirado. Solicita uno nuevo.", "danger")
            return redirect(url_for('auth.forgot_password'))
        
        if request.method == 'GET':
            return render_template('auth/reset_password.html', token=token, current_year=datetime.now().year)
        
        # Procesar el formulario de restablecimiento
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not password or not confirm_password:
            flash("Por favor, completa todos los campos.", "danger")
            return render_template('auth/reset_password.html', token=token, current_year=datetime.now().year)
        
        if password != confirm_password:
            flash("Las contraseñas no coinciden.", "danger")
            return render_template('auth/reset_password.html', token=token, current_year=datetime.now().year)
        
        # Validar fortaleza de la contraseña
        if len(password) < 8:
            flash("La contraseña debe tener al menos 8 caracteres.", "danger")
            return render_template('auth/reset_password.html', token=token, current_year=datetime.now().year)
        
        if not (any(c.islower() for c in password) and 
                any(c.isupper() for c in password) and 
                any(c.isdigit() for c in password) and 
                any(not c.isalnum() for c in password)):
            flash("La contraseña debe contener al menos una letra minúscula, una letra mayúscula, un número y un carácter especial.", "danger")
            return render_template('auth/reset_password.html', token=token, current_year=datetime.now().year)
        
        # Actualizar la contraseña
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        cursor.execute("""
            UPDATE usuarios 
            SET contrasena = ?, reset_token = NULL, reset_token_expiry = NULL 
            WHERE id = ?
        """, (hashed_password, user['id']))
        conn.commit()
        
        flash("Tu contraseña ha sido restablecida correctamente. Ahora puedes iniciar sesión.", "success")
        return redirect(url_for('auth.login'))
    
    except Exception as e:
        flash(f"Error al procesar la solicitud: {str(e)}", "danger")
        return render_template('auth/reset_password.html', token=token, current_year=datetime.now().year)
    finally:
        if conn:
            conn.close()