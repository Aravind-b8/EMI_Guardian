from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models.emi import EMI
from models.payment import Payment
from app import db
from sqlalchemy import select
from datetime import date

dashboard = Blueprint('dashboard', __name__)

@dashboard.route('/dashboard')
@login_required
def index():
    emis = db.session.execute(
        select(EMI).filter_by(user_id=current_user.id, is_active=True)
    ).scalars().all()

    total_outstanding = sum(e.remaining_amount() for e in emis)
    monthly_emi       = sum(e.emi_amount for e in emis)
    pending  = [e for e in emis if e.status == 'pending']
    paid     = [e for e in emis if e.status == 'paid']
    overdue  = [e for e in emis if e.status == 'overdue']
    upcoming = sorted(emis, key=lambda e: e.days_until_due())[:1]

    recent_payments = db.session.execute(
        select(Payment).where(user_id=current_user.id)
        .order_by(Payment.payment_date.desc()).limit(5)
    ).scalars().all()

    sorted_by_rate = sorted(emis, key=lambda e: e.interest_rate, reverse=True)
    today          = date.today()
    emi_days_map   = {e.emi_day: e for e in emis}

    return render_template('dashboard/index.html',
        emis=emis, total_outstanding=total_outstanding,
        monthly_emi=monthly_emi, pending=pending, paid=paid, overdue=overdue,
        upcoming=upcoming, recent_payments=recent_payments,
        sorted_by_rate=sorted_by_rate, emi_days_map=emi_days_map, today=today)


