import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify
from flask_dance.contrib.google import make_google_blueprint, google
from flask_sqlalchemy import SQLAlchemy
from flask_login import login_required, current_user

db = SQLAlchemy()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'  # atau sesuai DB kamu
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

import os
from dotenv import load_dotenv
load_dotenv()

app.secret_key = os.getenv("SECRET_KEY")  # penting untuk session login

google_bp = make_google_blueprint(
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    scope=[
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid"
    ],
    redirect_to="google_callback"
)

app.register_blueprint(google_bp, url_prefix="/login")

@app.route('/')
def index():
    print("Akses ke / - session:", session)
    if not session.get('user_id'):
        print("Belum login, redirect ke /login")
        return redirect('/login')
    print("Sudah login, render index")
    return render_template('index.html')

@app.route("/login/google/authorized")
def google_login():
    if not google.authorized:
        return redirect(url_for("google.login"))

    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return "Gagal mengambil data dari Google", 500

    user_info = resp.json()
    session["user_email"] = user_info["email"]
    session["user_name"] = user_info.get("name", "Guest")
    session["user_avatar"] = user_info.get("picture", "")
    return redirect(url_for("index"))  # atau redirect ke halaman utama kamu

@app.route("/login")
def login():
    if not google.authorized:
        return redirect(url_for("google.login"))

    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return "Gagal mengambil data user dari Google", 500

    user_info = resp.json()
    user_email = user_info["email"]
    user_name = user_info.get("name", "Guest")

    # Simpan ke database
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Cek apakah user sudah ada
    c.execute("SELECT id FROM users WHERE email = ?", (user_email,))
    row = c.fetchone()

    if row:
        user_id = row[0]
    else:
        # Tambahkan user baru
        c.execute("INSERT INTO users (username, email, name) VALUES (?, ?, ?)", (user_name, user_email, user_name))
        conn.commit()
        user_id = c.lastrowid

    conn.close()

    # Simpan ke session
    session["user_id"] = user_id
    session["user_email"] = user_email
    session["user_name"] = user_name
    session["user_avatar"] = user_info.get("picture", "")

    return redirect(url_for("index"))

@app.route("/login/google/callback")
def google_callback():
    if not google.authorized:
        return redirect(url_for("google.login"))

    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return f"Error saat mengambil data user: {resp.text}"

    user_info = resp.json()
    user_email = user_info["email"]
    user_name = user_info["name"]
    user_avatar = user_info.get("picture", "")

    # Cek atau tambahkan user ke database
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email = ?", (user_email,))
    user = cur.fetchone()

    if user:
        user_id = user[0]
    else:
        import random
        import string

        def generate_referral_code():
            return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        ref_code = generate_referral_code()

        c.execute("INSERT INTO users (name, email, avatar, balance, referral_code) VALUES (?, ?, ?, ?, ?)",
                (user_name, user_email, user_avatar, 0, ref_code))

        conn.commit()
        user_id = cur.lastrowid  # ambil ID user yang baru dibuat

    conn.close()

    # Simpan ke session
    session['user_id'] = user_id
    session["user_email"] = user_email
    session["user_name"] = user_name
    session["user_avatar"] = user_avatar
    session["user_balance"] = 0  # Optional: ambil dari DB kalau perlu

    return redirect(url_for("index"))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    
    user = get_user_by_id(session['user_id'])

    # ⬇️ Tambahkan rewards dummy (atau ambil dari sistem kamu)
    rewards = [100, 200, 300, 400, 500, 600, 1000]

    # ⬇️ Cek status check-in dari database (7 hari terakhir)
    user_id = session['user_id']
    checkins = []
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    for i in range(7):
        tanggal = (datetime.now() - timedelta(days=6 - i)).strftime('%Y-%m-%d')
        c.execute("SELECT 1 FROM task_claims WHERE user_id=? AND task_title='checkin' AND tanggal=?", 
                (user_id, tanggal))
        result = c.fetchone()
        checkins.append(bool(result))
    conn.close()

    # ⬇️ Siapkan dummy task harian atau ambil dari logic kamu
    tasks = [
        {"title": "login hari ini", "reward": 100, "status": "done", "claimed": False, "link": "#"},
        {"title": "selesaikan 1 misi offers", "reward": 1000, "status": "pending", "claimed": False, "link": "/offers"}
    ]

        # ⬇️ Ambil jumlah permen user
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT candy_balance FROM users WHERE id = ?", (user_id,))
    result = c.fetchone()
    candy_balance = result[0] if result else 0
    conn.close()

    return render_template('dashboard.html',
    user=user,
    rewards=rewards,
    checkins=checkins,
    tasks=tasks,
    candy_balance=candy_balance  # ⬅️ Tambahan ini penting!
)

