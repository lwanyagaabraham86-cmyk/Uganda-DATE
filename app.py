import os
import base64
import uuid
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from functools import wraps
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory, Response
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///uganda_date.db').replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024
@app.get('/manifest.webmanifest')
def manifest_webmanifest():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'manifest.webmanifest', mimetype='application/manifest+json')

@app.get('/sw.js')
def service_worker():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'sw.js', mimetype='application/javascript')

@app.get('/robots.txt')
def robots_txt():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'robots.txt', mimetype='text/plain')

@app.get('/sitemap.xml')
def sitemap_xml():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'sitemap.xml', mimetype='application/xml')

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
    location_accuracy_m = db.Column(db.Float, nullable=True)
    last_seen = db.Column(db.DateTime, nullable=True)
    min_age = db.Column(db.Integer, default=18, nullable=False)
    max_age = db.Column(db.Integer, default=60, nullable=False)
    bio = db.Column(db.Text, default='')
    mood = db.Column(db.String(120), default='')
    relationship_status = db.Column(db.String(60), default='')
    relationship_goal = db.Column(db.String(80), default='')
    smoking = db.Column(db.String(40), default='')
    religion = db.Column(db.String(80), default='')
    languages = db.Column(db.String(200), default='')
    work = db.Column(db.String(160), default='')
    education = db.Column(db.String(160), default='')
    interests = db.Column(db.String(500), default='')
    photo = db.Column(db.String(500), default='https://images.unsplash.com/photo-1531123897727-8f129e1688ce?w=700')
    photo1_data = db.Column(db.Text, nullable=True)
    photo2_data = db.Column(db.Text, nullable=True)
    photo3_data = db.Column(db.Text, nullable=True)
    photo4_data = db.Column(db.Text, nullable=True)
    photo5_data = db.Column(db.Text, nullable=True)
    photo6_data = db.Column(db.Text, nullable=True)
    verified = db.Column(db.Boolean, default=False)
    premium_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    likes_until = db.Column(db.DateTime, nullable=True)
    unlimited_until = db.Column(db.DateTime, nullable=True)
    boost_until = db.Column(db.DateTime, nullable=True)
    featured_until = db.Column(db.DateTime, nullable=True)
    super_likes = db.Column(db.Integer, default=0)
    subscription_plan = db.Column(db.String(20), default='free')
    credits = db.Column(db.Integer, default=0)
    referral_code = db.Column(db.String(24), unique=True, nullable=True)
    referred_by_id = db.Column(db.Integer, nullable=True)

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

class Block(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blocker_id = db.Column(db.Integer, nullable=False)
    blocked_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, nullable=False)
    reported_id = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(60), nullable=False)
    details = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)

MTN_MOMO_NUMBER = os.environ.get('MTN_MOMO_NUMBER', '65616659')
MTN_MOMO_MODE = os.environ.get('MTN_MOMO_MODE', 'manual').lower()
MTN_MOMO_BASE_URL = os.environ.get(
    'MTN_MOMO_BASE_URL',
    'https://proxy.momoapi.mtn.com' if MTN_MOMO_MODE == 'live'
    else 'https://sandbox.momodeveloper.mtn.com'
)
MTN_MOMO_TARGET_ENV = os.environ.get(
    'MTN_MOMO_TARGET_ENV',
    'mtnuganda' if MTN_MOMO_MODE == 'live' else 'sandbox'
)
MTN_MOMO_SUBSCRIPTION_KEY = os.environ.get('MTN_MOMO_SUBSCRIPTION_KEY', '')
MTN_MOMO_API_USER = os.environ.get('MTN_MOMO_API_USER', '')
MTN_MOMO_API_KEY = os.environ.get('MTN_MOMO_API_KEY', '')
MTN_MOMO_CALLBACK_URL = os.environ.get(
    'MTN_MOMO_CALLBACK_URL',
    'https://ugandadating.co.ug/momo/callback'
)

ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@ugandadating.app')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'change-me-now')

