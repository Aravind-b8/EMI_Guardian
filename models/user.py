from extensions import db, bcrypt
from flask_login import UserMixin
from datetime import datetime

class User(db.Model, UserMixin):
    __tablename__ = 'users'

    __table_args__ = {'extend_existing': True}
    id                = db.Column(db.Integer, primary_key=True)
    name              = db.Column(db.String(100), nullable=False)
    email             = db.Column(db.String(120), unique=True, nullable=False)
    password_hash     = db.Column(db.String(256), nullable=False, default='')
    is_admin          = db.Column(db.Boolean, default=False)
    monthly_income    = db.Column(db.Float, default=0)
    occupation        = db.Column(db.String(100), default='')
    salary_date       = db.Column(db.Integer, default=1)
    reminder_time     = db.Column(db.String(10), default='09:00')
    email_notif       = db.Column(db.Boolean, default=True)
    whatsapp_notif    = db.Column(db.Boolean, default=False)
    sms_notif         = db.Column(db.Boolean, default=False)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)
    is_active_account = db.Column(db.Boolean, default=True)

    emis     = db.relationship('EMI',     backref='user', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)

    def total_emi(self):
        return sum(e.emi_amount for e in self.emis if e.is_active)

    def emi_ratio(self):
        return round(self.total_emi() / self.monthly_income * 100, 1) if self.monthly_income > 0 else 0

    def health_score(self):
        ratio   = self.emi_ratio()
        overdue = sum(1 for e in self.emis if e.status == 'overdue')
        score   = 100
        if ratio > 50:   score -= 30
        elif ratio > 35: score -= 15
        score -= overdue * 10
        return max(10, min(100, score))
