from flask import Flask, render_template, jsonify, request, redirect, session, flash
import datetime
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
from flask_mail import Mail, Message
import threading
import time
from dotenv import load_dotenv
from flask import Flask, send_from_directory, render_template
from crawler import run_crawler
from sqlalchemy import create_engine
import os
import psycopg2.extras

app = Flask(__name__)
CORS(app)
# ✅ 인증 파일 경로 생성 (.well-known/acme-challenge)
ACME_CHALLENGE_PATH = os.path.join(app.root_path, '.well-known/acme-challenge')
os.makedirs(ACME_CHALLENGE_PATH, exist_ok=True)

# ✅ 인증 파일 경로 라우팅 (Let's Encrypt HTTP-01 인증용)
@app.route('/.well-known/acme-challenge/<path:filename>')
def letsencrypt_challenge(filename):
    return send_from_directory(ACME_CHALLENGE_PATH, filename)

# ✅ 강제적으로 .env 파일 로드
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path, override=True)  # .env 파일 강제 로드

app.secret_key = os.getenv('SECRET_KEY')
app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Flask-Mail 설정 (네이버 SMTP)
app.config['MAIL_SERVER'] = 'smtp.naver.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'danakkafishing@naver.com'
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = 'danakkafishing@naver.com'

mail = Mail(app)

#engine = create_engine(f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}@{os.getenv('MYSQL_HOST')}/{os.getenv('MYSQL_DATABASE')}")

@app.route("/crawl")
def trigger():
    token = request.args.get("token")
    if token != os.getenv("CRAWL_SECRET_TOKEN"):
        return "❌ Unauthorized", 403
    run_crawler()
    return "✅ 크롤링 완료!"
# 루트 경로: 홈페이지
@app.route('/')
def home():
    return render_template('boot.html')

def connect_postgres():
    user = os.getenv("PG_USER")
    password = os.getenv("PG_PASSWORD")
    host = os.getenv("PG_HOST")
    port = os.getenv("PG_PORT", 5432)
    database = os.getenv("PG_DATABASE")
    sslmode = os.getenv("PG_SSL", "require")

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}?sslmode={sslmode}"
    engine = create_engine(url, echo=False)
    return engine
 
# ✅ 로그인
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST': 
        email = request.form['email']
        password = request.form['password']

        engine = connect_postgres()
        conn = engine.raw_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT id, nickname, email, password_hash FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password_hash'], password):
            session['user'] = {'id': user['id'], 'email': user['email'], 'nickname': user['nickname']}
            flash("로그인 성공!", "success")
            conn.close()
            return redirect('/mypage')
        else:
            flash("이메일 또는 비밀번호가 일치하지 않습니다.", "danger")
            conn.close()

    return render_template('login.html')

@app.route('/mypage', methods=['GET', 'POST'])
def mypage():
    if 'user' not in session:
        flash("로그인이 필요합니다.", "warning")
        return redirect('/login')

    user_id = session['user']['id']

    engine = connect_postgres()
    conn = engine.raw_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # ✅ 회원 정보 수정 처리
    if request.method == 'POST':
        nickname = request.form.get('nickname')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')

        # ✅ 현재 비밀번호 확인
        cursor.execute("SELECT password_hash FROM users WHERE id=%s", (user_id,))
        user = cursor.fetchone()

        if not user:
            flash("사용자 정보를 찾을 수 없습니다.", "danger")
            conn.close()
            return redirect('/mypage')

        if not check_password_hash(user['password_hash'], current_password):
            flash("현재 비밀번호가 일치하지 않습니다.", "danger")
            conn.close()
            return redirect('/mypage')

        # ✅ 닉네임 및 비밀번호 변경
        if new_password:
            hashed_password = generate_password_hash(new_password)
            cursor.execute(
                "UPDATE users SET nickname=%s, password_hash=%s WHERE id=%s",
                (nickname, hashed_password, user_id)
            )
        else:
            cursor.execute(
                "UPDATE users SET nickname=%s WHERE id=%s",
                (nickname, user_id)
            )

        conn.commit()
        session['user']['nickname'] = nickname
        flash("회원 정보가 수정되었습니다.", "success")

    # ✅ 예약 알림 조회
    cursor.execute("SELECT id, user_id, TO_CHAR(date, 'YYYY-MM-DD') AS date, zone, ship_name FROM alarms WHERE user_id = %s ORDER BY date ASC", (user_id,))
    alarms = cursor.fetchall()
    conn.close()

    return render_template('mypage.html', user=session['user'], alarms=alarms)


