from flask import Blueprint

ventas_bp = Blueprint('ventas', __name__, url_prefix='', 
                        template_folder='templates')

from app.blueprints.ventas.routes import *