@app.before_request
def load_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id:
        g.user = get_user_by_id(user_id)
def get_user_by_id(user_id):
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    return user

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    with sqlite3.connect('database.db') as conn:
        cur = conn.cursor()
        cur.execute("SELECT name, email FROM users WHERE id = ?", (session['user_id'],))
        row = cur.fetchone()

    if row:
        user = {
            "name": row[0],
            "email": row[1],
            "avatar": session.get("user_avatar", "/static/img/default-avatar.png")  # default kalau kosong
        }
    else:
        user = {
            "name": "Unknown",
            "email": "Not Found",
            "avatar": "/static/img/default-avatar.png"
        }

    return render_template("profile.html", user=user)

@app.route("/edit_profile", methods=["POST"])
def edit_profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    username = request.form.get("username")
    email = request.form.get("email")

    cur = conn.cursor()
    cur.execute("UPDATE users SET username = ?, email = ? WHERE id = ?", (username, email, session["user_id"]))
    conn.commit()

    return redirect(url_for("profile"))

@app.route("/logout")
def logout():
    if google.authorized:
        del google.token
    return redirect(url_for("index"))


@app.route("/game-shop")
def game_shop():
    if "user_email" not in session:
        return redirect(url_for("login"))
    return render_template("game_shop.html")

@app.route("/offers")
def offers():
    return render_template("offers.html")

@app.route('/bitlabs')
def bitlabs():
    return render_template('bitlabs.html')

# Contoh data dummy
daily_tasks = [
    {"id": 1, "title": "Login Hari Ini", "reward": 500, "completed": False, "claimable": True, "action_url": "#"},
    {"id": 2, "title": "Kunjungi Halaman Misi", "reward": 300, "completed": False, "claimable": False, "action_url": "/misi"},
    {"id": 3, "title": "Nonton Iklan", "reward": 700, "completed": True, "claimable": False, "action_url": "#"},
]


    
import sqlite3

conn = sqlite3.connect("database.db")
cur = conn.cursor()

# Tambah kolom jika belum ada (try-catch untuk cegah error jika sudah ada)
try:
    cur.execute("ALTER TABLE users ADD COLUMN email TEXT")
except:
    pass
try:
    cur.execute("ALTER TABLE users ADD COLUMN name TEXT")
except:
    pass
try:
    cur.execute("ALTER TABLE users ADD COLUMN avatar TEXT")
except:
    pass
try:
    cur.execute("ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0")
except:
    pass
try:
    cur.execute("ALTER TABLE users ADD COLUMN referral_code TEXT")
except:
    pass

conn.commit()
conn.close()

print("Kolom berhasil ditambahkan jika belum ada.")

import sqlite3

def create_tables():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Tabel users
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT,
        poin INTEGER DEFAULT 0,
        last_checkin TEXT DEFAULT '',
        checkin_streak INTEGER DEFAULT 0,
        candy_balance INTEGER DEFAULT 0
    )''')

    # Tabel daily_claims
    c.execute('''CREATE TABLE IF NOT EXISTS daily_claims (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        day INTEGER,
        claimed INTEGER DEFAULT 0,
        tanggal TEXT
    )''')

    # Tabel task_claims
    c.execute('''CREATE TABLE IF NOT EXISTS task_claims (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_title TEXT,
        claimed INTEGER DEFAULT 1,
        tanggal TEXT
    )''')

    conn.commit()
    conn.close()

def init_checkin_table():
    with sqlite3.connect('database.db') as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS checkin_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                checkin_date DATE,
                day_index INTEGER
            )
        ''')

from datetime import datetime, timedelta, date

def get_today_checkin(user_id):
    today = date.today()
    with sqlite3.connect('database.db') as conn:
        cur = conn.cursor()
        cur.execute("SELECT day_index FROM checkin_log WHERE user_id=? AND checkin_date=?", (user_id, today))
        row = cur.fetchone()
        return row[0] if row else None

@app.route('/checkin', methods=['POST'])
def checkin():
    if 'user_id' not in session:
        return redirect('/login')
    
    user_id = session['user_id']
    today = date.today()

    # Cek apakah sudah checkin hari ini
    if get_today_checkin(user_id) is not None:
        return 'Sudah check-in hari ini!', 400

    # Hitung hari ke berapa berdasarkan total check-in sebelumnya
    with sqlite3.connect('database.db') as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM checkin_log WHERE user_id=?", (user_id,))
        total_checkin = cur.fetchone()[0]
        day_index = total_checkin + 1

        cur.execute("INSERT INTO checkin_log (user_id, checkin_date, day_index) VALUES (?, ?, ?)", (user_id, today, day_index))
        conn.commit()

    return jsonify({'success': True, 'day_index': day_index})