# ✅ 예약 정보 API
@app.route('/api/reservations', methods=['GET'])
def get_reservations():
    date_param = request.args.get('date')
    print(f"📅 요청 날짜: {date_param} ({type(date_param)})")

    engine = connect_postgres()
    conn = engine.raw_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        # 날짜가 전달된 경우 필터링
        if date_param:
            try:
                # ✅ 다양한 날짜 형식 처리
                formatted_date = parse_date(date_param)
                cursor.execute("SELECT * FROM cruise_schedule WHERE date = %s", (formatted_date,))
                print(f"✅ 날짜 필터링: {formatted_date}")
            except ValueError:
                print(f"❌ 날짜 파싱 오류: {date_param} - 지원되지 않는 날짜 형식")
                return jsonify({"error": "날짜 형식이 잘못되었습니다. (예: YYYY-MM-DD)"}), 400
        else:
            cursor.execute("SELECT * FROM cruise_schedule")
            print("✅ 전체 예약 조회")

        rows = cursor.fetchall()
        if not rows:
            print("❌ 예약 정보가 없습니다.")
            return jsonify({"message": "예약 정보가 없습니다."}), 404
        
        columns = ['id','zone', 'site_name', 'ship_name', 'date', 'wave_power', 'fish_name', 'reservation', 'booking_url']
        results = [dict(zip(columns, row.values())) for row in rows]
    
    except Exception as db_err:
        print(f"❌ DB 오류: {db_err}")
        return jsonify({"error": "DB 오류가 발생했습니다."}), 500
    finally:
        conn.close()

    return jsonify(results)


# ✅ 날짜 파싱 함수
def parse_date(date_str):
    """
    다양한 날짜 형식을 지원하는 함수
    """
    try:
        # ✅ 기본 형식 (YYYY-MM-DD)
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        pass

    try:
        # ✅ GMT 형식 (Sat, 31 May 2025 00:00:00 GMT)
        parsed_date = datetime.datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S GMT")
        return parsed_date.strftime("%Y-%m-%d")
    except ValueError:
        pass

    try:
        # ✅ 추가 형식 (예: 31 May 2025)
        parsed_date = datetime.datetime.strptime(date_str, "%d %b %Y")
        return parsed_date.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # ❌ 모든 형식 실패
    raise ValueError("지원되지 않는 날짜 형식")
# ✅ 회원가입
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        nickname = request.form['nickname']
        password = request.form['password']

        hashed_password = generate_password_hash(password)

        engine = connect_postgres()
        conn = engine.raw_connection()
        cursor = conn.cursor()

        # 이메일과 닉네임 중복 체크
        cursor.execute("SELECT id FROM users WHERE email=%s OR nickname=%s", (email, nickname))
        existing_user = cursor.fetchone()
        if existing_user:
            flash("이미 등록된 이메일 또는 닉네임입니다.", "danger")
            conn.close()
            return redirect('/register')

        # 중복이 없을 경우 저장
        cursor.execute("INSERT INTO users (email, nickname, password_hash) VALUES (%s, %s, %s)",
                       (email, nickname, hashed_password))
        conn.commit()
        conn.close()

        flash("가입이 완료되었습니다. 로그인해주세요.", "success")
        return redirect('/login')

    return render_template('register.html')

# ✅ 회원 탈퇴
@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user' not in session:
        flash("로그인이 필요합니다.", "warning")
        return redirect('/login')

    user_id = session['user']['id']

    engine = connect_postgres()
    conn = engine.raw_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
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

