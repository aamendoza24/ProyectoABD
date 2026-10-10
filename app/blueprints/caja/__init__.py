from flask import Blueprint

caja_bp = Blueprint('caja', __name__, template_folder='templates')

from app.blueprints.caja import routes
