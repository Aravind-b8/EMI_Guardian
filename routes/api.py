from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from models.emi import EMI
from models.payment import Payment
from app import db
from sqlalchemy import select
import math, os, requests as req

api = Blueprint('api', __name__)

def calc_emi(P, r, n):
    if not P or not n: return 0
    R = r / (12 * 100)
    if R == 0: return P / n
    return P * R * math.pow(1+R, n) / (math.pow(1+R, n) - 1)

@api.route('/calculate', methods=['POST'])
@login_required
def calculate():
    data  = request.json or {}
    P, r, n = float(data.get('principal',0)), float(data.get('rate',0)), int(data.get('months',0))
    emi   = calc_emi(P, r, n)
    total = emi * n
    return jsonify({'emi': round(emi,2), 'total_interest': round(total-P,2), 'total_payment': round(total,2)})

@api.route('/chat', methods=['POST'])
@login_required
def chat():
    data    = request.json or {}
    message = data.get('message','')
    emis    = db.session.execute(
        select(EMI).filter_by(user_id=current_user.id, is_active=True)
    ).scalars().all()

    summary = '; '.join(f"{e.name}: ₹{e.emi_amount:.0f}/mo @ {e.interest_rate}% ({e.status})" for e in emis)
    total   = sum(e.emi_amount for e in emis)
    ratio   = round(total / current_user.monthly_income * 100, 1) if current_user.monthly_income else 0
    system  = (f"You are EMI Guardian AI, a smart Indian financial advisor. "
               f"User: {current_user.name}. Income: ₹{current_user.monthly_income:,.0f}. "
               f"Loans: {summary}. Monthly EMI: ₹{total:,.0f} ({ratio}% of income). "
               f"Respond in 2-4 sentences with specific actionable advice. Use ₹. Be friendly.")

    api_key = os.environ.get('ANTHROPIC_API_KEY','')
    if api_key:
        try:
            r = req.post('https://api.anthropic.com/v1/messages',
                headers={'x-api-key':api_key,'anthropic-version':'2023-06-01','content-type':'application/json'},
                json={'model':'claude-sonnet-4-6','max_tokens':400,'system':system,
                      'messages':[{'role':'user','content':message}]}, timeout=15)
            reply = r.json().get('content',[{}])[0].get('text','')
            if reply: return jsonify({'reply': reply})
        except: pass

    # Smart built-in fallback
    overdue = [e for e in emis if e.status=='overdue']
    high    = max(emis, key=lambda e: e.interest_rate) if emis else None
    msg     = message.lower()
    if 'first' in msg or 'priority' in msg:
        reply = f"Pay your {high.name} first — at {high.interest_rate}%, it costs the most. Clearing it early saves ₹{high.total_interest():,.0f} in interest." if high else "No active EMIs found."
    elif 'overdue' in msg or 'miss' in msg:
        reply = f"You have {len(overdue)} overdue EMI(s): {', '.join(e.name for e in overdue)}. Pay immediately to protect your CIBIL score." if overdue else "Great news — no overdue EMIs!"
    elif 'another loan' in msg or 'new loan' in msg:
        reply = f"Your EMI-to-income ratio is {ratio}%. {'Avoid new loans — you are above the safe 40% limit.' if ratio>40 else 'You have some capacity, but stay cautious and keep ratio below 40%.'}"
    elif 'health' in msg or 'score' in msg:
        s = current_user.health_score()
        reply = f"Your financial health score is {s}/100. {'Excellent — keep paying on time!' if s>=75 else 'Improve by clearing overdue EMIs and reducing your EMI ratio below 40%.'}"
    elif 'save' in msg or 'interest' in msg or 'prepay' in msg:
        total_int = sum(e.total_interest() for e in emis)
        reply = f"You will pay ₹{total_int:,.0f} in total interest. Prepaying {high.name if high else 'your highest-rate loan'} first saves the most money."
    elif 'summary' in msg or 'situation' in msg:
        reply = f"You have {len(emis)} active EMIs totaling ₹{total:,.0f}/month ({ratio}% of income). {len(overdue)} overdue, {len([e for e in emis if e.status=='pending'])} pending this month."
    else:
        reply = f"You have {len(emis)} active EMIs costing ₹{total:,.0f}/month ({ratio}% of your ₹{current_user.monthly_income:,.0f} income). {'Urgent: clear overdue payments first!' if overdue else 'Keep paying on time to maintain a healthy credit score!'}"
    return jsonify({'reply': reply})

@api.route('/stats')
@login_required
def stats():
    from datetime import datetime, timedelta
    monthly = []
    for i in range(6, 0, -1):
        month_start = (datetime.now().replace(day=1) - timedelta(days=30*(i-1))).replace(day=1)
        if i > 1:
            month_end = (datetime.now().replace(day=1) - timedelta(days=30*(i-2))).replace(day=1)
        else:
            month_end = datetime.now()
        pays = db.session.execute(
            select(Payment).filter(
                Payment.user_id == current_user.id,
                Payment.payment_date >= month_start,
                Payment.payment_date <  month_end
            )
        ).scalars().all()
        monthly.append({'month': month_start.strftime('%b'), 'amount': sum(p.amount for p in pays)})
    emis = db.session.execute(
        select(EMI).filter_by(user_id=current_user.id, is_active=True)
    ).scalars().all()
    return jsonify({
        'monthly_trend': monthly,
        'by_category': [{'cat':e.category,'emi':e.emi_amount,'rate':e.interest_rate} for e in emis]
    })