PRICES = {
    'plus': {
        'name': 'Plus', 'price': 10000, 'period': 'month', 'type': 'subscription',
        'badge': 'Explore more',
        'features': ['Unlimited Likes', 'Unlimited Rewinds', 'Ad-free browsing', 'Private browsing']
    },
    'gold': {
        'name': 'Gold', 'price': 20000, 'period': 'month', 'type': 'subscription',
        'badge': 'Most popular',
        'features': ['Everything in Plus', 'See Who Likes You', '5 Special Likes', '10 bonus credits']
    },
    'platinum': {
        'name': 'Platinum', 'price': 30000, 'period': 'month', 'type': 'subscription',
        'badge': 'Best visibility',
        'features': ['Everything in Gold', 'Priority Likes', '10 Special Likes', '20 bonus credits']
    },
    'boost': {
        'name': 'Profile Boost', 'price': 2000, 'period': '30 minutes', 'type': 'addon',
        'badge': 'Get noticed',
        'features': ['Higher placement in Discover', 'Higher placement in Encounters']
    },
    'superlike': {
        'name': 'Special Like', 'price': 500, 'period': 'each', 'type': 'addon',
        'badge': 'Stand out',
        'features': ['Send a highlighted Special Like']
    },
    'featured': {
        'name': 'Featured Profile', 'price': 5000, 'period': '7 days', 'type': 'addon',
        'badge': 'Be seen',
        'features': ['Featured placement', 'More visibility in nearby discovery']
    },
    'credits10': {
        'name': '10 Credits', 'price': 2000, 'period': 'one-time', 'type': 'credits', 'credits': 10,
        'badge': 'Starter pack', 'features': ['Use for boosts and special interactions']
    },
    'credits25': {
        'name': '25 Credits', 'price': 5000, 'period': 'one-time', 'type': 'credits', 'credits': 25,
        'badge': 'Popular pack', 'features': ['Use for boosts and special interactions']
    },
    'credits60': {
        'name': '60 Credits', 'price': 10000, 'period': 'one-time', 'type': 'credits', 'credits': 60,
        'badge': 'Best value', 'features': ['Use for boosts and special interactions']
    },
    'premium': {'name': 'Premium', 'price': 10000, 'period': 'month', 'type': 'legacy'},
    'likes': {'name': 'See who liked you', 'price': 2000, 'period': 'week', 'type': 'legacy'},
    'unlimited': {'name': 'Unlimited Likes', 'price': 3000, 'period': 'week', 'type': 'legacy'},
}

PLAN_RANK = {'free': 0, 'plus': 1, 'gold': 2, 'platinum': 3}

def active_plan(user):
    if not user:
        return 'free'
    until = user.premium_until
    if until and until > datetime.utcnow():
        return (user.subscription_plan or 'premium').lower()
    return 'free'

def has_plan(user, required):
    return PLAN_RANK.get(active_plan(user), 0) >= PLAN_RANK.get(required, 0)

def normalize_mtn_msisdn(phone):
    digits = ''.join(ch for ch in (phone or '') if ch.isdigit())
    if digits.startswith('00'):
        digits = digits[2:]
    if digits.startswith('0'):
        digits = '256' + digits[1:]
    return digits

def momo_configured():
    return MTN_MOMO_MODE == 'live' and all([
        MTN_MOMO_SUBSCRIPTION_KEY,
        MTN_MOMO_API_USER,
        MTN_MOMO_API_KEY
    ])

