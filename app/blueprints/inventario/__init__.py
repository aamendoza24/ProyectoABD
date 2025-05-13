from flask import Blueprint

inventario_bp = Blueprint('inventario', __name__, url_prefix='', 
                        template_folder='templates')

from app.blueprints.inventario.routes import *