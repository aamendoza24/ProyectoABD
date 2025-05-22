from functools import wraps
from flask import session, redirect, url_for, flash, abort

def login_required(f):
    """
    Decorador para requerir inicio de sesión.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            #flash("Debes iniciar sesión para acceder a esta página.", "danger")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    """
    Decorador para requerir roles específicos.
    Uso: @role_required(['admin', 'gerente'])
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get("user_id") is None:
                #flash("Debes iniciar sesión para acceder a esta página.", "danger")
                return redirect(url_for('auth.login'))
            
            user_role = session.get("role")
            if user_role not in roles and user_role != 'admin':

                #flash("No tienes permiso para acceder a esta página.", "danger")
                abort(403)  # Forbidden
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator