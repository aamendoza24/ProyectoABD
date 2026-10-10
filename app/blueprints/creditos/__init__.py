from flask import Blueprint

creditos_bp = Blueprint('creditos', __name__, template_folder='templates', url_prefix='/creditos')

from . import routes
