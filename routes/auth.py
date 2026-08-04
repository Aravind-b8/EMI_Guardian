from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models.user import User
from app import db
from sqlalchemy import select

auth = Blueprint('auth', __name__)

@auth.route('/', methods=['GET', 'POST'])
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.index') if current_user.is_admin else url_for('dashboard.index'))
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = db.session.execute(
            select(User).filter_by(email=email)
        ).scalar_one_or_none()
        if user and user.check_password(password):
            if not user.is_active_account:
                flash('Your account is deactivated. Contact admin.', 'danger')
                return render_template('auth/login.html')
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or (
                url_for('admin.index') if user.is_admin else url_for('dashboard.index')
            ))
        flash('Invalid email or password. Please try again.', 'danger')
    return render_template('auth/login.html')

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        income   = request.form.get('monthly_income', 0)
        if not name or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('auth/register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('auth/register.html')
        existing = db.session.execute(
            select(User).filter_by(email=email)
        ).scalar_one_or_none()
        if existing:
            flash('Email already registered. Please login.', 'danger')
            return render_template('auth/register.html')
        user = User(
            name=name,
            email=email,
            phone=phone,
            whatsapp_number=phone,
            monthly_income=float(income or 0)
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f'Welcome, {name}! Your account is ready.', 'success')
        return redirect(url_for('dashboard.index'))
    return render_template('auth/register.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('auth.login'))
