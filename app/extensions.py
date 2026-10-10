from flask_session import Session
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy

session = Session()
mail = Mail()
db = SQLAlchemy()