#✅  이용후기 페이지
@app.route('/review', methods=['GET', 'POST'])
def reviews():
    if request.method == 'POST':
        if 'user' not in session:
            flash("로그인이 필요합니다.", "warning")
            return redirect('/login')

        review_text = request.form['review']
        user_id = session['user']['id']
        nickname = session['user']['nickname']

        engine = connect_postgres()
        conn = engine.raw_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO reviews (user_id, nickname, review, created_at) VALUES (%s, %s, %s, NOW())",
            (user_id, nickname, review_text)
        )
        conn.commit()
        conn.close()

        flash("후기가 등록되었습니다.", "success")
        return redirect('/review')

    # 후기 조회 (정렬 기준 적용)
    sort = request.args.get('sort', 'latest')
    engine = connect_postgres()
    conn = engine.raw_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if sort == 'popular':
        cursor.execute("SELECT id, user_id, nickname, review, created_at, likes FROM reviews ORDER BY likes DESC, created_at DESC")
    else:
        cursor.execute("SELECT id, user_id, nickname, review, created_at, likes FROM reviews ORDER BY created_at DESC")

    reviews = cursor.fetchall()
    conn.close()

    return render_template('review.html', reviews=reviews, user=session.get('user'), sort=sort)




# ✅ 후기 좋아요
@app.route('/like_review/<int:review_id>', methods=['POST'])
def like_review(review_id):
    if 'user' not in session:
        flash("로그인이 필요합니다.", "warning")
        return redirect('/login')

    user_id = session['user']['id']

    engine = connect_postgres()
    conn = engine.raw_connection()
    cursor = conn.cursor()

    # 사용자가 이미 좋아요를 눌렀는지 확인
    cursor.execute("SELECT 1 FROM review_likes WHERE user_id = %s AND review_id = %s", (user_id, review_id))
    if cursor.fetchone():
        flash("이미 좋아요를 누르셨습니다.", "warning")
        conn.close()
        return redirect('/review')

    # 좋아요 기록 저장
    cursor.execute("INSERT INTO review_likes (user_id, review_id) VALUES (%s, %s)", (user_id, review_id))

    # 좋아요 수 증가
    cursor.execute("UPDATE reviews SET likes = likes + 1 WHERE id = %s", (review_id,))
    conn.commit()
    conn.close()

    flash("후기에 좋아요를 추가했습니다.", "success")
    return redirect('/review')


# ✅후기 수정 (AJAX 사용)
@app.route('/edit_review/<int:review_id>', methods=['POST'])
def edit_review(review_id):
    if 'user' not in session:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    try:
        data = request.get_json()  # ✅ JSON 형식으로 데이터 수신
        new_review = data.get('review', '').strip()

        if not new_review:
            return jsonify({"success": False, "message": "후기 내용이 비어있습니다."}), 400

        conn = connect_postgres()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE reviews SET review = %s WHERE id = %s AND user_id = %s",
            (new_review, review_id, session['user']['id'])
        )
        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": "후기가 수정되었습니다."})

    except Exception as e:
        print(f"❌ 서버 오류: {e}")
        return jsonify({"success": False, "message": "서버 오류가 발생했습니다."}), 500

# ✅후기 삭제
@app.route('/delete_review/<int:review_id>', methods=['POST'])
def delete_review(review_id):
    if 'user' not in session:
        flash("로그인이 필요합니다.", "warning")
        return redirect('/login')

    engine = connect_postgres()
    conn = engine.raw_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reviews WHERE id = %s AND user_id = %s", (review_id, session['user']['id']))
    conn.commit()
    conn.close()

    flash("후기가 삭제되었습니다.", "success")
    return redirect('/review')

# 이용후기 페이지 (추가 경로)
@app.route('/review', methods=['GET', 'POST'])
def review_redirect():
    return redirect('/review')

