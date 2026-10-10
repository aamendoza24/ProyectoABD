from app import create_app
from app.extensions import db
from app.models import Cliente, Venta, Credit, CreditPayment, CashTurn, BusinessRule

app = create_app()

with app.app_context():
    # Creamos las tablas que no existen. 
    # SQLAlchemy no sobrescribirá Cliente ni Venta porque ignorará las ya existentes si omitimos drop_all().
    db.create_all()
    print("Tablas creadas con éxito.")
