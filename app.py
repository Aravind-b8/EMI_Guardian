from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, Blueprint
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from sqlalchemy import select, func, inspect
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import math, os, requests as req
import urllib.parse
import webbrowser
import requests
from datetime import date
from google import genai
import traceback
import os
import resend
from flask_apscheduler import APScheduler
import os
from dotenv import load_dotenv

load_dotenv()

# ── Extensions ──────────────────────────────────────────────────────────────
db           = SQLAlchemy()
bcrypt       = Bcrypt()
login_manager= LoginManager()

# ── Models ───────────────────────────────────────────────────────────────────
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id                = db.Column(db.Integer, primary_key=True)
    name              = db.Column(db.String(100), nullable=False)
    email             = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=True)
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
    emis     = db.relationship('EMI',     backref='user', lazy=True, cascade='all,delete-orphan')
    payments = db.relationship('Payment', backref='user', lazy=True, cascade='all,delete-orphan')

    def set_password(self, pw):   self.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')
    def check_password(self, pw): return bcrypt.check_password_hash(self.password_hash, pw)
    def total_emi(self):          return sum(e.emi_amount for e in self.emis if e.is_active)
    def emi_ratio(self):          return round(self.total_emi()/self.monthly_income*100,1) if self.monthly_income else 0
    def health_score(self):
        r=self.emi_ratio(); o=sum(1 for e in self.emis if e.status=='overdue')
        s=100
        if r>50: s-=30
        elif r>35: s-=15
        s-=o*10
        return max(10,min(100,s))

class EMI(db.Model):
    __tablename__ = 'emis'
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name            = db.Column(db.String(100), nullable=False)
    category        = db.Column(db.String(50), nullable=False)
    loan_amount     = db.Column(db.Float, nullable=False)
    interest_rate   = db.Column(db.Float, nullable=False)
    duration_months = db.Column(db.Integer, nullable=False)
    emi_amount      = db.Column(db.Float, nullable=False)
    emi_day         = db.Column(db.Integer, default=1)
    start_date      = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status          = db.Column(db.String(20), default='pending')
    paid_months     = db.Column(db.Integer, default=0)
    is_active       = db.Column(db.Boolean, default=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    notes           = db.Column(db.Text, default='')
    payments = db.relationship('Payment', backref='emi', lazy=True, cascade='all,delete-orphan')

    def remaining_months(self):  return max(0, self.duration_months - self.paid_months)
    def remaining_amount(self):  return round(self.emi_amount * self.remaining_months(), 2)
    def progress_pct(self):      return round(self.paid_months/self.duration_months*100,1) if self.duration_months else 0
    def end_date(self):          return self.start_date + relativedelta(months=self.duration_months)
    def total_interest(self):    return round(self.emi_amount*self.duration_months - self.loan_amount, 2)
    def next_due_date(self):
        today=date.today(); due=date(today.year,today.month,min(self.emi_day,28))
        if due<today: due+=relativedelta(months=1)
        return due
    def days_until_due(self):    return (self.next_due_date()-date.today()).days
    def category_icon(self):
        return {'Bike':'🏍️','Home':'🏠','Car':'🚗','Mobile':'📱',
                'Education':'🎓','Personal':'👤','Credit Card':'💳','Others':'📦'}.get(self.category,'💰')

class Payment(db.Model):
    __tablename__ = 'payments'
    id           = db.Column(db.Integer, primary_key=True)
    emi_id       = db.Column(db.Integer, db.ForeignKey('emis.id'),  nullable=False)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount       = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    mode         = db.Column(db.String(50), default='UPI')
    remarks      = db.Column(db.String(200), default='')
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)




# 📥 1. THE OUTBOUND CHANNELS (Real Workers)
# =====================================================================
# 🔔 DYNAMIC AUTOMATED NOTIFICATION & CRON CHECK ENGINE
# =====================================================================
import requests
from datetime import date, datetime

