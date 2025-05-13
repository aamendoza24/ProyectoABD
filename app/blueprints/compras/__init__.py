from flask import Blueprint

compras_bp = Blueprint('compras', __name__, url_prefix='', 
                        template_folder='templates')

from app.blueprints.compras.routes import *