def momo_access_token():
    auth = base64.b64encode(
        f'{MTN_MOMO_API_USER}:{MTN_MOMO_API_KEY}'.encode('utf-8')
    ).decode('ascii')
    response = requests.post(
        f'{MTN_MOMO_BASE_URL}/collection/token/',
        headers={
            'Authorization': f'Basic {auth}',
            'Ocp-Apim-Subscription-Key': MTN_MOMO_SUBSCRIPTION_KEY,
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()['access_token']

def momo_request_to_pay(amount, payer_phone, reference_id, product_name):
    token = momo_access_token()
    phone = normalize_mtn_msisdn(payer_phone)
    if not (phone.isdigit() and len(phone) == 12 and phone.startswith('256')):
        raise ValueError('Enter a valid Uganda MTN number.')
    payload = {
        'amount': str(int(amount)),
        'currency': 'UGX',
        'externalId': reference_id,
        'payer': {'partyIdType': 'MSISDN', 'partyId': phone},
        'payerMessage': f'Uganda Dating - {product_name}',
        'payeeNote': f'Uganda Dating - {product_name}',
    }
    headers = {
        'Authorization': f'Bearer {token}',
        'Ocp-Apim-Subscription-Key': MTN_MOMO_SUBSCRIPTION_KEY,
        'X-Target-Environment': MTN_MOMO_TARGET_ENV,
        'X-Reference-Id': reference_id,
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
    }
    if MTN_MOMO_CALLBACK_URL:
        headers['X-Callback-Url'] = MTN_MOMO_CALLBACK_URL
    response = requests.post(
        f'{MTN_MOMO_BASE_URL}/collection/v1_0/requesttopay',
        json=payload, headers=headers, timeout=20
    )
    if response.status_code not in (200, 202):
        raise RuntimeError(f'MTN MoMo request failed ({response.status_code}).')
    return True

def momo_payment_status(reference_id):
    token = momo_access_token()
    response = requests.get(
        f'{MTN_MOMO_BASE_URL}/collection/v1_0/requesttopay/{reference_id}',
        headers={
            'Authorization': f'Bearer {token}',
            'Ocp-Apim-Subscription-Key': MTN_MOMO_SUBSCRIPTION_KEY,
            'X-Target-Environment': MTN_MOMO_TARGET_ENV,
            'Cache-Control': 'no-cache',
        },
        timeout=20
    )
    response.raise_for_status()
    return response.json()

MAX_PROFILE_IMAGE_BYTES = 180 * 1024
ALLOWED_PROFILE_IMAGE_MIMES = {'image/jpeg', 'image/png', 'image/webp'}

def clean_profile_photo(data_url):
    """Validate a browser-compressed image data URL before storing it."""
    if not data_url or ',' not in data_url:
        return None
    header, payload = data_url.split(',', 1)
    if not header.startswith('data:'):
        return None
    mime = header[5:].split(';', 1)[0].strip().lower()
    if mime not in ALLOWED_PROFILE_IMAGE_MIMES:
        return None
    try:
        raw = base64.b64decode(payload, validate=True)
    except Exception:
        return None
    if not raw or len(raw) > MAX_PROFILE_IMAGE_BYTES:
        return None
    normalized = base64.b64encode(raw).decode('ascii')
    return f'data:{mime};base64,{normalized}'

def photo_url(user, slot=1):
    if slot < 1 or slot > 6:
        return user.photo
    data = getattr(user, f'photo{slot}_data', None)
    if data:
        return url_for('user_photo', user_id=user.id, slot=slot)
    return user.photo

def profile_photos(user):
    photos = []
    for slot in range(1, 7):
        data = getattr(user, f'photo{slot}_data', None)
        if data:
            photos.append(url_for('user_photo', user_id=user.id, slot=slot))
    if not photos and user.photo:
        photos.append(user.photo)
    return photos


def ensure_referral_code(user):
    if user.referral_code:
        return user.referral_code
    code = uuid.uuid4().hex[:10].upper()
    while User.query.filter_by(referral_code=code).first():
        code = uuid.uuid4().hex[:10].upper()
    user.referral_code = code
    db.session.commit()
    return code

@app.get('/user/<int:user_id>/photo/<int:slot>')
def user_photo(user_id, slot):
    if slot not in range(1, 7):
        return '', 404
    user = db.session.get(User, user_id)
    if not user:
        return '', 404
    data = getattr(user, f'photo{slot}_data', None)
    if not data or ',' not in data:
        return '', 404
    header, payload = data.split(',', 1)
    mime = header[5:].split(';', 1)[0].strip().lower() if header.startswith('data:') else 'image/jpeg'
    if mime not in ALLOWED_PROFILE_IMAGE_MIMES:
        return '', 404
    try:
        raw = base64.b64decode(payload, validate=True)
    except Exception:
        return '', 404
    return Response(raw, mimetype=mime, headers={'Cache-Control': 'public, max-age=86400'})

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

    age_ok_for_me = (me.min_age or 18) <= user.age <= (me.max_age or 60)
    age_ok_for_them = (user.min_age or 18) <= me.age <= (user.max_age or 60)
    return accepts(my_choice, their_gender) and accepts(their_choice, my_gender) and age_ok_for_me and age_ok_for_them


def nearby_profiles(me, exclude_ids=None, limit=200):
    """Return mutually compatible profiles sorted by real GPS distance when coordinates exist."""
    exclude_ids = set(exclude_ids or ()) | {me.id}
    blocked_ids = {
        b.blocked_id for b in Block.query.filter_by(blocker_id=me.id).all()
    } | {
        b.blocker_id for b in Block.query.filter_by(blocked_id=me.id).all()
    }
    exclude_ids |= blocked_ids
    radius = max(1.0, min(float(request.args.get('distance_km') or me.search_radius_km or 25), 500.0))

    min_age = max(18, min(100, int(request.args.get('min_age') or me.min_age or 18)))
    max_age = max(18, min(100, int(request.args.get('max_age') or me.max_age or 60)))
    if min_age > max_age: min_age, max_age = max_age, min_age
    query = User.query.filter(~User.id.in_(exclude_ids))
    query = query.filter(User.age >= min_age, User.age <= max_age)
    candidates = query.all()
    gender_filter = (request.args.get('gender') or 'Everyone').lower()
    if gender_filter in ('women','woman'):
        candidates = [u for u in candidates if u.gender == 'Woman']
    elif gender_filter in ('men','man'):
        candidates = [u for u in candidates if u.gender == 'Man']
    elif gender_filter in ('non-binary','nonbinary'):
        candidates = [u for u in candidates if u.gender == 'Non-binary']

    location_filter = (request.args.get('location') or 'Any').strip().lower()
    online_only = request.args.get('online') == '1'
    verified_only = request.args.get('verified') == '1'
    photos_only = request.args.get('photos') == '1'
    new_only = request.args.get('new') == '1'
    online_cutoff = datetime.utcnow() - timedelta(minutes=10)
    recent_cutoff = datetime.utcnow() - timedelta(days=7)

    results = []
    has_my_gps = me.latitude is not None and me.longitude is not None

    lat_delta = radius / 111.0
    lon_denominator = max(0.1, cos(radians(me.latitude or 0)))
    lon_delta = radius / (111.0 * lon_denominator)
    min_lat = (me.latitude - lat_delta) if has_my_gps else None
    max_lat = (me.latitude + lat_delta) if has_my_gps else None
    min_lon = (me.longitude - lon_delta) if has_my_gps else None
    max_lon = (me.longitude + lon_delta) if has_my_gps else None

    def area_group(city):
        c = (city or '').strip().lower()
        kampala_areas = {
            'kampala', 'central kampala', 'makindye', 'muyenga', 'bukoto',
            'ntinda', 'kololo', 'nakawa', 'rubaga', 'kawempe', 'najjera',
            'kibuye', 'munyonyo', 'buziga', 'kabalagala', 'nsambya',
            'kisugu', 'namuwongo', 'bugolobi', 'kiwafu', 'katwe',
            'namirembe', 'makerere', 'mengo', 'kansanga'
        }
        if c in kampala_areas or 'kampala' in c:
            return 'kampala'
        if 'wakiso' in c or 'kira' in c or 'kajjansi' in c:
            return 'wakiso'
        return c

    my_area = area_group(me.city)

    for user in candidates:
        if verified_only and not user.verified:
            continue
        if online_only and (not user.last_seen or user.last_seen < online_cutoff):
            continue
        if photos_only and len(profile_photos(user)) < 2:
            continue
        if new_only and (not user.created_at or user.created_at < recent_cutoff):
            continue
        if location_filter not in ('', 'any', 'all') and location_filter not in (user.city or '').lower():
            continue
        if not preference_matches(me, user):
            continue
        if has_my_gps and user.latitude is not None and user.longitude is not None:
            if not (min_lat <= user.latitude <= max_lat and min_lon <= user.longitude <= max_lon):
                continue
            distance = distance_km(me.latitude, me.longitude, user.latitude, user.longitude)
            if distance <= radius:
                results.append((user, distance))
            continue
        if not has_my_gps and my_area and area_group(user.city) == my_area:
            results.append((user, None))

    def visibility_key(item):
        user, distance = item
        now = datetime.utcnow()
        featured = 0 if user.featured_until and user.featured_until > now else 1
        boosted = 0 if user.boost_until and user.boost_until > now else 1
        no_distance = distance is None
        return (featured, boosted, no_distance, distance if distance is not None else 999999)

    results.sort(key=visibility_key)
    return results[:limit]

@app.context_processor
def inject_globals():
    user = current_user()
    return {
        'current_user': user,
        'prices': PRICES,
        'mtn_momo_number': MTN_MOMO_NUMBER,
        'active_plan': active_plan(user),
        'credits_balance': user.credits if user else 0,
        'momo_auto_enabled': momo_configured(),
        'photo_url': photo_url,
        'profile_photos': profile_photos,
        'ensure_referral_code': ensure_referral_code,
    }

@app.route('/')
def home():
    if session.get('user_id'):
        return redirect(url_for('discover'))
    return render_template('landing.html')

@app.get('/invite')
@login_required
def invite_friends():
    me = current_user()
    code = ensure_referral_code(me)
    referral_url = url_for('register', ref=code, _external=True)
    return render_template('invite.html', referral_url=referral_url, referral_code=code)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        try:
            name = request.form['name'].strip()
            email = request.form['email'].strip().lower()
            password = request.form['password']
            age = int(request.form['age'])
            referral_code = (request.form.get('ref') or request.args.get('ref') or '').strip().upper()[:24]
            min_age = max(18, min(100, int(request.form.get('min_age', 18))))
            max_age = max(18, min(100, int(request.form.get('max_age', 60))))
        except (KeyError, ValueError):
            flash('Please complete all required fields.', 'error')
            return render_template('register.html')
        if min_age > max_age:
            min_age, max_age = max_age, min_age

        gender = request.form['gender']
        interested_in = request.form['interested_in']
        city = request.form.get('city', 'Kampala')
        photos = []
        for slot in range(1, 7):
            photo = clean_profile_photo(request.form.get(f'photo{slot}_data', ''))
            if photo:
                photos.append(photo)

        if age < 18:
            flash('Uganda Dating is for adults 18+ only.', 'error')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'error')
            return render_template('register.html')
        if len(photos) < 2:
            flash('Please add at least two clear photos of yourself from your gallery.', 'error')
            return render_template('register.html')

        referrer = User.query.filter_by(referral_code=referral_code).first() if referral_code else None
        if referrer and referrer.id == getattr(current_user(), 'id', None):
            referrer = None

        new_referral_code = uuid.uuid4().hex[:10].upper()
        while User.query.filter_by(referral_code=new_referral_code).first():
            new_referral_code = uuid.uuid4().hex[:10].upper()

        data = {
            'name': name, 'email': email,
            'password_hash': generate_password_hash(password),
            'age': age, 'gender': gender, 'interested_in': interested_in,
            'city': city, 'min_age': min_age, 'max_age': max_age,
            'photo1_data': photos[0], 'photo2_data': photos[1],
            'bio': 'New on Uganda Dating. Looking forward to meeting someone genuine!',
            'referred_by_id': referrer.id if referrer else None,
            'referral_code': new_referral_code
        }
        for slot, photo in enumerate(photos[2:6], start=3):
            data[f'photo{slot}_data'] = photo
        user = User(**data)
        db.session.add(user)
        db.session.commit()
        user.photo = url_for('user_photo', user_id=user.id, slot=1)
        if referrer:
            referrer.credits = (referrer.credits or 0) + 5
            user.credits = (user.credits or 0) + 2
        db.session.commit()
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
    me.last_seen = datetime.utcnow()
    db.session.commit()
    nearby = nearby_profiles(me, limit=200)
    return render_template('discover.html', nearby=nearby, radius=me.search_radius_km or 25, has_location=me.latitude is not None and me.longitude is not None)

@app.route('/member/<int:user_id>')
@login_required
def view_member_profile(user_id):
    me = current_user()
    member = db.session.get(User, user_id)
    if not member or member.id == me.id:
        flash('That profile is not available.', 'error')
        return redirect(url_for('discover'))
    blocked = Block.query.filter(
        ((Block.blocker_id == me.id) & (Block.blocked_id == member.id)) |
        ((Block.blocker_id == member.id) & (Block.blocked_id == me.id))
    ).first()
    if blocked:
        flash('This profile is unavailable because one of you has blocked the other.', 'error')
        return redirect(url_for('discover'))
    me.last_seen = datetime.utcnow()
    db.session.commit()
    distance = None
    if me.latitude is not None and me.longitude is not None and member.latitude is not None and member.longitude is not None:
        distance = distance_km(me.latitude, me.longitude, member.latitude, member.longitude)
    online = bool(member.last_seen and member.last_seen >= datetime.utcnow() - timedelta(minutes=10))
    liked = Like.query.filter_by(from_id=me.id, to_id=member.id).first() is not None
    mutual = Like.query.filter_by(from_id=member.id, to_id=me.id).first() is not None
    return render_template('member_profile.html', member=member, distance=distance, online=online, liked=liked, mutual=mutual)

@app.post('/member/<int:user_id>/block')
@login_required
def block_member(user_id):
    me = current_user()
    member = db.session.get(User, user_id)
    if not member or member.id == me.id:
        flash('That profile is not available.', 'error')
        return redirect(url_for('discover'))
    existing = Block.query.filter_by(blocker_id=me.id, blocked_id=member.id).first()
    if not existing:
        db.session.add(Block(blocker_id=me.id, blocked_id=member.id))
        db.session.commit()
    flash(f'{member.name} has been blocked. You will no longer see this profile.', 'success')
    return redirect(url_for('discover'))

@app.post('/member/<int:user_id>/report')
@login_required
def report_member(user_id):
    me = current_user()
    member = db.session.get(User, user_id)
    if not member or member.id == me.id:
        flash('That profile is not available.', 'error')
        return redirect(url_for('discover'))
    category = (request.form.get('category') or 'Other').strip()[:60]
    details = (request.form.get('details') or '').strip()[:1000]
    db.session.add(Report(reporter_id=me.id, reported_id=member.id, category=category, details=details))
    db.session.commit()
    flash('Thanks for helping keep Uganda Dating safe. Your report was sent to our moderation team.', 'success')
    return redirect(url_for('discover'))

@app.post('/location')
@login_required
def update_location():
    me = current_user()
    try:
        lat = float(request.form.get('latitude', ''))
        lon = float(request.form.get('longitude', ''))
        radius = float(request.form.get('search_radius_km', me.search_radius_km or 25))
        accuracy = float(request.form.get('accuracy', '0') or 0)
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'Invalid location or range.'}), 400
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify({'ok': False, 'error': 'Invalid coordinates.'}), 400
    if accuracy < 0 or accuracy > 100000:
        accuracy = 0
    me.latitude, me.longitude = lat, lon
    me.location_accuracy_m = accuracy or me.location_accuracy_m
    me.search_radius_km = max(1, min(radius, 500))
    db.session.commit()
    return jsonify({'ok': True, 'radius': me.search_radius_km, 'accuracy_m': me.location_accuracy_m})

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
    if me.id == user_id:
        return jsonify({'ok': False})
    blocked = Block.query.filter(
        ((Block.blocker_id == me.id) & (Block.blocked_id == user_id)) |
        ((Block.blocker_id == user_id) & (Block.blocked_id == me.id))
    ).first()
    if blocked:
        return jsonify({'ok': False, 'error': 'This profile is unavailable.'}), 403
    kind = request.form.get('kind','like')
    if kind == 'superlike':
        if (me.super_likes or 0) > 0:
            me.super_likes -= 1
        elif (me.credits or 0) >= 3:
            me.credits -= 3
        else:
            return jsonify({'ok': False, 'error': 'You need a Special Like or 3 credits.', 'upgrade': url_for('premium')}), 402
    existing = Like.query.filter_by(from_id=me.id, to_id=user_id).first()
    if not existing:
        db.session.add(Like(from_id=me.id, to_id=user_id, kind=kind))
        db.session.commit()
    mutual = Like.query.filter_by(from_id=user_id, to_id=me.id).first()
    return jsonify({'ok': True, 'match': bool(mutual)})

