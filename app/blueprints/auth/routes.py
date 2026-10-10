from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from app.services.auth_service import AuthService
from app.blueprints.auth import auth_bp

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if session.get('user_id'):
            return redirect(url_for('dashboard.index'))
        return render_template('auth/login.html', current_year=datetime.now().year)

    username = request.form.get("username")
    password = request.form.get("password")
    
    try:
        success, message, session_data = AuthService.verificar_login(username, password)
        if success:
            for k, v in session_data.items():
                session[k] = v
            #flash(message, "success")
            return redirect(url_for('dashboard.index'))
        else:
            flash(message, "danger")
            return render_template('auth/login.html', current_year=datetime.now().year)
    except Exception as e:
        flash(f"Error al procesar la solicitud: {str(e)}", "danger")
        return render_template('auth/login.html', current_year=datetime.now().year)

@auth_bp.route("/logout", methods=['POST'])
def logout():
    session.clear()
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
        success, message = AuthService.iniciar_recuperacion_contrasena(email)
        if success:
            flash(message, "success")
            return redirect(url_for('auth.login'))
        else:
            flash(message, "danger")
            return render_template('auth/forgot_password.html', current_year=datetime.now().year)
    except Exception as e:
        flash(f"Error al procesar la solicitud: {str(e)}", "danger")
        return render_template('auth/forgot_password.html', current_year=datetime.now().year)

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if not token:
        flash("Enlace de recuperación inválido.", "danger")
        return redirect(url_for('auth.login'))
    
    if request.method == 'GET':
        return render_template('auth/reset_password.html', token=token, current_year=datetime.now().year)
        
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    
    try:
        success, message = AuthService.procesar_reseteo_contrasena(token, password, confirm_password)
        if success:
            flash(message, "success")
            return redirect(url_for('auth.login'))
        else:
            flash(message, "danger")
            return render_template('auth/reset_password.html', token=token, current_year=datetime.now().year)
    except Exception as e:
        flash(f"Error al procesar la solicitud: {str(e)}", "danger")
        return render_template('auth/reset_password.html', token=token, current_year=datetime.now().year)