from flask import Flask, render_template
from flask_session import Session
from flask_mail import Mail
from app.config import Config
from app.extensions import session, mail
from datetime import datetime

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Inicializar extensiones
    session.init_app(app)
    mail.init_app(app)
    
    # Registrar blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.dashboard import dashboard_bp
    from app.blueprints.ventas import ventas_bp
    from app.blueprints.compras import compras_bp
    from app.blueprints.inventario import inventario_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.reportes import reportes_bp
    from app.blueprints.backups import backup_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(ventas_bp)
    app.register_blueprint(compras_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(reportes_bp)
    app.register_blueprint(backup_bp)

    # Configuración de caché
    @app.after_request
    def add_header(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    
    # Manejo de errores


    
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500
    
    # Contexto global para plantillas
    @app.context_processor
    def inject_global_vars():
        return {
            'current_year': datetime.now().year
        }
    
    return app