@app.route('/likes')
@login_required
def likes():
    me = current_user()
    incoming = Like.query.filter_by(to_id=me.id).order_by(Like.created_at.desc()).all()
    if not has_plan(me, 'gold'):
        return render_template('likes.html', liked_users=[], locked=True, like_count=len(incoming))
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
    liked_ids = {x.to_id for x in Like.query.filter_by(from_id=me.id).all()}
    me.last_seen = datetime.utcnow()
    db.session.commit()
    nearby = nearby_profiles(me, liked_ids, 30)
    return render_template('encounters.html', nearby=nearby, radius=me.search_radius_km or 25, has_location=me.latitude is not None and me.longitude is not None)

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

@app.route('/swipe')
@login_required
def swipe():
    return redirect(url_for('discover'))

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
    blocked = Block.query.filter(
        ((Block.blocker_id == me.id) & (Block.blocked_id == other.id)) |
        ((Block.blocker_id == other.id) & (Block.blocked_id == me.id))
    ).first()
    if blocked:
        flash('Messaging is unavailable because one of you has blocked the other.', 'error')
        return redirect(url_for('chats'))
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
        me.name = request.form['name'].strip()
        me.city = request.form.get('city', 'Kampala')
        me.gender = request.form.get('gender', me.gender)
        me.interested_in = request.form.get('interested_in', me.interested_in)
        me.bio = request.form.get('bio', '').strip()
        me.mood = request.form.get('mood', '').strip()[:120]
        me.relationship_status = request.form.get('relationship_status', '').strip()[:60]
        me.relationship_goal = request.form.get('relationship_goal', '').strip()[:80]
        me.smoking = request.form.get('smoking', '').strip()[:40]
        me.religion = request.form.get('religion', '').strip()[:80]
        me.languages = request.form.get('languages', '').strip()[:200]
        me.work = request.form.get('work', '').strip()[:160]
        me.education = request.form.get('education', '').strip()[:160]
        me.interests = request.form.get('interests', '').strip()[:500]
        try:
            me.search_radius_km = max(1, min(float(request.form.get('search_radius_km', me.search_radius_km or 25)), 500))
        except ValueError:
            pass
        try:
            min_age = max(18, min(100, int(request.form.get('min_age', me.min_age or 18))))
            max_age = max(18, min(100, int(request.form.get('max_age', me.max_age or 60))))
            if min_age > max_age:
                min_age, max_age = max_age, min_age
            me.min_age, me.max_age = min_age, max_age
        except ValueError:
            pass
        for slot in range(1, 7):
            incoming = request.form.get(f'photo{slot}_data', '')
            if incoming:
                cleaned = clean_profile_photo(incoming)
                if cleaned:
                    setattr(me, f'photo{slot}_data', cleaned)
        me.photo = url_for('user_photo', user_id=me.id, slot=1) if me.photo1_data else me.photo
        db.session.commit()
        flash('Profile updated.', 'success')
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
        if not phone:
            flash('Enter the MTN number that will authorize this payment.', 'error')
            return render_template('payment.html', plan=plan, product=product, auto_payment=momo_configured())

        if momo_configured():
            reference = str(uuid.uuid4())
            pay = Payment(
                user_id=current_user().id,
                plan=plan,
                amount=product['price'],
                payer_phone=normalize_mtn_msisdn(phone),
                transaction_id=reference,
                status='pending'
            )
            db.session.add(pay)
            db.session.commit()
            try:
                momo_request_to_pay(product['price'], phone, reference, product['name'])
                return render_template(
                    'payment.html',
                    plan=plan,
                    product=product,
                    momo_reference=reference,
                    auto_payment=True
                )
            except Exception:
                db.session.delete(pay)
                db.session.commit()
                flash('We could not start the MTN Mobile Money request. Please try again.', 'error')
                return render_template('payment.html', plan=plan, product=product, auto_payment=True)

        txid = request.form.get('transaction_id','').strip()
        if not txid:
            flash('Enter your MTN transaction ID after completing the payment.', 'error')
            return render_template('payment.html', plan=plan, product=product, auto_payment=False)
        if Payment.query.filter_by(transaction_id=txid).first():
            flash('That transaction ID has already been submitted.', 'error')
            return render_template('payment.html', plan=plan, product=product, auto_payment=False)
        pay = Payment(
            user_id=current_user().id,
            plan=plan,
            amount=product['price'],
            payer_phone=normalize_mtn_msisdn(phone),
            transaction_id=txid
        )
        db.session.add(pay)
        db.session.commit()
        flash('Payment submitted. Your purchase will activate after verification.', 'success')
        return redirect(url_for('premium'))
    return render_template('payment.html', plan=plan, product=product, auto_payment=momo_configured())

