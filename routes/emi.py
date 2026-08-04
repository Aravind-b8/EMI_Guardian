from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models.emi import EMI
from models.payment import Payment
from app import db
from sqlalchemy import select
from datetime import datetime
import math

emi_bp = Blueprint('emi_bp', __name__)

def calc_emi(P, r, n):
    if not P or not n: return 0
    R = r / (12 * 100)
    if R == 0: return P / n
    return P * R * math.pow(1+R, n) / (math.pow(1+R, n) - 1)

@emi_bp.route('/emis')
@login_required
def list_emis():
    status = request.args.get('status', 'all')
    stmt = select(EMI).filter_by(user_id=current_user.id, is_active=True)
    if status != 'all':
        stmt = select(EMI).filter_by(user_id=current_user.id, is_active=True, status=status)
    stmt = stmt.order_by(EMI.emi_day)
    emis = db.session.execute(stmt).scalars().all()
    return render_template('emi/list.html', emis=emis, status=status)

@emi_bp.route('/emis/add', methods=['GET','POST'])
@login_required
def add_emi():
    if request.method == 'POST':
        P = float(request.form.get('loan_amount', 0) or 0)
        r = float(request.form.get('interest_rate', 0) or 0)
        n = int(request.form.get('duration_months', 0) or 0)
        if not P or not r or not n:
            flash('Please fill all required fields.', 'danger')
            return render_template('emi/add.html')
        emi_amt = calc_emi(P, r, n)
        start   = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
        new_emi = EMI(
            user_id=current_user.id,
            name=request.form.get('name','').strip(),
            category=request.form.get('category','Others'),
            loan_amount=P, interest_rate=r, duration_months=n,
            emi_amount=round(emi_amt, 2),
            emi_day=int(request.form.get('emi_day', 1) or 1),
            start_date=start,
            notes=request.form.get('notes','').strip()
        )
        db.session.add(new_emi)
        db.session.commit()
        flash(f'"{new_emi.name}" added! EMI: ₹{new_emi.emi_amount:,.0f}/month', 'success')
        return redirect(url_for('emi_bp.list_emis'))
    return render_template('emi/add.html')

@emi_bp.route('/emis/<int:emi_id>/pay', methods=['POST'])
@login_required
def mark_paid(emi_id):
    e = db.session.execute(
        select(EMI).filter_by(id=emi_id, user_id=current_user.id)
    ).scalar_one_or_none()
    
    if not e:
        flash('EMI not found.', 'danger')
        return redirect(url_for('emi_bp.list_emis'))
        
    mode = request.form.get('mode', 'UPI')
    remarks = request.form.get('remarks', 'Marked as paid')
    
    # 1. Record the current payment transaction into your payment logs table
    payment = Payment(
        emi_id=e.id, 
        user_id=current_user.id, 
        amount=e.emi_amount, 
        mode=mode, 
        remarks=remarks
    )
    db.session.add(payment)
    
    # 2. Increment the installment counter row tracker
    e.paid_months += 1
    
    # 🌟 FIXED STATUS ASSIGNMENT RULE: 
    # Force status to lowercase 'paid' right now so your dashboard boxes move it immediately!
    e.status = 'paid'
    
    # If the loan is entirely closed out, you can optionally set it inactive
    if e.paid_months >= e.duration_months:
        e.status = 'completed' # Marks total lifetime payoff
    
    db.session.commit()
    flash(f'✅ {e.name} payment of ₹{e.emi_amount:,.0f} recorded!', 'success')
    return redirect(request.referrer or url_for('emi_bp.list_emis'))

@emi_bp.route('/emis/<int:emi_id>/delete', methods=['POST'])
@login_required
def delete_emi(emi_id):
    e = db.session.execute(
        select(EMI).filter_by(id=emi_id, user_id=current_user.id)
    ).scalar_one_or_none()
    if not e:
        flash('EMI not found.', 'danger')
        return redirect(url_for('emi_bp.list_emis'))
    e.is_active = False
    db.session.commit()
    flash(f'"{e.name}" removed.', 'success')
    return redirect(url_for('emi_bp.list_emis'))

@emi_bp.route('/calculator')
@login_required
def calculator():
    return render_template('emi/calculator.html')

@emi_bp.route('/history')
@login_required
def history():
    payments = db.session.execute(
        select(Payment).filter_by(user_id=current_user.id)
        .order_by(Payment.payment_date.desc())
    ).scalars().all()
    return render_template('emi/history.html', payments=payments)
