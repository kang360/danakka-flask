from flask import Flask, render_template, jsonify, request, redirect, session, flash
import sqlite3
import datetime
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
from flask_mail import Mail, Message
import threading
import time
from dotenv import load_dotenv

app = Flask(__name__)
CORS(app)
# ✅ 강제적으로 .env 파일 로드
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path, override=True)  # .env 파일 강제 로드

# ✅ 로드 확인 (디버깅)
print(f"✅ SECRET_KEY 로드 확인: {os.getenv('SECRET_KEY')}")
print(f"✅ MAIL_PASSWORD 로드 확인: {os.getenv('MAIL_PASSWORD')}")

app.secret_key = os.getenv('SECRET_KEY')
app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Flask-Mail 설정 (네이버 SMTP)
# Flask-Mail SSL (465) 설정
app.config['MAIL_SERVER'] = 'smtp.naver.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USERNAME'] = 'danakkafishing@naver.com'
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = 'danakkafishing@naver.com'

mail = Mail(app)

# DB 파일 경로
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users.db')
ALARM_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alarm.db')
CRUISE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cruise_schedule.db')
REVIEW_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reviews.db')

# DB 초기화 (테이블 생성)
def init_db():
    # users.db 초기화
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            nickname TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()

    # alarm.db 초기화
    conn = sqlite3.connect(ALARM_DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS alarms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            date TEXT, 
            zone TEXT, 
            ship_name TEXT, 
            email TEXT
        );
    """)
    conn.commit()
    conn.close()

    # cruise_schedule.db 초기화
    conn = sqlite3.connect(CRUISE_DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS cruise_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone TEXT, 
            site_name TEXT, 
            ship_name TEXT, 
            date TEXT, 
            wave_power TEXT, 
            fish_name TEXT, 
            reservation TEXT, 
            booking_url TEXT
        );
    """)
    conn.commit()
    conn.close()

        # reviews.db 초기화
    conn = sqlite3.connect(REVIEW_DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, 
            nickname TEXT, 
            review TEXT, 
            created_at TEXT,
            likes INTEGER DEFAULT 0
        );
    """)

    # 좋아요 기록 테이블 (user_id, review_id 중복 방지)
    c.execute("""
        CREATE TABLE IF NOT EXISTS review_likes (
            user_id INTEGER, 
            review_id INTEGER, 
            PRIMARY KEY (user_id, review_id)
        );
    """)
    conn.commit()
    conn.close()

# 앱 실행 시 DB 초기화
init_db()

# 루트 경로: 홈페이지
@app.route('/')
def home():
    return render_template('boot.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, nickname, email, password FROM users WHERE email=?", (email,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            session['user'] = {'id': user[0], 'email': user[2], 'nickname': user[1]}
            flash("로그인 성공!", "success")
            return redirect('/mypage')
        else:
            flash("이메일 또는 비밀번호가 일치하지 않습니다.", "danger")

    return render_template('login.html')

# 마이페이지 (사용자 정보 수정 및 탈퇴)
# 마이페이지 (예약 알림 및 회원 정보 수정)
@app.route('/mypage', methods=['GET', 'POST'])
def mypage():
    if 'user' not in session:
        flash("로그인이 필요합니다.", "warning")
        return redirect('/login')

    if request.method == 'POST':
        nickname = request.form.get('nickname')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # 현재 비밀번호 확인
        c.execute("SELECT password FROM users WHERE id=?", (session['user']['id'],))
        stored_password = c.fetchone()[0]

        if not check_password_hash(stored_password, current_password):
            flash("현재 비밀번호가 일치하지 않습니다.", "danger")
            return redirect('/mypage')

        # 비밀번호 변경 (새 비밀번호가 입력된 경우)
        if new_password:
            hashed_password = generate_password_hash(new_password)
            c.execute("UPDATE users SET nickname=?, password=? WHERE id=?",
                      (nickname, hashed_password, session['user']['id']))
        else:
            c.execute("UPDATE users SET nickname=? WHERE id=?",
                      (nickname, session['user']['id']))

        conn.commit()
        conn.close()

        session['user']['nickname'] = nickname
        flash("회원 정보가 수정되었습니다.", "success")

    # 예약 알림 조회 (로그인된 사용자)
    user_id = session['user']['id']
    conn = sqlite3.connect(ALARM_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, date, zone, ship_name FROM alarms WHERE user_id = ? ORDER BY date DESC", (user_id,))
    alarms = c.fetchall()
    conn.close()

    return render_template('mypage.html', user=session['user'], alarms=alarms)

# 예약 정보 API
@app.route('/api/reservations', methods=['GET'])
def get_reservations():
    date_param = request.args.get('date')
    print(f"📅 요청 날짜: {date_param} ({type(date_param)})")

    conn = sqlite3.connect('cruise_schedule.db')
    cursor = conn.cursor()

    # 날짜가 전달된 경우 필터링
    if date_param:
        try:
            parts = date_param.split("-")
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            weekday_ko = ["월", "화", "수", "목", "금", "토", "일"]
            weekday = weekday_ko[datetime.date(year, month, day).weekday()]
            db_date = f"{year}년 {month}월{day}일({weekday})"
            cursor.execute("SELECT * FROM cruise_schedule WHERE date = ?", (db_date,))
        except Exception as e:
            print(f"❌ 날짜 파싱 오류: {e}")
            return jsonify({"error": "날짜 형식이 잘못되었습니다."}), 400
    else:
        cursor.execute("SELECT * FROM cruise_schedule")

    rows = cursor.fetchall()
    columns = ['zone', 'site_name', 'ship_name', 'date', 'wave_power', 'fish_name', 'reservation', 'booking_url']
    results = [dict(zip(columns, row)) for row in rows]

    conn.close()
    return jsonify(results)
# 회원가입
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        nickname = request.form['nickname']
        password = request.form['password']

        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # 이메일과 닉네임 중복 체크
        c.execute("SELECT id FROM users WHERE email=? OR nickname=?", (email, nickname))
        existing_user = c.fetchone()
        if existing_user:
            flash("이미 등록된 이메일 또는 닉네임입니다.", "danger")
            return redirect('/register')

        # 중복이 없을 경우 저장
        c.execute("INSERT INTO users (email, nickname, password) VALUES (?, ?, ?)",
                  (email, nickname, hashed_password))
        conn.commit()
        flash("가입이 완료되었습니다. 로그인해주세요.", "success")
        conn.close()

        return redirect('/login')

    return render_template('register.html')
# 회원 탈퇴
@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user' not in session:
        flash("로그인이 필요합니다.", "warning")
        return redirect('/login')

    user_id = session['user']['id']

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    session.pop('user', None)
    flash("회원 탈퇴가 완료되었습니다.", "info")

    return redirect('/')

# 이용약관 페이지
@app.route('/terms')
def terms():
    return render_template('terms.html')

# 로그아웃
@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("로그아웃되었습니다.", "info")
    return redirect('/')
# 이용후기 페이지
@app.route('/review', methods=['GET', 'POST'])
def reviews():
    if request.method == 'POST':
        if 'user' not in session:
            flash("로그인이 필요합니다.", "warning")
            return redirect('/login')

        review_text = request.form['review']
        user_id = session['user']['id']
        nickname = session['user']['nickname']

        conn = sqlite3.connect(REVIEW_DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO reviews (user_id, nickname, review, created_at) VALUES (?, ?, ?, ?)",
                  (user_id, nickname, review_text, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()

        flash("후기가 등록되었습니다.", "success")
        return redirect('/review')

   # 후기 조회 (정렬 기준 적용)
    sort = request.args.get('sort', 'latest')
    conn = sqlite3.connect(REVIEW_DB_PATH)
    c = conn.cursor()

    if sort == 'popular':
        c.execute("SELECT id, user_id, nickname, review, created_at, likes FROM reviews ORDER BY likes DESC, created_at DESC")
    else:
        c.execute("SELECT id, user_id, nickname, review, created_at, likes FROM reviews ORDER BY created_at DESC")

    reviews = c.fetchall()
    conn.close()

    return render_template('review.html', reviews=reviews, user=session.get('user'), sort=sort)

# 후기 좋아요
@app.route('/like_review/<int:review_id>', methods=['POST'])
def like_review(review_id):
    if 'user' not in session:
        flash("로그인이 필요합니다.", "warning")
        return redirect('/login')

    user_id = session['user']['id']

    conn = sqlite3.connect(REVIEW_DB_PATH)
    c = conn.cursor()

    # 사용자가 이미 좋아요를 눌렀는지 확인
    c.execute("SELECT 1 FROM review_likes WHERE user_id = ? AND review_id = ?", (user_id, review_id))
    if c.fetchone():
        flash("이미 좋아요를 누르셨습니다.", "warning")
        return redirect('/review')

    # 좋아요 기록 저장
    c.execute("INSERT INTO review_likes (user_id, review_id) VALUES (?, ?)", (user_id, review_id))

    # 좋아요 수 증가
    c.execute("UPDATE reviews SET likes = likes + 1 WHERE id = ?", (review_id,))
    conn.commit()
    conn.close()

    flash("후기에 좋아요를 추가했습니다.", "success")
    return redirect('/review')


# 후기 수정 (페이지 없이 바로 수정)
@app.route('/edit_review/<int:review_id>', methods=['POST'])
def edit_review(review_id):
    if 'user' not in session:
        flash("로그인이 필요합니다.", "warning")
        return redirect('/login')

    new_review = request.form['review']

    conn = sqlite3.connect(REVIEW_DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE reviews SET review = ? WHERE id = ? AND user_id = ?",
              (new_review, review_id, session['user']['id']))
    conn.commit()
    conn.close()

    flash("후기가 수정되었습니다.", "success")
    return redirect('/review')

# 후기 삭제
@app.route('/delete_review/<int:review_id>', methods=['POST'])
def delete_review(review_id):
    if 'user' not in session:
        flash("로그인이 필요합니다.", "warning")
        return redirect('/login')

    conn = sqlite3.connect(REVIEW_DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM reviews WHERE id = ? AND user_id = ?", (review_id, session['user']['id']))
    conn.commit()
    conn.close()

    flash("후기가 삭제되었습니다.", "success")
    return redirect('/review')

# 이용후기 페이지 (추가 경로)
@app.route('/review', methods=['GET', 'POST'])
def review_redirect():
    return redirect('/review')

# 예약 알림 신청 (최대 3회 제한)
@app.route('/alarm_request', methods=['POST'])
def alarm_request():
    if 'user' not in session:
        if 'user' not in session:
            return jsonify({"message": "로그인이 필요합니다."}), 401

    date = request.form['date']
    zone = request.form['zone']
    ship_name = request.form['ship_name']
    user_id = session['user']['id']
    email = session['user']['email']  # 로그인된 이메일 자동 사용

    conn = sqlite3.connect(ALARM_DB_PATH)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM alarms WHERE user_id = ?", (user_id,))
    alarm_count = c.fetchone()[0]

    if alarm_count >= 3:
        return jsonify({"message": "예약 알림은 최대 3개까지 등록할 수 있습니다."}), 400
    
   

    # 알림 등록
    c.execute("INSERT INTO alarms (user_id, email, date, zone, ship_name) VALUES (?, ?, ?, ?, ?)",
              (user_id, email, date, zone, ship_name))
    conn.commit()
    conn.close()

    flash("예약 알림이 등록되었습니다.", "success")
    return redirect('/mypage')


# 예약 알림 삭제 (마이페이지에서)
@app.route('/delete_alarm/<int:alarm_id>', methods=['POST'])
def delete_alarm(alarm_id):
    if 'user' not in session:
        flash("로그인이 필요합니다.", "warning")
        return redirect('/login')

    user_id = session['user']['id']

    conn = sqlite3.connect(ALARM_DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM alarms WHERE id = ? AND user_id = ?", (alarm_id, user_id))
    conn.commit()
    conn.close()

    flash("예약 알림이 삭제되었습니다.", "success")
    return redirect('/mypage')


# ✅ 예약 상태 확인 함수 (먼저 정의)
def check_reservation_status(date, zone, ship_name):
    # 예약 데이터베이스 연결
    conn = sqlite3.connect(CRUISE_DB_PATH)
    cursor = conn.cursor()

    # 예약 상태와 URL 확인 (DB에서 확인)
    cursor.execute("""
        SELECT reservation, booking_url 
        FROM cruise_schedule 
        WHERE date = ? AND zone = ? AND ship_name = ?
    """, (date, zone, ship_name))
    result = cursor.fetchone()
    conn.close()

    if result:
        reservation_status, booking_url = result
        return reservation_status, booking_url
    else:
        return "마감", None

# ✅ 예약 알림 이메일 발송 함수 (SSL)
def send_alert_email(to_email, date, zone, ship_name, booking_url):
    subject = f'🚤 예약 알림: {date} - {zone} - {ship_name} 예약 가능!'
    message_body = f"""
    <h3>🚤 예약 알림</h3>
    <p>{date} - {zone} - {ship_name}에 예약 가능한 자리가 생겼습니다.</p>
    <p>지금 바로 확인하세요!</p>
    <a href="{booking_url}">예약 페이지로 이동</a>
    """

    # Flask 애플리케이션 컨텍스트 내에서 이메일 전송
    with app.app_context():
        msg = Message(subject, 
                      recipients=[to_email], 
                      sender=app.config['MAIL_DEFAULT_SENDER'])
        msg.html = message_body

        try:
            mail.send(msg)
            print(f"✅ 이메일 발송 완료: {to_email}")
        except Exception as e:
            print(f"❌ 이메일 발송 오류: {e}")

# ✅ 예약 알림 확인 및 이메일 발송
def check_reservation_alerts():
    conn = sqlite3.connect('E:/start python/20.혼자 공부/웹사이트 개발/alarm.db')
    cursor = conn.cursor()

    cursor.execute("SELECT id, date, zone, ship_name, email, user_id FROM alarms")
    alarms = cursor.fetchall()

    for alarm in alarms:
        alarm_id, date, zone, ship_name, email, user_id = alarm

        # ✅ 예약 상태 확인
        reservation_status, booking_url = check_reservation_status(date, zone, ship_name)
        print(f"✅ 예약 상태 확인: {reservation_status}, URL: {booking_url}")

        # 예약 상태가 "마감"이 아니고 URL이 있을 경우
        if reservation_status not in ["마감", "예약 마감"] and booking_url:
            send_alert_email(email, date, zone, ship_name, booking_url)
            print(f"✅ 이메일 전송: {email} - {zone} - {ship_name} - {booking_url}")

            # 이메일 발송 성공 시 알림 삭제
            cursor.execute("DELETE FROM alarms WHERE id = ? AND user_id = ?", (alarm_id, user_id))
            print(f"✅ 알림 삭제: {alarm_id} - 사용자 ID: {user_id}")
        else:
            print(f"🚫 예약 알림 조건 미충족: {email} - {zone} - {ship_name}")

    conn.commit()
    conn.close()

# 예약 알림 스케줄링 (1시간마다 확인)
def schedule_alerts():
    while True:
        print("🔔 예약 알림 확인 중...")
        check_reservation_alerts()
        time.sleep(3600)  # 1시간마다 확인

# 예약 알림 스케줄링 시작
alert_thread = threading.Thread(target=schedule_alerts)
alert_thread.daemon = True
alert_thread.start()


# Flask 실행
if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5000, debug=True)