@app.get('/momo/status/<reference>')
@login_required
def momo_status(reference):
    payment = Payment.query.filter_by(transaction_id=reference, user_id=current_user().id).first()
    if not payment:
        return jsonify({'ok': False, 'error': 'Payment not found.'}), 404
    if payment.status != 'verified' and momo_configured():
        try:
            result = momo_payment_status(reference)
            status = str(result.get('status', '')).upper()
            if status in ('SUCCESSFUL', 'SUCCESS'):
                payment.status = 'verified'
                payment.verified_at = datetime.utcnow()
                activate_purchase(current_user(), payment.plan)
                db.session.commit()
            elif status in ('FAILED', 'REJECTED', 'CANCELLED', 'TIMEOUT'):
                payment.status = 'rejected'
                db.session.commit()
                return jsonify({'ok': True, 'status': 'failed'})
        except Exception:
            pass
    return jsonify({'ok': True, 'status': payment.status})

@app.post('/momo/callback')
def momo_callback():
    data = request.get_json(silent=True) or {}
    reference = request.headers.get('X-Reference-Id') or data.get('externalId') or data.get('referenceId')
    status = str(data.get('status', '')).upper()
    if reference:
        payment = Payment.query.filter_by(transaction_id=reference).first()
        if payment and status in ('SUCCESSFUL', 'SUCCESS'):
            payment.status = 'verified'
            payment.verified_at = datetime.utcnow()
            user = db.session.get(User, payment.user_id)
            if user:
                activate_purchase(user, payment.plan)
            db.session.commit()
        elif payment and status in ('FAILED', 'REJECTED', 'CANCELLED', 'TIMEOUT'):
            payment.status = 'rejected'
            db.session.commit()
    return '', 204

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
    base_until = max(user.premium_until or now, now)
    if plan in ('plus', 'gold', 'platinum', 'premium'):
        user.subscription_plan = {'premium': 'gold'}.get(plan, plan)
        user.premium_until = base_until + timedelta(days=30)
        user.unlimited_until = user.premium_until
        if plan in ('gold', 'platinum', 'premium'):
            user.likes_until = user.premium_until
        if plan in ('gold', 'premium'):
            user.super_likes = (user.super_likes or 0) + 5
            user.credits = (user.credits or 0) + 10
        elif plan == 'platinum':
            user.super_likes = (user.super_likes or 0) + 10
            user.credits = (user.credits or 0) + 20
    elif plan == 'likes':
        user.likes_until = max(user.likes_until or now, now) + timedelta(days=7)
    elif plan == 'unlimited':
        user.unlimited_until = max(user.unlimited_until or now, now) + timedelta(days=7)
    elif plan == 'boost':
        user.boost_until = max(user.boost_until or now, now) + timedelta(minutes=30)
    elif plan == 'featured':
        user.featured_until = max(user.featured_until or now, now) + timedelta(days=7)
    elif plan == 'superlike':
        user.super_likes = (user.super_likes or 0) + 1
    elif plan == 'credits10':
        user.credits = (user.credits or 0) + 10
    elif plan == 'credits25':
        user.credits = (user.credits or 0) + 25
    elif plan == 'credits60':
        user.credits = (user.credits or 0) + 60

