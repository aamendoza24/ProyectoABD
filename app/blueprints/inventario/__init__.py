from flask import Blueprint

inventario_bp = Blueprint('inventario', __name__, url_prefix='/inventario', 
                        template_folder='templates')

from app.blueprints.inventario.routes import *