from extensions import db
from datetime import datetime

class Payment(db.Model):
    __tablename__ = 'payments'

    __table_args__ = {'extend_existing': True}
    id           = db.Column(db.Integer, primary_key=True)
    emi_id       = db.Column(db.Integer, db.ForeignKey('emis.id'),  nullable=False)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount       = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    mode         = db.Column(db.String(50), default='UPI')
    remarks      = db.Column(db.String(200), default='')
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
