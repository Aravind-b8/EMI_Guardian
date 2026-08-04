from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models.user import User
from models.emi import EMI
from models.payment import Payment
from app import db
from sqlalchemy import select, func
from functools import wraps

admin = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

@admin.route('/')
@login_required
@admin_required
def index():
    total_users     = db.session.execute(select(func.count(User.id)).filter_by(is_admin=False)).scalar()
    total_emis      = db.session.execute(select(func.count(EMI.id)).filter_by(is_active=True)).scalar()
    total_payments  = db.session.execute(select(func.count(Payment.id))).scalar()
    total_amount    = db.session.execute(select(func.sum(Payment.amount))).scalar() or 0
    overdue_emis    = db.session.execute(select(func.count(EMI.id)).filter_by(status='overdue', is_active=True)).scalar()
    pending_emis    = db.session.execute(select(func.count(EMI.id)).filter_by(status='pending', is_active=True)).scalar()
    paid_emis       = db.session.execute(select(func.count(EMI.id)).filter_by(status='paid',    is_active=True)).scalar()
    recent_users    = db.session.execute(select(User).filter_by(is_admin=False).order_by(User.created_at.desc()).limit(5)).scalars().all()
    recent_payments = db.session.execute(select(Payment).order_by(Payment.payment_date.desc()).limit(8)).scalars().all()
    users           = db.session.execute(select(User).filter_by(is_admin=False)).scalars().all()
    emi_by_cat      = db.session.execute(
        select(EMI.category, func.count(EMI.id), func.sum(EMI.emi_amount))
        .filter_by(is_active=True).group_by(EMI.category)
    ).all()
    return render_template('admin/index.html',
        total_users=total_users, total_emis=total_emis,
        total_payments=total_payments, total_amount=total_amount,
        overdue_emis=overdue_emis, pending_emis=pending_emis, paid_emis=paid_emis,
        recent_users=recent_users, recent_payments=recent_payments,
        users=users, emi_by_cat=emi_by_cat)

@admin.route('/users')
@login_required
@admin_required
def users():
    q     = request.args.get('q','').strip()
    stmt  = select(User).filter_by(is_admin=False)
    if q:
        stmt = select(User).filter(
            User.is_admin == False,
            (User.name.ilike(f'%{q}%') | User.email.ilike(f'%{q}%'))
        )
    all_users = db.session.execute(stmt.order_by(User.created_at.desc())).scalars().all()
    return render_template('admin/users.html', users=all_users, q=q)

@admin.route('/users/<int:user_id>')
@login_required
@admin_required
def user_detail(user_id):
    user     = db.session.get(User, user_id)
    if not user: flash('User not found.','danger'); return redirect(url_for('admin.users'))
    emis     = db.session.execute(select(EMI).filter_by(user_id=user_id, is_active=True)).scalars().all()
    payments = db.session.execute(select(Payment).filter_by(user_id=user_id).order_by(Payment.payment_date.desc())).scalars().all()
    return render_template('admin/user_detail.html', user=user, emis=emis, payments=payments)

@admin.route('/users/<int:user_id>/edit', methods=['GET','POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = db.session.get(User, user_id)
    if not user: flash('User not found.','danger'); return redirect(url_for('admin.users'))
    if request.method == 'POST':
        user.name           = request.form.get('name', user.name).strip()
        user.email          = request.form.get('email', user.email).strip().lower()
        user.occupation     = request.form.get('occupation','').strip()
        user.monthly_income = float(request.form.get('monthly_income', 0) or 0)
        user.salary_date    = int(request.form.get('salary_date', 1) or 1)
        new_pw = request.form.get('new_password','').strip()
        if new_pw and len(new_pw) >= 6:
            user.set_password(new_pw)
        db.session.commit()
        flash(f'User "{user.name}" updated!', 'success')
        return redirect(url_for('admin.user_detail', user_id=user.id))
    return render_template('admin/edit_user.html', user=user)

@admin.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    user = db.session.get(User, user_id)
    if not user: flash('User not found.','danger'); return redirect(url_for('admin.users'))
    user.is_active_account = not user.is_active_account
    db.session.commit()
    flash(f'User {user.name} {"activated" if user.is_active_account else "deactivated"}.', 'success')
    return redirect(url_for('admin.users'))

@admin.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user: flash('User not found.','danger'); return redirect(url_for('admin.users'))
    db.session.delete(user)
    db.session.commit()
    flash(f'User "{user.name}" deleted.', 'success')
    return redirect(url_for('admin.users'))

@admin.route('/emis')
@login_required
@admin_required
def all_emis():
    status = request.args.get('status','all')
    stmt   = select(EMI).filter_by(is_active=True)
    if status != 'all':
        stmt = select(EMI).filter_by(is_active=True, status=status)
    emis = db.session.execute(stmt.order_by(EMI.status)).scalars().all()
    return render_template('admin/emis.html', emis=emis, status=status)

@admin.route('/emis/<int:emi_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_emi(emi_id):
    e = db.session.get(EMI, emi_id)
    if not e: flash('EMI not found.','danger'); return redirect(url_for('admin.all_emis'))
    e.is_active = False
    db.session.commit()
    flash(f'EMI "{e.name}" removed.', 'success')
    return redirect(url_for('admin.all_emis'))

@admin.route('/payments')
@login_required
@admin_required
def all_payments():
    payments = db.session.execute(
        select(Payment).order_by(Payment.payment_date.desc())
    ).scalars().all()
    return render_template('admin/payments.html', payments=payments)
