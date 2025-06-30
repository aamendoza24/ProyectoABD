from flask import Blueprint

reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes', 
                        template_folder='templates')

from app.blueprints.reportes.routes import *
#from app.blueprints.reportes.reportes_dashboard import *