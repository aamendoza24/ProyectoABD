from app.extensions import db

class BusinessRule(db.Model):
    __tablename__ = 'business_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), nullable=False, unique=True)
    value = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    type = db.Column(db.String(20), default='string') # string, integer, float, boolean
