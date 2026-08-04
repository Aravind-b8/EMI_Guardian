from extensions import db
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

class EMI(db.Model):
    __tablename__ = 'emis'

    __table_args__ = {'extend_existing': True}
    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name             = db.Column(db.String(100), nullable=False)
    category         = db.Column(db.String(50),  nullable=False)
    loan_amount      = db.Column(db.Float, nullable=False)
    interest_rate    = db.Column(db.Float, nullable=False)
    duration_months  = db.Column(db.Integer, nullable=False)
    emi_amount       = db.Column(db.Float, nullable=False)
    emi_day          = db.Column(db.Integer, default=1)
    start_date       = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status           = db.Column(db.String(20), default='pending')
    paid_months      = db.Column(db.Integer, default=0)
    is_active        = db.Column(db.Boolean, default=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    notes            = db.Column(db.Text, default='')

    payments = db.relationship('Payment', backref='emi', lazy=True, cascade='all, delete-orphan')

    def remaining_months(self):
        return max(0, self.duration_months - self.paid_months)

    def remaining_amount(self):
        return round(self.emi_amount * self.remaining_months(), 2)

    def progress_pct(self):
        if self.duration_months == 0: return 0
        return round(self.paid_months / self.duration_months * 100, 1)

    def end_date(self):
        return self.start_date + relativedelta(months=self.duration_months)

    def total_interest(self):
        return round(self.emi_amount * self.duration_months - self.loan_amount, 2)

    def next_due_date(self):
        today = date.today()
        due = date(today.year, today.month, min(self.emi_day, 28))
        if due < today:
            due = due + relativedelta(months=1)
        return due

    def days_until_due(self):
        return (self.next_due_date() - date.today()).days

    def category_icon(self):
        return {'Bike':'🏍️','Home':'🏠','Car':'🚗','Mobile':'📱',
                'Education':'🎓','Personal':'👤','Credit Card':'💳','Others':'📦'}.get(self.category,'💰')