@app.route('/checkin-status')
def checkin_status():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    with sqlite3.connect('database.db') as conn:
        cur = conn.cursor()
        cur.execute("SELECT day_index, checkin_date FROM checkin_log WHERE user_id=? ORDER BY day_index", (user_id,))
        data = cur.fetchall()
        return jsonify(data)

@app.route('/penarikan')
def penarikan():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Ambil balance
    c.execute("SELECT candy_balance FROM users WHERE id = ?", (user_id,))
    result = c.fetchone()
    candy_balance = result[0] if result else 0
    rupiah_estimate = candy_balance * 100 / 1000

    # Ambil riwayat penarikan
    c.execute("SELECT method, candy_amount, rupiah_amount, status, created_at FROM withdrawals WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    history = c.fetchall()

    conn.close()

    return render_template('penarikan.html',
        candy_balance=candy_balance,
        rupiah_estimate=rupiah_estimate,
        withdraw_history=history
    )

conn = sqlite3.connect("database.db")
cur = conn.cursor()
cur.execute('''
CREATE TABLE IF NOT EXISTS withdrawals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    method TEXT,
    candy_amount INTEGER,
    rupiah_amount INTEGER,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()
conn.close()

@app.route('/withdraw', methods=['POST'])
def withdraw():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    method = request.form['method']
    rupiah = int(request.form['amount'])

    candy_cost = int(rupiah * 100)  # karena 1000 candy = Rp 100

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Cek saldo
    c.execute("SELECT candy_balance FROM users WHERE id = ?", (user_id,))
    current_balance = c.fetchone()[0]
    if current_balance < candy_cost:
        conn.close()
        return "Saldo tidak cukup", 400

    # Kurangi saldo
    c.execute("UPDATE users SET candy_balance = candy_balance - ? WHERE id = ?", (candy_cost, user_id))

    # Simpan riwayat penarikan
    c.execute("""
        INSERT INTO withdrawals (user_id, method, candy_amount, rupiah_amount, status)
        VALUES (?, ?, ?, ?, 'pending')
    """, (user_id, method, candy_cost, rupiah))

    conn.commit()
    conn.close()

    return redirect('/penarikan')

@app.route('/add-candy', methods=['POST'])
def add_candy():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    data = request.get_json()
    amount = int(data.get('amount', 0))

    user_id = session['user_id']

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE users SET candy_balance = candy_balance + ? WHERE id = ?", (amount, user_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route('/tap', methods=['POST'])
def tap():
    if 'user_id' not in session:
        return jsonify({"success": False}), 401

    user_id = session['user_id']
    data = request.get_json()
    amount = data.get("amount", 0)

    # Tambahkan candy ke user di database
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("UPDATE users SET candy = candy + ? WHERE id = ?", (amount, user_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True})

@app.route('/claim-task', methods=['POST'])
def claim_task():
    user_id = session.get('user_id')
    task_title = request.json.get('task_title')
    tanggal = datetime.now().strftime('%Y-%m-%d')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Cek apakah sudah klaim sebelumnya
    c.execute("SELECT * FROM task_claims WHERE user_id=? AND task_title=? AND tanggal=?", 
              (user_id, task_title, tanggal))
    if c.fetchone():
        conn.close()
        return jsonify({'status': 'already_claimed'})

    c.execute("INSERT INTO task_claims (user_id, task_title, claimed, tanggal) VALUES (?, ?, 1, ?)", 
              (user_id, task_title, tanggal))
    conn.commit()
    conn.close()
    return jsonify({'status': 'claimed'})

DAILY_TASKS = [
    {
        'id': 1,
        'title': 'Main Candy Machine 10x',
        'completed': False,
        'link': '/candy',
    },
    {
        'id': 2,
        'title': 'Lihat Toko 1x',
        'completed': False,
        'link': '/shop',
    },
]

@app.route("/toko")
def toko():
    items = [
        {"id": 1, "name": "Paket Hemat", "price_rp": 5000, "description": "100 Diamond", "image": "paket-hemat.png"},
        {"id": 2, "name": "Paket Sultan", "price_rp": 20000, "description": "600 Diamond + Bonus", "image": "paket-sultan.png"},
        # dst...
    ]
    return render_template("toko.html", items=items)

@app.route('/bundle/<int:bundle_id>')
def bundle_detail(bundle_id):
    bundle = get_bundle_by_id(bundle_id)  # fungsi ini nanti kita buat
    if not bundle:
        return "Paket tidak ditemukan", 404
    return render_template('bundle_detail.html', bundle=bundle)

def get_bundle_by_id(bundle_id):
    for bundle in bundles:
        if bundle["id"] == bundle_id:
            return bundle
    return None

# views.py (Flask/Django-like pseudocode)

@app.route('/beli/<product_id>', methods=['POST'])
def beli_produk(product_id):
    user = get_current_user()
    produk = get_produk(product_id)

    if produk.kategori in ['diamond', 'akun']:
        if user.saldo_rp >= produk.harga:
            user.saldo_rp -= produk.harga
            user.riwayat_pembelian.append(produk)
            flash('Pembelian berhasil!')
        else:
            flash('Saldo tidak cukup.')
    return redirect(url_for('riwayat_pembelian'))

# models.py
class PremiumPurchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    package_id = db.Column(db.Integer, db.ForeignKey('premium_package.id'))
    status = db.Column(db.String(20), default='pending')  # pending, success, failed
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

@app.route('/premium/<int:package_id>')
def premium_detail(package_id):
    package = PremiumPackage.query.get_or_404(package_id)
    return render_template('premium/detail.html', package=package)

@app.route('/premium/<int:package_id>/checkout', methods=['GET', 'POST'])
@login_required
def premium_checkout(package_id):
    package = PremiumPackage.query.get_or_404(package_id)
    
    if request.method == 'POST':
        new_order = PremiumPurchase(
            user_id=current_user.id,
            package_id=package.id,
            status='success'  # nanti bisa diubah ke 'pending' kalau pakai gateway
        )
        db.session.add(new_order)
        db.session.commit()
        flash("Pembelian berhasil! Paket premium aktif.", "success")
        return redirect(url_for('premium_success', order_id=new_order.id))
    
    return render_template('premium/checkout.html', package=package)

@app.route('/premium/success/<int:order_id>')
@login_required
def premium_success(order_id):
    order = PremiumPurchase.query.get_or_404(order_id)
    return render_template('premium/success.html', order=order)

@app.route('/buy/<item_id>', methods=['POST'])
def buy(item_id):
    # Pastikan user login via session (kamu pakai flask-dance + session)
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Silakan login terlebih dahulu.'}), 401

    # Daftar item yang valid (sesuaikan jika mau ubah harga/jumlah)
    items = {
        "diamond50":  {"price": 5000,  "desc": "50 Diamond",  "type": "diamond", "amount": 50},
        "diamond150": {"price": 12000, "desc": "150 Diamond", "type": "diamond", "amount": 150},
        "diamond500": {"price": 35000, "desc": "500 Diamond", "type": "diamond", "amount": 500},
        "basic":      {"price": 10000, "desc": "Akun Basic",  "type": "account"},
        "pro":        {"price": 25000, "desc": "Akun Pro",    "type": "account"},
        "legend":     {"price": 50000, "desc": "Akun Legend", "type": "account"},
        # alias (jika frontend pake 'akun_basic' dsb.)
        "akun_basic": {"price": 10000, "desc": "Akun Basic",  "type": "account"},
        "akun_pro":   {"price": 25000, "desc": "Akun Pro",    "type": "account"},
        "akun_legend":{"price": 50000, "desc": "Akun Legend", "type": "account"},
    }

    if item_id not in items:
        return jsonify({"success": False, "message": "Item tidak ditemukan."}), 404

    item = items[item_id]
    user_id = session['user_id']

    # Ambil saldo user dari DB
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT balance, candy_balance FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False, 'message': 'User tidak ditemukan.'}), 404

    balance = row[0] or 0
    candy_balance = row[1] or 0
    price = int(item['price'])

    if balance < price:
        conn.close()
        return jsonify({'success': False, 'message': 'Saldo tidak cukup. Silakan top up.'}), 402

    # Proses: kurangi saldo
    c.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (price, user_id))

    # Jika paket diamond, tambahkan candy_balance (jumlah diamond)
    if item.get('type') == 'diamond':
        amount = int(item.get('amount', 0))
        c.execute("UPDATE users SET candy_balance = candy_balance + ? WHERE id = ?", (amount, user_id))

    # Buat tabel transaksi jika belum ada, lalu simpan transaksi
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    item_id TEXT,
                    item_desc TEXT,
                    price INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    c.execute("INSERT INTO transactions (user_id, item_id, item_desc, price) VALUES (?, ?, ?, ?)",
              (user_id, item_id, item['desc'], price))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Berhasil membeli {item['desc']} seharga Rp{price:,}",
        "redirect": url_for('toko')
    })

if __name__ == '__main__':
    create_tables()  # ← Panggil ini sebelum app.run
    init_checkin_table()
    app.run(debug=True)