# ✅예약 알림 신청 (최대 3회 제한)
@app.route('/alarm_request', methods=['POST'])
def alarm_request():
    if 'user' not in session:
        return jsonify({"message": "로그인이 필요합니다."}), 401

    try:
        data = request.get_json()  # JSON 형식으로 데이터 수신
        date = data.get('date')
        zone = data.get('zone')
        ship_name = data.get('ship_name')
        user_id = session['user']['id']
        email = session['user']['email']

        if not date or not zone or not ship_name:
            return jsonify({"message": "필수 데이터가 누락되었습니다."}), 400

        engine = connect_postgres()
        conn = engine.raw_connection()
        cursor = conn.cursor()

        # ✅ 사용자 알림 최대 3개 제한 확인
        cursor.execute("SELECT COUNT(*) FROM alarms WHERE user_id = %s", (user_id,))
        alarm_count = cursor.fetchone()[0]

        if alarm_count >= 3:
            return jsonify({"message": "예약 알림은 최대 3개까지 등록할 수 있습니다."}), 400

        # ✅ 동일한 알림 중복 등록 방지
        cursor.execute("""
            SELECT COUNT(*) 
            FROM alarms 
            WHERE user_id = %s AND date = %s AND zone = %s AND ship_name = %s
        """, (user_id, date, zone, ship_name))
        duplicate_count = cursor.fetchone()[0]

        if duplicate_count > 0:
            return jsonify({"message": "이미 동일한 예약 알림이 등록되어 있습니다."}), 400

        # ✅ 알림 등록
        cursor.execute("INSERT INTO alarms (user_id, email, date, zone, ship_name) VALUES (%s, %s, %s, %s, %s)",
                       (user_id, email, date, zone, ship_name))
        conn.commit()
        conn.close()
        
        
        return jsonify({"success": True, "message": "예약 알림이 등록되었습니다."})

    except Exception as e:
        print(f"❌ 서버 오류: {e}")
        return jsonify({"message": "서버 내부 오류가 발생했습니다."}), 500
    



# ✅ 예약 알림 삭제 (AJAX 대응)
@app.route('/delete_alarm/<int:alarm_id>', methods=['POST'])
def delete_alarm(alarm_id):
    if 'user' not in session:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    user_id = session['user']['id']

    try:
        engine = connect_postgres()
        conn = engine.raw_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM alarms WHERE id = %s AND user_id = %s", (alarm_id, user_id))
        if cursor.rowcount == 0:
            return jsonify({"success": False, "message": "삭제할 알림을 찾을 수 없습니다."}), 404

        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": "예약 알림이 삭제되었습니다."})
    except Exception as e:
        print(f"❌ 서버 오류: {e}")
        return jsonify({"success": False, "message": f"서버 오류가 발생했습니다. {str(e)}"}), 500
    




# ✅ 예약 상태 확인 함수
def check_reservation_status(date, zone, ship_name):
    engine = connect_postgres()
    conn = engine.raw_connection()
    cursor = conn.cursor()

    # 예약 상태와 URL 확인 (DB에서 확인)
    cursor.execute("SELECT reservation, booking_url FROM cruise_schedule WHERE date = %s AND zone = %s AND ship_name = %s",
                   (date, zone, ship_name))
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
    engine = connect_postgres()
    conn = engine.raw_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, date, zone, ship_name, email, user_id FROM alarms")
    alarms = cursor.fetchall()

    for alarm in alarms:
        alarm_id = alarm['id']
        date = alarm['date']
        zone = alarm['zone']
        ship_name = alarm['ship_name']
        email = alarm['email']
        user_id = alarm['user_id']

        # ✅ 예약 상태 확인
        reservation_status, booking_url = check_reservation_status(date, zone, ship_name)
        print(f"✅ 예약 상태 확인: {reservation_status}, URL: {booking_url}")

        # 예약 상태가 "마감"이 아니고 URL이 있을 경우
        if reservation_status not in ["마감", "예약 마감"] and booking_url:
            try:
                send_alert_email(email, date, zone, ship_name, booking_url)
                print(f"✅ 이메일 전송: {email} - {zone} - {ship_name} - {booking_url}")

                # ✅ 이메일 발송 성공 시 알림 삭제
                cursor.execute("DELETE FROM alarms WHERE id = %s AND user_id = %s", (alarm_id, user_id))
                print(f"✅ 알림 삭제: {alarm_id} - 사용자 ID: {user_id}")

            except Exception as e:
                print(f"❌ 이메일 발송 오류: {e}")
        else:
            print(f"🚫 예약 알림 조건 미충족: {email} - {zone} - {ship_name}")

    conn.commit()
    conn.close()


# Flask 실행
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80, debug=True)