@app.route('/admin/reports')
@admin_required
def admin_reports():
    reports = Report.query.order_by(Report.created_at.desc()).all()
    return render_template('admin_reports.html', reports=reports)

@app.post('/admin/reports/<int:report_id>/resolve')
@admin_required
def resolve_report(report_id):
    report = db.session.get(Report, report_id)
    if report:
        report.status = 'resolved'
        report.reviewed_at = datetime.utcnow()
        db.session.commit()
        flash('Report marked resolved.', 'success')
    return redirect(url_for('admin_reports'))

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

@app.get('/privacy')
def privacy():
    return render_template('legal.html', page='privacy')

@app.get('/terms')
def terms():
    return render_template('legal.html', page='terms')

@app.get('/community-guidelines')
def community_guidelines():
    return render_template('legal.html', page='guidelines')

@app.get('/child-safety')
def child_safety():
    return render_template('legal.html', page='child_safety')

CITY_PAGES = {
    'kampala': {'name':'Kampala','areas':'Kololo, Ntinda, Bugolobi, Muyenga, Makindye, Bukoto, Kabalagala, Kansanga and nearby areas','title':'Dating in Kampala, Uganda | Meet Singles Near You','description':'Meet singles in Kampala with Uganda Dating. Discover compatible people nearby, browse full profiles, like, match and chat.','intro':'Looking for a dating app in Kampala? Uganda Dating helps adults discover compatible singles around Kampala and its neighbourhoods with smart age, gender and distance preferences.'},
    'wakiso': {'name':'Wakiso','areas':'Kira, Najjera, Kira Road, Kiwatule, Kyaliwajjala and nearby areas','title':'Dating in Wakiso, Uganda | Meet Singles Near You','description':'Meet singles in Wakiso on Uganda Dating. Discover compatible people around Kira, Najjera and nearby areas.','intro':'Meet people in Wakiso without endless searching. Uganda Dating lets you focus on compatible singles around Kira, Najjera and surrounding communities.'},
    'entebbe': {'name':'Entebbe','areas':'Entebbe town and surrounding communities','title':'Dating in Entebbe, Uganda | Meet Singles Near You','description':'Meet singles in Entebbe with Uganda Dating. Discover genuine connections nearby and start real conversations.','intro':'Dating in Entebbe can be more personal when you meet people nearby. Uganda Dating helps adults discover compatible local connections and start conversations.'},
    'jinja': {'name':'Jinja','areas':'Jinja City and surrounding communities','title':'Dating in Jinja, Uganda | Meet Singles Near You','description':'Meet singles in Jinja on Uganda Dating. Discover compatible people nearby and build genuine connections.','intro':'Whether you live in Jinja or are new to the city, Uganda Dating gives you a modern way to discover compatible adults nearby.'},
    'mbarara': {'name':'Mbarara','areas':'Mbarara City and surrounding communities','title':'Dating in Mbarara, Uganda | Meet Singles Near You','description':'Meet singles in Mbarara with Uganda Dating. Browse profiles, match and chat with people nearby.','intro':'Discover dating in Mbarara with people who fit your preferences. Browse profiles, open full galleries and connect at your own pace.'},
    'gulu': {'name':'Gulu','areas':'Gulu City and surrounding communities','title':'Dating in Gulu, Uganda | Meet Singles Near You','description':'Meet singles in Gulu on Uganda Dating. Discover compatible people nearby and start meaningful conversations.','intro':'Uganda Dating brings a modern dating experience to Gulu, making it easier to discover compatible adults and start genuine conversations.'},
    'mbale': {'name':'Mbale','areas':'Mbale City and surrounding communities','title':'Dating in Mbale, Uganda | Meet Singles Near You','description':'Meet singles in Mbale with Uganda Dating. Discover nearby profiles, matches and real conversations.','intro':'Meet people around Mbale using age, gender, activity and distance preferences designed to help you find better matches.'}
}