def send_email_via_resend(user_email, user_name, emi_name, emi_amount, due_date):
    """Sends a professional HTML transactional email alert using the Resend platform API."""
    # 🌟 CRITICAL ROUTE FIX: Points directly to the verified API delivery endpoint
    url = "https://resend.com"
    headers = {
        "Authorization": "Bearer re_YourActualResendAPIKeyHerePattern",  # 🌟 Replace with your live Resend API key
        "Content-Type": "application/json"
    }
    payload = {
        "from": "EMI Guardian <onboarding@resend.dev>",
        "to": [user_email],
        "subject": f"⏰ Reminder: Your {emi_name} EMI is due in 5 Days!",
        "html": f"""
        <h3>Hello {user_name},</h3>
        <p>This is an automated alert from your **EMI Guardian Portal**.</p>
        <p>Your upcoming installment for <strong>{emi_name}</strong> is scheduled in exactly 5 days.</p>
        <ul>
            <li><strong>Amount Due:</strong> ₹{emi_amount:,.2f}</li>
            <li><strong>Due Date:</strong> {due_date}</li>
        </ul>
        <p>Please ensure your account has sufficient balance to maintain a healthy credit score.</p>
        """
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        return response.status_code in [200, 201, 202]
    except Exception as e:
        print(f"❌ Resend API Dispatch Error: {e}")
        return False


def send_whatsapp_via_meta(phone_number, user_name, emi_name, emi_amount, due_date):
    """Logs an automated WhatsApp template tracking alert to the local system log console."""
    print(f"📱 [WhatsApp Log] Dispatched to {phone_number}: Hello {user_name}, your {emi_name} EMI of ₹{emi_amount} is due on {due_date}!")
    return True


def check_and_send_daily_reminders(): 
    """
    Scans account tables to look for installments falling exactly 5 days away from today.
    Fires notifications to outbound API channels strictly respecting user saved preference states.
    """ 
    print("--> [Scheduler] Executing daily 5-day advance notification scan...") 
    all_users = User.query.filter_by(is_active_account=True).all() 
    today = date.today() 
    alerts_dispatched = 0 
    
    for user in all_users: 
        for emi in user.emis: 
            if not emi.is_active or emi.status == 'paid': 
                continue 
                
            try: 
                due_year, due_month = today.year, today.month 
                if today.day > emi.emi_day: 
                    due_month = 1 if today.month == 12 else today.month + 1
                    due_year = today.year + 1 if today.month == 12 else today.year
                        
                import calendar 
                max_days = calendar.monthrange(due_year, due_month)[1]
                target_day = min(emi.emi_day, max_days) 
                next_due_date = date(due_year, due_month, target_day) 
                
                # Check if it satisfies the 5-day lead warning rule condition
                if (next_due_date - today).days == 5: 
                    due_str = next_due_date.strftime('%d-%b-%Y')
                    
                    # 📨 Channel 1: Execute Email via Resend if checked on profile page
                    if user.email_notif and user.email:
                        send_email_via_resend(user.email, user.name, emi.name, emi.emi_amount, due_str)
                        
                    # 📱 Channel 2: Execute WhatsApp Log if checked on profile page
                    if user.whatsapp_notif and user.whatsapp_number:
                        send_whatsapp_via_meta(user.whatsapp_number, user.name, emi.name, emi.emi_amount, due_str)
                        
                    alerts_dispatched += 1 
            except Exception as e: 
                print(f"Error calculating dates for EMI ID {emi.id}: {e}") 
                
    return alerts_dispatched


# Notification Blueprint
notification_bp = Blueprint('notification', __name__)
# 3. Existing force-cron-check route 
@notification_bp.route('/admin/force-cron-check') 
@login_required 
def force_cron_check(): 
    count = check_and_send_daily_reminders()
    flash(f"Manual check complete. Scan finished. Reminders sent: {count}", "info")
    return redirect(url_for('dashboard.index')) 



def seed():
    if 'users' not in inspect(db.engine).get_table_names(): return
    if db.session.execute(select(User)).first(): return
    admin = User(name='Admin',email='admin@emiguardian.com',is_admin=True,monthly_income=100000,occupation='Administrator')
    admin.set_password('admin123')
    db.session.add(admin)
    u = User(name='Rolex',email='rolex@email.com',is_admin=False,monthly_income=35000,occupation='Software Engineer')
    u.set_password('rolex123')
    db.session.add(u)
    db.session.flush()
    loans=[
        EMI(user_id=u.id,name='Personal Loan',  category='Personal',    loan_amount=150000, interest_rate=18,  duration_months=36, emi_amount=5040, emi_day=2, start_date=datetime(2025,10,1),paid_months=8, status='overdue'),
        EMI(user_id=u.id,name='Bike Loan',       category='Bike',        loan_amount=70000,  interest_rate=11,  duration_months=24, emi_amount=3400, emi_day=5, start_date=datetime(2025,4,1), paid_months=14,status='pending'),
        EMI(user_id=u.id,name='Home Loan',       category='Home',        loan_amount=2500000,interest_rate=8.5, duration_months=180,emi_amount=3950, emi_day=10,start_date=datetime(2021,7,1), paid_months=60,status='paid'),
        EMI(user_id=u.id,name='Education Loan',  category='Education',   loan_amount=120000, interest_rate=10,  duration_months=36, emi_amount=3960, emi_day=15,start_date=datetime(2025,12,1),paid_months=6, status='pending'),
        EMI(user_id=u.id,name='Mobile EMI',      category='Mobile',      loan_amount=22000,  interest_rate=14,  duration_months=12, emi_amount=2100, emi_day=20,start_date=datetime(2025,9,1), paid_months=10,status='paid'),
        EMI(user_id=u.id,name='Credit Card',     category='Credit Card', loan_amount=1500,   interest_rate=36,  duration_months=6,  emi_amount=300,  emi_day=25,start_date=datetime(2026,4,1), paid_months=2, status='pending'),
    ]
    for l in loans: db.session.add(l)
    db.session.flush()
    pays=[
        Payment(emi_id=loans[0].id,user_id=u.id,amount=5040,payment_date=datetime(2026,6,2), mode='Cash',       remarks='Late by 2 days'),
        Payment(emi_id=loans[1].id,user_id=u.id,amount=3400,payment_date=datetime(2026,6,5), mode='UPI',        remarks='On time'),
        Payment(emi_id=loans[2].id,user_id=u.id,amount=3950,payment_date=datetime(2026,6,10),mode='Net Banking',remarks='Auto-debit'),
        Payment(emi_id=loans[3].id,user_id=u.id,amount=3960,payment_date=datetime(2026,6,15),mode='UPI',        remarks='On time'),
        Payment(emi_id=loans[4].id,user_id=u.id,amount=2100,payment_date=datetime(2026,6,20),mode='UPI',        remarks='On time'),
    ]
    for p in pays: db.session.add(p)
    db.session.commit()
    print('✅ Demo data seeded.')

# =====================================================================
# 🌟 FORCED ABSOLUTE ROUTING ON NOTIFICATION BLUEPRINT
# ====================================================================

# 1. Blueprint Initialization

# =====================================================================
# 🌟 PERFECTLY ALIGNED DYNAMIC DATA-DRIVEN AI ADVISOR ENGINE
# =====================================================================
@login_required
def send_notification(user_id):
    target_user = User.query.get_or_404(user_id)
    total_due = target_user.total_emi()
    today_str = date.today().strftime('%d-%b-%Y')
    
    email_success = False
    whatsapp_success = False

    if target_user.email_notif:
        email_success = send_email_reminder(
            user_email=target_user.email,
            user_name=target_user.name,
            emi_amount=total_due,
            due_date=today_str
        )
        
    if target_user.whatsapp_notif:
        user_phone = getattr(target_user, 'phone', '919876543210') 
        whatsapp_success = send_whatsapp_redirect(
            phone_number=user_phone,
            user_name=target_user.name,
            emi_amount=total_due,
            due_date=today_str
        )
        
    if email_success or whatsapp_success:
        flash(f"Reminders processed successfully for {target_user.name}!", "success")
    else:
        flash("No notifications were sent. Check user notification preferences.", "info")
        
    return redirect(url_for('dashboard.index'))


# 3. Add the test route right below it 🌟
@notification_bp.route('/test-reminders')
def test_reminders():
    # 🌟 REMEMBER: Replace this email with your actual Resend account login email to test!
    test_email = "your_resend_signup_email@example.com"  
    test_phone = "919876543210"                          
    test_name = "Supriya (Test User)"
    test_amount = "5,000"
    test_date = date.today().strftime('%d-%b-%Y')

    email_status = send_email_reminder(test_email, test_name, test_amount, test_date)
    whatsapp_status = send_whatsapp_redirect(test_phone, test_name, test_amount, test_date)
    
    return f"<h1>Test Page</h1><p>Email Sent: {email_status} | WhatsApp Window Triggered: {whatsapp_status}</p>"


# 1. Initialize your free email API key (Sign up at resend.com to get your key)
resend_api_key = os.getenv("RESEND_API_KEY")

# 2. Pure Python Email Helper
def send_email_reminder(user_email, user_name, emi_amount, due_date):
    """Sends a professional HTML email via Resend API entirely from Python."""
    try:
        params = {
            "from": "EMI Guardian <onboarding@resend.dev>", # Resend free sandbox sender
            "to": user_email,
            "subject": "⚠️ Action Required: Upcoming EMI Reminder",
            "html": f"""
                <div style="font-family: Arial, sans-serif; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
                    <h2 style="color: #d9534f;">EMI Payment Reminder</h2>
                    <p>Dear {user_name},</p>
                    <p>This is an automated notification from <strong>EMI Guardian</strong> regarding your upcoming loan obligation.</p>
                    <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                        <tr>
                            <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Amount Due:</td>
                            <td style="padding: 8px; border: 1px solid #ddd; color: #5cb85c; font-weight: bold;">₹{emi_amount}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Due Date:</td>
                            <td style="padding: 8px; border: 1px solid #ddd;">{due_date}</td>
                        </tr>
                    </table>
                    <p>Please ensure your linked account has a sufficient balance to prevent bounce charges and protect your financial health score.</p>
                    <hr style="border: 0; border-top: 1px solid #eee;" />
                    <p style="font-size: 12px; color: #777;">Thank you for using EMI Guardian.</p>
                </div>
            """
        }
        resend.Emails.send(params)
        return True
    except Exception as e:
        print(f"Failed to send email to {user_email}: {e}")
        return False

# 3. Pure Python WhatsApp Helper
def send_whatsapp_redirect(phone_number, user_name, emi_amount, due_date):
    """Launches the default system browser to WhatsApp Web with a pre-filled payload."""
    try:
        # Standardize Indian phone number format (Remove + sign, add country prefix if missing)
        clean_phone = str(phone_number).strip().replace("+", "")
        if len(clean_phone) == 10:
            clean_phone = f"91{clean_phone}"
            
        message = f"Hello {user_name}, this is a reminder from EMI Guardian. Your EMI payment of Rs. {emi_amount} is due on {due_date}. Please process it to avoid penalty fees."
        
        # Safely URL encode message text using Python standard library
        encoded_message = urllib.parse.quote(message)
        whatsapp_url = f"https://whatsapp.com{clean_phone}&text={encoded_message}"
        
        # Triggers server/admin machine browser window natively
        webbrowser.open(whatsapp_url)
        return True
    except Exception as e:
        print(f"Failed to launch WhatsApp helper: {e}")
        return False
# 4. Flask Route to trigger the reminders based on User data


# ── Helper ────────────────────────────────────────────────────────────────────
def calc_emi(P,r,n):
    if not P or not n: return 0
    R=r/(12*100)
    if R==0: return P/n
    return P*R*math.pow(1+R,n)/(math.pow(1+R,n)-1)

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def dec(*a,**kw):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.','danger'); return redirect(url_for('auth.login'))
        return f(*a,**kw)
    return dec

# ── AUTH Blueprint ────────────────────────────────────────────────────────────
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/', methods=['GET','POST'])
@auth_bp.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.index') if current_user.is_admin else url_for('dashboard.index'))
    if request.method=='POST':
        email=request.form.get('email','').strip().lower()
        pw=request.form.get('password','')
        user=db.session.execute(select(User).where(User.email==email)).scalar_one_or_none()
        if user and user.check_password(pw):
            if not user.is_active_account:
                flash('Account deactivated. Contact admin.','danger')
                return render_template('auth/login.html')
            login_user(user,remember=True)
            nxt=request.args.get('next')
            return redirect(nxt or (url_for('admin.index') if user.is_admin else url_for('dashboard.index')))
        flash('Invalid email or password.','danger')
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET','POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('dashboard.index'))
    if request.method=='POST':
        name=request.form.get('name','').strip()
        email=request.form.get('email','').strip().lower()
        pw=request.form.get('password','')
        income=request.form.get('monthly_income',0)
        if not name or not email or not pw:
            flash('All fields required.','danger'); return render_template('auth/register.html')
        if len(pw)<6:
            flash('Password min 6 characters.','danger'); return render_template('auth/register.html')
        if db.session.execute(select(User).where(User.email==email)).scalar_one_or_none():
            flash('Email already registered.','danger'); return render_template('auth/register.html')
        user=User(name=name,email=email,monthly_income=float(income or 0))
        user.set_password(pw)
        db.session.add(user); db.session.commit()
        login_user(user)
        flash(f'Welcome, {name}!','success')
        return redirect(url_for('dashboard.index'))
    return render_template('auth/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user(); flash('Logged out.','info')
    return redirect(url_for('auth.login'))

# ── DASHBOARD Blueprint ───────────────────────────────────────────────────────
dash_bp = Blueprint('dashboard', __name__)
@dash_bp.route('/dashboard')
@login_required
def index():
    # 1. Fetch active EMI entries linked to the logged-in profile
    emis = db.session.execute(
        select(EMI).where(EMI.user_id == current_user.id, EMI.is_active == True)
    ).scalars().all()
    
    pending = [e for e in emis if e.status == 'pending']
    paid = [e for e in emis if e.status == 'paid']
    overdue = [e for e in emis if e.status == 'overdue']
    upcoming = sorted(emis, key=lambda e: e.days_until_due())[:1]
    
    recent_payments = db.session.execute(
        select(Payment).where(Payment.user_id == current_user.id)
        .order_by(Payment.payment_date.desc()).limit(5)
    ).scalars().all()
    
    sorted_by_rate = sorted(emis, key=lambda e: e.interest_rate, reverse=True)
    
    import calendar as cal
    today = date.today()
    days_in_month = cal.monthrange(today.year, today.month)[1]
    emi_days_map = {e.emi_day: e for e in emis}

    # 📊 2. CHART GENERATION LOGIC: Group total EMI value by category
    category_totals = {}
    for e in emis:
        cat_name = e.category if e.category else 'Other'
        category_totals[cat_name] = category_totals.get(cat_name, 0) + e.emi_amount
        
    total_monthly_emi = sum(category_totals.values())
    
    # Standard color palette designed for dark themes
    color_palette = ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b', '#858796']
    chart_slices = []
    current_percentage = 0
    
    if total_monthly_emi > 0:
        for idx, (cat_name, amt) in enumerate(category_totals.items()):
            slice_percentage = (amt / total_monthly_emi) * 100
            start_at = current_percentage
            end_at = current_percentage + slice_percentage
            current_percentage += slice_percentage
            
            chart_slices.append({
                'category': cat_name,
                'amount': amt,
                'percentage': round(slice_percentage, 1),
                'start': round(start_at, 2),
                'end': round(end_at, 2),
                'color': color_palette[idx % len(color_palette)]
            })

    return render_template(
        'dashboard/index.html', 
        emis=emis,
        total_outstanding=sum(e.remaining_amount() for e in emis), 
        monthly_emi=total_monthly_emi, 
        pending=pending,
        paid=paid,
        overdue=overdue,
        upcoming=upcoming, 
        recent_payments=recent_payments,
        sorted_by_rate=sorted_by_rate, 
        emi_days_map=emi_days_map,
        today=today,
        days_in_month=days_in_month,
        chart_slices=chart_slices # <-- Array mapped to template context
    )


@dash_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        form_type = request.form.get('form_type', 'profile')
        
        # 👤 1. PROFILE DETAILS FORM SUBMISSION
        if form_type == 'profile':
            current_user.name = request.form.get('name', current_user.name).strip()
            current_user.occupation = request.form.get('occupation', '').strip()
            current_user.monthly_income = float(request.form.get('monthly_income', 0) or 0)
            current_user.salary_date = int(request.form.get('salary_date', 1) or 1)
            current_user.reminder_time = request.form.get('reminder_time', '09:00')
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            
        # 🔔 2. NOTIFICATION CHANNELS TOGGLE SUBMISSION
        elif form_type == 'notifications':
            current_user.email_notif = 'email_notif' in request.form
            current_user.whatsapp_notif = 'whatsapp_notif' in request.form
            current_user.sms_notif = 'sms_notif' in request.form
            db.session.commit()
            flash('Notification preferences saved!', 'success')
            
        # 🔒 3. SECURITY PASSWORD UPDATION SUBMISSION
        elif form_type == 'password':
            current_pw = request.form.get('current_password', '')
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', '')
            
            if not current_user.check_password(current_pw):
                flash('Current password is incorrect.', 'danger')
            elif len(new_pw) < 6:
                flash('New password must be at least 6 characters.', 'danger')
            elif new_pw != confirm_pw:
                flash('Passwords do not match.', 'danger')
            else:
                current_user.set_password(new_pw)
                db.session.commit()
                flash('Password changed successfully!', 'success')
                
        return redirect(url_for('dashboard.profile'))
        
    return render_template('dashboard/profile.html')


# ── EMI Blueprint ─────────────────────────────────────────────────────────────
emi_bp = Blueprint('emi_bp', __name__)

@emi_bp.route('/emis')
@login_required
def list_emis():
    status=request.args.get('status','all')
    stmt=select(EMI).where(EMI.user_id==current_user.id,EMI.is_active==True)
    if status!='all': stmt=stmt.where(EMI.status==status)
    emis=db.session.execute(stmt.order_by(EMI.emi_day)).scalars().all()
    return render_template('emi/list.html',emis=emis,status=status)

@emi_bp.route('/emis/add',methods=['GET','POST'])
@login_required
def add_emi():
    if request.method=='POST':
        P=float(request.form.get('loan_amount',0) or 0)
        r=float(request.form.get('interest_rate',0) or 0)
        n=int(request.form.get('duration_months',0) or 0)
        if not P or not r or not n:
            flash('Fill all required fields.','danger'); return render_template('emi/add.html')
        start=datetime.strptime(request.form.get('start_date'),'%Y-%m-%d')
        e=EMI(user_id=current_user.id,name=request.form.get('name','').strip(),
              category=request.form.get('category','Others'),loan_amount=P,interest_rate=r,
              duration_months=n,emi_amount=round(calc_emi(P,r,n),2),
              emi_day=int(request.form.get('emi_day',1) or 1),start_date=start,
              notes=request.form.get('notes','').strip())
        db.session.add(e); db.session.commit()
        flash(f'"{e.name}" added! EMI: ₹{e.emi_amount:,.0f}/month','success')
        return redirect(url_for('emi_bp.list_emis'))
    return render_template('emi/add.html')

@emi_bp.route('/emis/<int:eid>/pay',methods=['POST'])
@login_required
def mark_paid(eid):
    e=db.session.execute(select(EMI).where(EMI.id==eid,EMI.user_id==current_user.id)).scalar_one_or_none()
    if not e: flash('Not found.','danger'); return redirect(url_for('emi_bp.list_emis'))
    db.session.add(Payment(emi_id=e.id,user_id=current_user.id,amount=e.emi_amount,
                           mode=request.form.get('mode','UPI'),
                           remarks=request.form.get('remarks','Paid')))
    e.paid_months+=1
    e.status='paid' if e.paid_months>=e.duration_months else 'pending'
    db.session.commit(); flash(f'✅ {e.name} ₹{e.emi_amount:,.0f} recorded!','success')
    return redirect(request.referrer or url_for('emi_bp.list_emis'))

@emi_bp.route('/emis/<int:eid>/delete',methods=['POST'])
@login_required
def delete_emi(eid):
    e=db.session.execute(select(EMI).where(EMI.id==eid,EMI.user_id==current_user.id)).scalar_one_or_none()
    if not e: flash('Not found.','danger'); return redirect(url_for('emi_bp.list_emis'))
    e.is_active=False; db.session.commit(); flash(f'"{e.name}" removed.','success')
    return redirect(url_for('emi_bp.list_emis'))

@emi_bp.route('/calculator')
@login_required
def calculator(): return render_template('emi/calculator.html')

@emi_bp.route('/history')
@login_required
def history():
    pays=db.session.execute(select(Payment).where(Payment.user_id==current_user.id).order_by(Payment.payment_date.desc())).scalars().all()
    return render_template('emi/history.html',payments=pays)

# ── ADMIN Blueprint ───────────────────────────────────────────────────────────
admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/')
@login_required
@admin_required
def index():
    users=db.session.execute(select(User).where(User.is_admin==False)).scalars().all()
    total_emis    =db.session.execute(select(func.count(EMI.id)).where(EMI.is_active==True)).scalar()
    total_payments=db.session.execute(select(func.count(Payment.id))).scalar()
    total_amount  =db.session.execute(select(func.sum(Payment.amount))).scalar() or 0
    overdue_emis  =db.session.execute(select(func.count(EMI.id)).where(EMI.status=='overdue',EMI.is_active==True)).scalar()
    pending_emis  =db.session.execute(select(func.count(EMI.id)).where(EMI.status=='pending',EMI.is_active==True)).scalar()
    paid_emis     =db.session.execute(select(func.count(EMI.id)).where(EMI.status=='paid',   EMI.is_active==True)).scalar()
    recent_payments=db.session.execute(select(Payment).order_by(Payment.payment_date.desc()).limit(8)).scalars().all()
    emi_by_cat    =db.session.execute(select(EMI.category,func.count(EMI.id),func.sum(EMI.emi_amount)).where(EMI.is_active==True).group_by(EMI.category)).all()
    return render_template('admin/index.html',
        total_users=len(users),total_emis=total_emis,total_payments=total_payments,
        total_amount=total_amount,overdue_emis=overdue_emis,pending_emis=pending_emis,
        paid_emis=paid_emis,recent_users=users[:5],recent_payments=recent_payments,
        users=users,emi_by_cat=emi_by_cat)

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    q=request.args.get('q','').strip()
    stmt=select(User).where(User.is_admin==False)
    if q: stmt=stmt.where(User.name.ilike(f'%{q}%')|User.email.ilike(f'%{q}%'))
    all_users=db.session.execute(stmt.order_by(User.created_at.desc())).scalars().all()
    return render_template('admin/users.html',users=all_users,q=q)

@admin_bp.route('/users/<int:uid>')
@login_required
@admin_required
def user_detail(uid):
    user=db.session.get(User,uid)
    if not user: flash('Not found.','danger'); return redirect(url_for('admin.users'))
    emis=db.session.execute(select(EMI).where(EMI.user_id==uid,EMI.is_active==True)).scalars().all()
    pays=db.session.execute(select(Payment).where(Payment.user_id==uid).order_by(Payment.payment_date.desc())).scalars().all()
    return render_template('admin/user_detail.html',user=user,emis=emis,payments=pays)

@admin_bp.route('/users/<int:uid>/edit',methods=['GET','POST'])
@login_required
@admin_required
def edit_user(uid):
    user=db.session.get(User,uid)
    if not user: flash('Not found.','danger'); return redirect(url_for('admin.users'))
    if request.method=='POST':
        user.name=request.form.get('name',user.name).strip()
        user.email=request.form.get('email',user.email).strip().lower()
        user.occupation=request.form.get('occupation','').strip()
        user.monthly_income=float(request.form.get('monthly_income',0) or 0)
        new_pw=request.form.get('new_password','').strip()
        if new_pw and len(new_pw)>=6: user.set_password(new_pw)
        db.session.commit(); flash(f'User "{user.name}" updated!','success')
        return redirect(url_for('admin.user_detail',uid=user.id))
    return render_template('admin/edit_user.html',user=user)

@admin_bp.route('/users/<int:uid>/toggle',methods=['POST'])
@login_required
@admin_required
def toggle_user(uid):
    user=db.session.get(User,uid)
    if not user: flash('Not found.','danger'); return redirect(url_for('admin.users'))
    user.is_active_account=not user.is_active_account; db.session.commit()
    flash(f'{user.name} {"activated" if user.is_active_account else "deactivated"}.','success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/<int:uid>/delete',methods=['POST'])
@login_required
@admin_required
def delete_user(uid):
    user=db.session.get(User,uid)
    if not user: flash('Not found.','danger'); return redirect(url_for('admin.users'))
    db.session.delete(user); db.session.commit()
    flash(f'User "{user.name}" deleted.','success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/emis')
@login_required
@admin_required
def all_emis():
    status=request.args.get('status','all')
    stmt=select(EMI).where(EMI.is_active==True)
    if status!='all': stmt=stmt.where(EMI.status==status)
    emis=db.session.execute(stmt.order_by(EMI.status)).scalars().all()
    return render_template('admin/emis.html',emis=emis,status=status)

@admin_bp.route('/emis/<int:eid>/delete',methods=['POST'])
@login_required
@admin_required
def delete_emi(eid):
    e=db.session.get(EMI,eid)
    if not e: flash('Not found.','danger'); return redirect(url_for('admin.all_emis'))
    e.is_active=False; db.session.commit(); flash(f'"{e.name}" removed.','success')
    return redirect(url_for('admin.all_emis'))

@admin_bp.route('/payments')
@login_required
@admin_required
def all_payments():
    pays=db.session.execute(select(Payment).order_by(Payment.payment_date.desc())).scalars().all()
    return render_template('admin/payments.html',payments=pays)

# ── API Blueprint ─────────────────────────────────────────────────────────────
api_bp = Blueprint('api', __name__)

@api_bp.route('/calculate',methods=['POST'])
@login_required
def calculate():
    d=request.json or {}
    P,r,n=float(d.get('principal',0)),float(d.get('rate',0)),int(d.get('months',0))
    emi=calc_emi(P,r,n); total=emi*n
    return jsonify({'emi':round(emi,2),'total_interest':round(total-P,2),'total_payment':round(total,2)})




@api_bp.route("/ai-advisor")
@login_required
def ai_advisor():
    return render_template("api/ai_advisor.html")
@api_bp.route('/chat', methods=['POST'])
@login_required
def chat():
    import traceback
    try:
        data = request.get_json(silent=True) or {}
        user_message = data.get("message", "").strip()
        if not user_message:
            return jsonify({"reply": "Please enter a message."})

        # 🧠 1. CONVERSATIONAL INTENT FILTER (Bypasses API latency instantly)
        msg_lower = user_message.lower().strip()
        if msg_lower in ['hi', 'hello', 'hey', 'good morning', 'good evening']:
            return jsonify({'reply': f"Hello {current_user.name}! I am your EMI Guardian advisor. How can I help you manage your loans or budget today?"})
            
        if any(q in msg_lower for q in ['how are you', 'how you doing', 'how is it going']):
            return jsonify({'reply': f"I am doing fantastic, {current_user.name}! Thank you for checking in. I am fully operational and analyzing your debt profile. What financial questions do you have today?"})

        # Fetch live data rows securely from your application models
        emis = EMI.query.filter_by(user_id=current_user.id, is_active=True).all()
        total_emi = sum(e.emi_amount for e in emis)
        total_loan_amount = sum(e.loan_amount for e in emis)
        
        # Build comprehensive real-time context
        context = f"""
        You are EMI Guardian AI, an expert conversational personal finance assistant in India.
        User Name: {current_user.name}
        Monthly Income: ₹{current_user.monthly_income}
        Active Loans: {len(emis)}
        Monthly EMI Outflow: ₹{total_emi}
        
        Current Database Loans Profile:
        """
        for emi in emis:
            context += f"- Loan: {emi.name} | Amount: ₹{emi.loan_amount} | EMI: ₹{emi.emi_amount} | Interest: {emi.interest_rate}% | Status: {emi.status}\n"
            
        context += f"""
        Answer naturally and keep responses concise under 3 sentences. Address the user politely by name ({current_user.name}).
        User Question: {user_message}
        """

        # 🔮 2. LIVE AI PROCESSING VIA MODERN GOOGLE-GENAI SDK
        try:
            client = genai.Client(api_key=os.getenv("RESEND_API_KEY"))
            
            # 🌟 UPDATED MODEL STRIP: Changed to standard gemini-1.5-flash to bypass the 404 name block
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=context
            )
            
            if response and hasattr(response, 'text'):
                return jsonify({ "reply": response.text })
            else:
                raise AttributeError("Response text layout could not be extracted.")
                
        except Exception as ai_err:
            print(f"⚠️ [AI Advisor Gateway] Fallback activated. Error details: {ai_err}")
            
            # 📊 3. ADVANCED CONVERSATIONAL OFFLINE REASONING ENGINE
            if any(k in msg_lower for k in ["how to", "tips", "reduce", "strategy", "improve", "actionable", "ratio"]):
                strategy_reply = f"💡 **Personalised Debt Reduction Strategies for {current_user.name}:**\n\n"
                strategy_reply += "1. **The Avalanche Method:** Prioritise your highest interest loan right now. Throw any extra income at that specific debt first while paying minimums on the rest.\n"
                strategy_reply += "2. **Increase Income Streams:** Since your Debt-to-Income ratio stands at a tight metric, picking up freelance tasks or structured overtime will boost your income denominator and lower your ratio instantly.\n"
                strategy_reply += "3. **Loan Snowball / Consolidation:** Consider shifting multiple small active EMIs into a single, lower-interest personal loan framework to trim down your overlapping monthly payment outgo."
                return jsonify({"reply": strategy_reply})
                
            elif any(k in msg_lower for k in ["budget", "income", "spend", "salary"]):
                remaining_income = current_user.monthly_income - total_emi
                ratio = (total_emi / current_user.monthly_income) * 100 if current_user.monthly_income > 0 else 0
                
                budget_reply = f"💰 **Smart Offline Budget Analysis for {current_user.name}:**\n\n"
                budget_reply += f"• **Monthly Income:** ₹{current_user.monthly_income:,.2f}\n"
                budget_reply += f"• **Total EMI Commitments:** ₹{total_emi:,.2f}/month\n"
                budget_reply += f"• **Disposable Cash Left:** ₹{remaining_income:,.2f}\n"
                budget_reply += f"• **Debt-to-Income Ratio:** **{ratio:.1f}%**\n\n"
                budget_reply += "✅ **Healthy Budget:** Your debt distribution profile stays safe and within comfortable spending thresholds." if ratio <= 50 else "⚠️ **Warning:** More than 50% of your earnings go to installment debts!"
                return jsonify({"reply": budget_reply})
                
            else:
                # Default clean dynamic data fallback summary
                local_reply = f"Hello {current_user.name}! I can read your loan database metrics perfectly right here on your computer:\n\n"
                local_reply += f"📋 **Summary:** You have **{len(emis)} active accounts** with a total loan value of **₹{total_loan_amount:,.2f}**.\n"
                local_reply += f"💸 **Outflow:** Your monthly combined EMI outgo is **₹{total_emi:,.2f}/month**.\n\n"
                local_reply += "✅ Your loan accounts are currently structured beautifully and tracking smoothly!"
                return jsonify({"reply": local_reply})
            
    except Exception:
        traceback.print_exc()
        return jsonify({ "reply": "AI service is currently experiencing network issues. Please try again in a few moments." })

