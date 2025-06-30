from flask import Blueprint

backup_bp = Blueprint('backup', __name__, url_prefix='/backup', 
                        template_folder='templates',
                        static_folder='static')

from app.blueprints.backups.routes import *