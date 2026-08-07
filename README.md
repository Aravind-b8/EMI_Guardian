# 🛡️ EMI Guardian AI — Full Stack Python Project

Never miss an EMI again. AI-powered loan tracking with admin panel.

## 🚀 Live Demo

🔗 https://emi-guardian-1.onrender.com/

## 🚀 Quick Setup (Windows)

### Step 1 — Open terminal in the project folder
```
Right-click inside the folder → "Open in Terminal"
```

### Step 2 — Create virtual environment
```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
```

### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Run the app
```bash
python app.py
```

### Step 5 — Open in browser
```
http://localhost:5000
```

---

## 🔑 Demo Credentials

| Role  | Email                    | Password  |
|-------|--------------------------|-----------|
| User  | rolex@email.com          | rolex123  |
| Admin | admin@emiguardian.com    | admin123  |

---

## 🤖 Enable AI Chatbot (Optional)

Get a free API key from https://console.anthropic.com

Then set it as an environment variable:
```bash
# Windows
set ANTHROPIC_API_KEY=sk-ant-your-key-here

# Mac/Linux
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Without the key, the chatbot uses smart built-in responses based on your EMI data.

---

## 📁 Project Structure

```
emi_guardian/
├── app.py                  # Main Flask app + DB seeding
├── requirements.txt
├── models/
│   ├── user.py             # User model + health score
│   ├── emi.py              # EMI model + calculations
│   └── payment.py          # Payment model
├── routes/
│   ├── auth.py             # Login, register, logout
│   ├── dashboard.py        # Dashboard + profile
│   ├── emi.py              # EMI CRUD + mark paid
│   ├── admin.py            # Admin panel
│   └── api.py              # AI chat + EMI calculator API
└── templates/
    ├── base.html           # Main layout (dark glassmorphism)
    ├── auth/               # Login + register
    ├── dashboard/          # Dashboard + profile
    ├── emi/                # List, add, calculator, history
    └── admin/              # Admin panel + base
```

---

## ✨ Features

### User Features
- 🔐 Login / Register / Logout
- 📊 Dashboard with stats, charts, health score
- ➕ Add EMI with live calculator preview
- ✅ Mark EMI as paid (with mode + remarks)
- 📋 EMI list with filter (all/pending/paid/overdue)
- 🧮 Full EMI calculator with amortization schedule
- 📅 Calendar view with color-coded EMI days
- 📜 Payment history
- ⚙️ Profile + notification preferences
- 🤖 AI chatbot (Anthropic Claude API)

### Admin Panel
- 📊 Platform-wide dashboard with charts
- 👥 User management (view, activate/deactivate)
- 👤 Individual user detail page
- 📋 All EMIs across all users
- 💳 All payments with search
- 🔍 Search/filter across all tables

---

## 🛠 Tech Stack

| Layer       | Technology         |
|-------------|--------------------|
| Backend     | Flask (Python)     |
| Database    | SQLite → PostgreSQL|
| ORM         | SQLAlchemy         |
| Auth        | Flask-Login + Bcrypt|
| AI          | Anthropic Claude API|
| Charts      | Chart.js           |
| Icons       | Font Awesome 6     |
| Fonts       | Inter + Space Grotesk|
| UI Theme    | Dark Glassmorphism |