@api_bp.route('/stats')
@login_required
def stats():
    from datetime import timedelta
    monthly=[]
    for i in range(6,0,-1):
        ms=(datetime.now().replace(day=1)-timedelta(days=30*(i-1))).replace(day=1)
        me=(datetime.now().replace(day=1)-timedelta(days=30*(i-2))).replace(day=1) if i>1 else datetime.now()
        pays=db.session.execute(select(Payment).where(Payment.user_id==current_user.id,Payment.payment_date>=ms,Payment.payment_date<me)).scalars().all()
        monthly.append({'month':ms.strftime('%b'),'amount':sum(p.amount for p in pays)})
    emis=db.session.execute(select(EMI).where(EMI.user_id==current_user.id,EMI.is_active==True)).scalars().all()
    return jsonify({'monthly_trend':monthly,'by_category':[{'cat':e.category,'emi':e.emi_amount,'rate':e.interest_rate} for e in emis]})



# ── App Factory ──────────────────────────────────────────────────────────────

def create_app():
    app = Flask(__name__)

    # Secret Key
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "emi-guardian-secret")

    scheduler = APScheduler()

    # ---------------- Database Configuration ----------------
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Render PostgreSQL
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    else:
        # Local PostgreSQL
        app.config["SQLALCHEMY_DATABASE_URI"] = (
            f"postgresql://"
            f"{os.getenv('PG_USER', 'postgres')}:"
            f"{os.getenv('PG_PASS', 'lingeswar')}@"
            f"{os.getenv('PG_HOST', 'localhost')}:"
            f"{os.getenv('PG_PORT', '5432')}/"
            f"{os.getenv('PG_DB', 'emi_guardian')}"
        )

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize Extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please login to continue."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(uid):
        return db.session.get(User, int(uid))

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dash_bp)
    app.register_blueprint(emi_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(notification_bp, url_prefix="/admin")

    # Start Scheduler
    scheduler.init_app(app)
    scheduler.start()

    # Create Database Tables
    with app.app_context():
        db.create_all()
        seed()

    return app
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)






