import os
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///uganda_date.db').replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(30), nullable=False)
    interested_in = db.Column(db.String(30), nullable=False)
    city = db.Column(db.String(80), default='Kampala')
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    search_radius_km = db.Column(db.Float, default=25.0, nullable=False)
    bio = db.Column(db.Text, default='')
    photo = db.Column(db.String(500), default='https://images.unsplash.com/photo-1531123897727-8f129e1688ce?w=700')
    verified = db.Column(db.Boolean, default=False)
    premium_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    likes_until = db.Column(db.DateTime, nullable=True)
    unlimited_until = db.Column(db.DateTime, nullable=True)
    boost_until = db.Column(db.DateTime, nullable=True)
    featured_until = db.Column(db.DateTime, nullable=True)
    super_likes = db.Column(db.Integer, default=0)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_id = db.Column(db.Integer, nullable=False)
    to_id = db.Column(db.Integer, nullable=False)
    kind = db.Column(db.String(20), default='like')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    plan = db.Column(db.String(40), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    payer_phone = db.Column(db.String(30), nullable=False)
    transaction_id = db.Column(db.String(120), unique=True, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified_at = db.Column(db.DateTime, nullable=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, nullable=False)
    receiver_id = db.Column(db.Integer, nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

MTN_MOMO_NUMBER = os.environ.get('MTN_MOMO_NUMBER', '65616659')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@ugandadating.app')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'change-me-now')

PRICES = {
    'premium': {'name': 'Premium', 'price': 10000, 'period': 'month'},
    'likes': {'name': 'See who liked you', 'price': 2000, 'period': 'week'},
    'unlimited': {'name': 'Unlimited Likes', 'price': 3000, 'period': 'week'},
    'boost': {'name': 'Profile Boost', 'price': 2000, 'period': 'one boost'},
    'superlike': {'name': 'Super Like', 'price': 500, 'period': 'each'},
    'featured': {'name': 'Featured Profile', 'price': 5000, 'period': 'week'},
}

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        # A session can survive a database reset/redeployment. Never trust
        # the presence of user_id alone; make sure the account still exists.
        uid = session.get('user_id')
        if not uid:
            return redirect(url_for('login'))
        user = db.session.get(User, uid)
        if user is None:
            session.clear()
            flash('Your session has expired. Please sign in again.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def current_user():
    uid = session.get('user_id')
    return db.session.get(User, uid) if uid else None

def distance_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two coordinates in kilometres."""
    r = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return r * 2 * atan2(sqrt(a), sqrt(1 - a))

def preference_matches(me, user):
    """Return True when both people are interested in each other's gender."""
    my_choice = (me.interested_in or 'Everyone').strip().lower()
    their_choice = (user.interested_in or 'Everyone').strip().lower()
    their_gender = (user.gender or '').strip().lower()
    my_gender = (me.gender or '').strip().lower()

    def accepts(choice, gender):
        if choice in ('everyone', 'anyone', 'all'):
            return True
        if choice in ('women', 'woman'):
            return gender in ('woman', 'women')
        if choice in ('men', 'man'):
            return gender in ('man', 'men')
        if choice in ('non-binary', 'nonbinary'):
            return gender in ('non-binary', 'nonbinary')
        return choice == gender

    return accepts(my_choice, their_gender) and accepts(their_choice, my_gender)


def nearby_profiles(me, limit=200):
    """Return compatible nearby profiles. Uses stored coordinates when available;
    for Uganda profiles without coordinates, falls back to city/area compatibility
    so Discover is not empty simply because GPS coordinates were never captured.
    """
    prefs = getattr(me, "interested_in", None) or getattr(me, "looking_for", None)
    query = User.query.filter(User.id != me.id)

    # Mutual preference filtering when those fields exist.
    if prefs:
        query = query.filter(User.gender.in_([x.strip() for x in str(prefs).split(",") if x.strip()]))
    candidates = query.all()

    out = []
    for p in candidates:
        p_pref = getattr(p, "interested_in", None) or getattr(p, "looking_for", None)
        if p_pref and getattr(me, "gender", None):
            allowed = [x.strip() for x in str(p_pref).split(",") if x.strip()]
            if allowed and me.gender not in allowed:
                continue

        distance = None
        if getattr(me, "latitude", None) is not None and getattr(me, "longitude", None) is not None and getattr(p, "latitude", None) is not None and getattr(p, "longitude", None) is not None:
            from math import radians, sin, cos, sqrt, atan2
            lat1, lon1, lat2, lon2 = map(radians, [me.latitude, me.longitude, p.latitude, p.longitude])
            dlat, dlon = lat2-lat1, lon2-lon1
            aa = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
            distance = 6371 * 2 * atan2(sqrt(aa), sqrt(1-aa))

        # If both users have a location and distance exceeds the range, exclude.
        radius = float(getattr(me, "search_radius_km", None) or 25)
        if distance is not None and distance > radius:
            continue

        # If coordinates are missing, retain the profile. This allows Kampala/Makindye
        # users to discover profiles whose location was entered as an area/city only.
        out.append((p, distance))

    out.sort(key=lambda x: (x[1] is None, x[1] if x[1] is not None else 999999))
    return out[:limit]

@app.route('/')
def home():
    if session.get('user_id'):
        return redirect(url_for('discover'))
    return render_template('landing.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        age = int(request.form['age'])
        gender = request.form['gender']
        interested_in = request.form['interested_in']
        city = request.form.get('city', 'Kampala')
        if age < 18:
            flash('Uganda Dating is for adults 18+ only.', 'error')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'error')
            return render_template('register.html')
        user = User(name=name, email=email, password_hash=generate_password_hash(password), age=age,
                    gender=gender, interested_in=interested_in, city=city,
                    bio='New on Uganda Dating. Looking forward to meeting someone genuine!')
        db.session.add(user); db.session.commit()
        session['user_id'] = user.id
        return redirect(url_for('discover'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email'].strip().lower()).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            session['user_id'] = user.id
            return redirect(url_for('discover'))
        flash('Email or password is incorrect.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('home'))

@app.route('/discover')
@login_required
def discover():
    me = current_user()
    # Discover shows compatible nearby people based on BOTH users' gender preferences.
    # We intentionally do not remove people you have already liked here, so the
    # discovery page can show the full compatible nearby pool.
    nearby = nearby_profiles(me, limit=200)
    return render_template('discover.html', nearby=nearby, nearby_count=len(nearby), radius=me.search_radius_km or 25, has_location=me.latitude is not None and me.longitude is not None)

@app.post('/location')
@login_required
def update_location():
    me = current_user()
    try:
        lat = float(request.form.get('latitude', ''))
        lon = float(request.form.get('longitude', ''))
        radius = float(request.form.get('search_radius_km', me.search_radius_km or 25))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'Invalid location or range.'}), 400
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify({'ok': False, 'error': 'Invalid coordinates.'}), 400
    me.latitude, me.longitude = lat, lon
    me.search_radius_km = max(1, min(radius, 500))
    db.session.commit()
    return jsonify({'ok': True, 'radius': me.search_radius_km})

@app.post('/search-radius')
@login_required
def update_search_radius():
    me = current_user()
    try:
        radius = float(request.form.get('search_radius_km', '25'))
    except ValueError:
        radius = 25
    me.search_radius_km = max(1, min(radius, 500))
    db.session.commit()
    return redirect(request.form.get('next') or url_for('discover'))

@app.post('/like/<int:user_id>')
@login_required
def like(user_id):
    me = current_user()
    if me.id == user_id: return jsonify({'ok': False})
    existing = Like.query.filter_by(from_id=me.id, to_id=user_id).first()
    if not existing:
        db.session.add(Like(from_id=me.id, to_id=user_id, kind=request.form.get('kind','like')))
        db.session.commit()
    mutual = Like.query.filter_by(from_id=user_id, to_id=me.id).first()
    return jsonify({'ok': True, 'match': bool(mutual)})

@app.route('/likes')
@login_required
def likes():
    me = current_user()
    incoming = Like.query.filter_by(to_id=me.id).order_by(Like.created_at.desc()).all()
    liked_users = []
    seen = set()
    for item in incoming:
        if item.from_id in seen:
            continue
        user = db.session.get(User, item.from_id)
        if user:
            liked_users.append((user, item.kind))
            seen.add(item.from_id)
    return render_template('likes.html', liked_users=liked_users)

@app.route('/encounters')
@login_required
def encounters():
    me = current_user()
    nearby = nearby_profiles(me, limit=50)
    return render_template('swipe.html', nearby=nearby, radius=me.search_radius_km or 25)

@app.route('/chats')
@login_required
def chats():
    me = current_user()
    rows = Message.query.filter((Message.sender_id == me.id) | (Message.receiver_id == me.id)).order_by(Message.created_at.desc()).all()
    other_ids = []
    for row in rows:
        other_id = row.receiver_id if row.sender_id == me.id else row.sender_id
        if other_id not in other_ids:
            other_ids.append(other_id)
    conversations = []
    for other_id in other_ids:
        other = db.session.get(User, other_id)
        if not other:
            continue
        last = Message.query.filter(((Message.sender_id == me.id) & (Message.receiver_id == other.id)) | ((Message.sender_id == other.id) & (Message.receiver_id == me.id))).order_by(Message.created_at.desc()).first()
        conversations.append((other, last))
    return render_template('chats.html', conversations=conversations)


@app.route('/matches')
@login_required
def matches():
    me = current_user()
    outgoing = {x.to_id for x in Like.query.filter_by(from_id=me.id).all()}
    incoming = {x.from_id for x in Like.query.filter_by(to_id=me.id).all()}
    ids = list(outgoing & incoming)
    matches = User.query.filter(User.id.in_(ids)).all() if ids else []
    return render_template('matches.html', matches=matches)

@app.route('/messages/<int:user_id>', methods=['GET','POST'])
@login_required
def messages(user_id):
    me = current_user(); other = db.session.get(User, user_id)
    if not other: return redirect(url_for('matches'))
    if request.method == 'POST' and request.form.get('body','').strip():
        db.session.add(Message(sender_id=me.id, receiver_id=other.id, body=request.form['body'].strip()))
        db.session.commit()
    msgs = Message.query.filter(((Message.sender_id==me.id)&(Message.receiver_id==other.id))|((Message.sender_id==other.id)&(Message.receiver_id==me.id))).order_by(Message.created_at).all()
    return render_template('messages.html', other=other, messages=msgs)

@app.route('/profile', methods=['GET','POST'])
@login_required
def profile():
    me = current_user()
    if request.method == 'POST':
        me.name = request.form['name'].strip(); me.city = request.form.get('city','Kampala')
        me.gender = request.form.get('gender', me.gender)
        me.interested_in = request.form.get('interested_in', me.interested_in)
        me.bio = request.form.get('bio','').strip(); me.photo = request.form.get('photo','').strip() or me.photo
        try:
            me.search_radius_km = max(1, min(float(request.form.get('search_radius_km', me.search_radius_km or 25)), 500))
        except ValueError:
            pass
        db.session.commit(); flash('Profile updated.', 'success')
    return render_template('profile.html', user=me)

@app.route('/premium')
@login_required
def premium():
    return render_template('premium.html')

@app.route('/payment/<plan>', methods=['GET','POST'])
@login_required
def payment(plan):
    if plan not in PRICES:
        return redirect(url_for('premium'))
    product = PRICES[plan]
    if request.method == 'POST':
        phone = request.form.get('payer_phone','').strip()
        txid = request.form.get('transaction_id','').strip()
        if not phone or not txid:
            flash('Enter the MTN number used and your MTN transaction ID.', 'error')
            return render_template('payment.html', plan=plan, product=product)
        if Payment.query.filter_by(transaction_id=txid).first():
            flash('That transaction ID has already been submitted.', 'error')
            return render_template('payment.html', plan=plan, product=product)
        pay = Payment(user_id=current_user().id, plan=plan, amount=product['price'], payer_phone=phone, transaction_id=txid)
        db.session.add(pay); db.session.commit()
        flash('Payment submitted. Your purchase will activate after MTN payment verification.', 'success')
        return redirect(url_for('premium'))
    return render_template('payment.html', plan=plan, product=product)

@app.route('/checkout/<plan>', methods=['GET','POST'])
@login_required
def checkout(plan):
    return redirect(url_for('payment', plan=plan))

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get('admin_email') != ADMIN_EMAIL:
            return redirect(url_for('admin_login', next=request.path))
        return f(*args, **kwargs)
    return wrapper

@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('email','').strip().lower() == ADMIN_EMAIL.lower() and request.form.get('password','') == ADMIN_PASSWORD:
            session['admin_email'] = ADMIN_EMAIL
            return redirect(request.args.get('next') or url_for('admin_payments'))
        flash('Invalid admin credentials.', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_email', None)
    return redirect(url_for('home'))

def activate_purchase(user, plan):
    now = datetime.utcnow()
    if plan == 'premium':
        user.premium_until = max(user.premium_until or now, now) + timedelta(days=30)
    elif plan == 'likes':
        user.likes_until = max(user.likes_until or now, now) + timedelta(days=7)
    elif plan == 'unlimited':
        user.unlimited_until = max(user.unlimited_until or now, now) + timedelta(days=7)
    elif plan == 'boost':
        user.boost_until = max(user.boost_until or now, now) + timedelta(hours=24)
    elif plan == 'featured':
        user.featured_until = max(user.featured_until or now, now) + timedelta(days=7)
    elif plan == 'superlike':
        user.super_likes = (user.super_likes or 0) + 1

@app.route('/admin/payments')
@admin_required
def admin_payments():
    payments = Payment.query.order_by(Payment.created_at.desc()).all()
    return render_template('admin_payments.html', payments=payments)

@app.post('/admin/payments/<int:payment_id>/verify')
@admin_required
def verify_payment(payment_id):
    payment = db.session.get(Payment, payment_id)
    if not payment:
        flash('Payment not found.', 'error')
        return redirect(url_for('admin_payments'))
    if payment.status != 'verified':
        payment.status = 'verified'
        payment.verified_at = datetime.utcnow()
        user = db.session.get(User, payment.user_id)
        if user:
            activate_purchase(user, payment.plan)
        db.session.commit()
        flash('Payment verified and feature activated.', 'success')
    return redirect(url_for('admin_payments'))

@app.post('/admin/payments/<int:payment_id>/reject')
@admin_required
def reject_payment(payment_id):
    payment = db.session.get(Payment, payment_id)
    if payment and payment.status == 'pending':
        payment.status = 'rejected'; db.session.commit()
        flash('Payment rejected.', 'success')
    return redirect(url_for('admin_payments'))

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

with app.app_context():
    db.create_all()
    # Lightweight migration for deployments that already have the original User table.
    # This keeps the new MTN MoMo entitlement fields from breaking an existing database.
    user_columns = {c['name'] for c in db.session.execute(db.text("PRAGMA table_info(user)")).mappings()} if db.engine.dialect.name == 'sqlite' else {r[0] for r in db.session.execute(db.text("SELECT column_name FROM information_schema.columns WHERE table_name='user'")).all()}
    # Use database-specific SQL types here. PostgreSQL does not have DATETIME/FLOAT
    # type names, while SQLite accepts a much smaller set of type affinities.
    if db.engine.dialect.name == 'postgresql':
        new_columns = {
            'likes_until': 'TIMESTAMP',
            'unlimited_until': 'TIMESTAMP',
            'boost_until': 'TIMESTAMP',
            'featured_until': 'TIMESTAMP',
            'super_likes': 'INTEGER DEFAULT 0',
            'latitude': 'DOUBLE PRECISION',
            'longitude': 'DOUBLE PRECISION',
            'search_radius_km': 'DOUBLE PRECISION DEFAULT 25'
        }
        for column, sql_type in new_columns.items():
            if column not in user_columns:
                db.session.execute(db.text(f'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS {column} {sql_type}'))
    else:
        new_columns = {
            'likes_until': 'DATETIME',
            'unlimited_until': 'DATETIME',
            'boost_until': 'DATETIME',
            'featured_until': 'DATETIME',
            'super_likes': 'INTEGER DEFAULT 0',
            'latitude': 'FLOAT',
            'longitude': 'FLOAT',
            'search_radius_km': 'FLOAT DEFAULT 25'
        }
        for column, sql_type in new_columns.items():
            if column not in user_columns:
                db.session.execute(db.text(f'ALTER TABLE user ADD COLUMN {column} {sql_type}'))
    db.session.commit()
    if User.query.count() == 0:
        demo = [
            ('Anita', 'anita@demo.ug', 24, 'Woman', 'Men', 'Kampala', 'Love good conversations, travel, food and new adventures.', 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=700'),
            ('Brian', 'brian@demo.ug', 28, 'Man', 'Women', 'Kampala', 'Kind, ambitious and love good vibes. Looking for something real.', 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=700'),
            ('Sarah', 'sarah@demo.ug', 26, 'Woman', 'Men', 'Entebbe', 'Coffee, music and weekend adventures. Here for a genuine connection.', 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=700'),
        ]
        for n,e,a,g,i,c,b,p in demo:
            db.session.add(User(name=n,email=e,password_hash=generate_password_hash('demo123'),age=a,gender=g,interested_in=i,city=c,bio=b,photo=p,verified=True,latitude={'Kampala':0.3476,'Entebbe':0.0512}.get(c),longitude={'Kampala':32.5825,'Entebbe':32.4637}.get(c)))
        db.session.commit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