@app.get('/dating/<city_slug>')
def city_landing(city_slug):
    city = CITY_PAGES.get(city_slug.lower())
    if not city:
        return render_template('404.html'), 404
    return render_template('seo_city.html', city=city, slug=city_slug.lower())

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
            'search_radius_km': 'DOUBLE PRECISION DEFAULT 25',
            'location_accuracy_m': 'DOUBLE PRECISION',
            'last_seen': 'TIMESTAMP',
            'min_age': 'INTEGER DEFAULT 18',
            'max_age': 'INTEGER DEFAULT 60',
            'mood': 'VARCHAR(120)',
            'relationship_status': 'VARCHAR(60)',
            'relationship_goal': 'VARCHAR(80)',
            'smoking': 'VARCHAR(40)',
            'religion': 'VARCHAR(80)',
            'languages': 'VARCHAR(200)',
            'work': 'VARCHAR(160)',
            'education': 'VARCHAR(160)',
            'interests': 'VARCHAR(500)',
            'subscription_plan': "VARCHAR(20) DEFAULT 'free'",
            'credits': 'INTEGER DEFAULT 0',
            'photo1_data': 'TEXT',
            'photo2_data': 'TEXT',
            'photo3_data': 'TEXT',
            'photo4_data': 'TEXT',
            'photo5_data': 'TEXT',
            'photo6_data': 'TEXT',
            'referral_code': 'VARCHAR(24)',
            'referred_by_id': 'INTEGER'
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
            'search_radius_km': 'FLOAT DEFAULT 25',
            'location_accuracy_m': 'FLOAT',
            'last_seen': 'DATETIME',
            'min_age': 'INTEGER DEFAULT 18',
            'max_age': 'INTEGER DEFAULT 60',
            'mood': 'VARCHAR(120)',
            'relationship_status': 'VARCHAR(60)',
            'relationship_goal': 'VARCHAR(80)',
            'smoking': 'VARCHAR(40)',
            'religion': 'VARCHAR(80)',
            'languages': 'VARCHAR(200)',
            'work': 'VARCHAR(160)',
            'education': 'VARCHAR(160)',
            'interests': 'VARCHAR(500)',
            'subscription_plan': "VARCHAR(20) DEFAULT 'free'",
            'credits': 'INTEGER DEFAULT 0',
            'photo1_data': 'TEXT',
            'photo2_data': 'TEXT',
            'photo3_data': 'TEXT',
            'photo4_data': 'TEXT',
            'photo5_data': 'TEXT',
            'photo6_data': 'TEXT',
            'referral_code': 'VARCHAR(24)',
            'referred_by_id': 'INTEGER'
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
