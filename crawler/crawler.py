import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import re

current_year = datetime.now().year
current_month = datetime.now().month
# ✅ 환경변수 로드 (.env 파일)
load_dotenv()

# ✅ MySQL 연결 설정
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



# ✅ MySQL 테이블 생성
def create_table():
    engine = connect_postgres()
    with engine.connect() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS cruise_schedule (
                id INT AUTO_INCREMENT PRIMARY KEY,
                zone VARCHAR(100) NOT NULL,
                site_name VARCHAR(100) NOT NULL,
                ship_name VARCHAR(100) NOT NULL,
                date DATE NOT NULL,
                wave_power VARCHAR(100),
                fish_name VARCHAR(100),
                reservation VARCHAR(100),
                booking_url TEXT,
                UNIQUE (zone, site_name, ship_name, date)
            )
        '''))
        print("✅ 테이블 생성 완료")
# ✅ 날짜 형식 변환 함수 (YYYY-MM-DD)
def format_date(raw_date, year):
    try:
        # ✅ 정규식으로 날짜 감지 (연도 포함 또는 미포함)
        match = re.search(r'(\d{1,2})월\s*(\d{1,2})일(\(\w\))?', raw_date)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            formatted_date = f"{year}-{month:02d}-{day:02d}"
            return formatted_date
        else:
            print(f"❌ 날짜 형식 인식 실패: {raw_date}")
            return None
    except Exception as e:
        print(f"❌ 날짜 형식 변환 실패: {raw_date} - {e}")
        return None

# ✅ 크롤링할 사이트별 메서드 (루키나호)
def crawl_site_lukina(site_name, base_url):
    data = []
   

    for month in range(current_month, current_month + 12):
        year = current_year if month <= 12 else current_year + 1
        month = month if month <= 12 else month - 12
        url = f"{base_url}/{year}{month:02d}"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        items = soup.select(".shipsinfo_daywarp")
        for item in items:
            raw_date = item.select_one(".date_info").text.strip().replace("\n", "")
            formatted_date = format_date(raw_date, year)  # ✅ 날짜 변환
    
            if not formatted_date:
                continue  # 날짜 변환 실패 시 무시
            
            wave_power = item.select_one(".date_info2").text.strip()
            zone = "인천권"
            ships = item.select(".small_event_wrap")
            for ship in ships:
                ship_name = ship.select_one(".ship_info>.title").text.strip()
                fish_name = ship.select_one(".fishspecies").text.replace("어종 :", "").split("/")[0].strip() if ship.select_one(".fishspecies") else "[]"
                reservation = ship.select_one(".number.blink_me.n_blue.f_20").text.strip() if ship.select_one(".number.blink_me.n_blue.f_20") else "마감"
                booking_url = f"{base_url}/{year}{month:02d}"
                
                data.append([zone, site_name, ship_name, formatted_date, wave_power, fish_name, reservation, booking_url])
    
    return data
def crawl_site_rise(site_name, base_url):
    data = []
   
    # 12개월 동안 크롤링
    for month in range(current_month, current_month + 12):
        year = current_year if month <= 12 else current_year + 1
        month = month if month <= 12 else month - 12
        
        # URL 생성
        url = f"{base_url}/{year}{month:02d}"
        response = requests.get(url)
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select(".shipsinfo_daywarp")
        if not items:
            break
        # 날짜 추출
        for item in items:
            # 선박명
            ship_name = item.select_one(".ship_info>div.title").text.strip()
            zone = "인천권"
            # 날짜 및 조류세기
            
            raw_date = item.select_one(".date_wrap").text.strip().replace("\n", "")
            formatted_date = format_date(raw_date, year)  # ✅ 날짜 변환
            
            if not formatted_date:
                continue  # 날짜 변환 실패 시 무시
            
            wave_power = item.select_one(".date_info2").text.strip()

            # 어종 정보
            fish_name = item.select_one(".fishspecies").text.replace("어종 :", "").split("/")[0].strip()

            # 예약 정보
            reser_img = item.select_one('li.remain').text.strip()
            if "남은자리" in reser_img:
                reservation = item.select_one('li.remain span.number').text.strip()
            else:
                reservation = "마감"
            booking_url = f"{base_url}/{year}{month:02d}"    
            
            # 데이터 리스트에 추가
            data.append([zone,site_name, ship_name, formatted_date, wave_power, fish_name, reservation, booking_url])
           
    df = pd.DataFrame(data, columns=['지역','사이트', '선박명', '날짜', '조류세기', '어종', '예약자리','바로가기'])
    return data

def crawl_site_ottogi(site_name, base_url):

    data = []

    # 12개월 동안 크롤링
    for month in range(current_month, current_month + 12):
        year = current_year if month <= 12 else current_year + 1
        month = month if month <= 12 else month - 12
        
        # URL 생성
        url = f"{base_url}/{year}{month:02d}"
        response = requests.get(url)
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select(".shipsinfo_daywarp")
      
        # 날짜 추출
        for item in items:
        # 날짜 및 조류세기
            
            raw_date = item.select_one(".date_wrap").text.strip().replace("\n", "")
            formatted_date = format_date(raw_date, year)  # ✅ 날짜 변환
            
            if not formatted_date:
                continue  # 날짜 변환 실패 시 무시
            
            
            wave_power = item.select_one(".date_info2").text.strip()
            zone = "인천권"
            
            ships = item.select(".ships_warp>table")
            for ship in ships:
                ship_name = ship.select_one(".ship_info>div.title").text.strip()
                fish_element = ship.select_one("#fish")
                if fish_element is not None:
                    fish_name = fish_element.text.strip().replace('[', '').replace(']', '')
                else:
                    fish_name = '[]'
                reservation = ship.select_one('.remain').text.strip()
                if "남은자리" in reservation:
                    reservation = ship.select_one('.number.blink_me').text.strip()
                else:
                    reservation = "마감"
                booking_url = f"{base_url}/{year}{month:02d}"  
                    
                data.append([zone,site_name, ship_name, formatted_date, wave_power, fish_name, reservation, booking_url])
                
    # DataFrame 생성
    df = pd.DataFrame(data, columns=['지역','사이트', '선박명', '날짜', '조류세기', '어종', '예약자리','바로가기'])
    return data
def crawl_site_supernova(site_name, base_url):
    
    data = []

    # 12개월 동안 크롤링
    for month in range(current_month, current_month + 12):
        year = current_year if month <= 12 else current_year + 1
        month = month if month <= 12 else month - 12
        
        # URL 생성
        url = f"{base_url}/{year}{month:02d}"
        response = requests.get(url)
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select(".shipsinfo_daywarp")
      
        # 날짜 추출
        for item in items:
        # 날짜 및 조류세기
            
            raw_date = item.select_one(".date_wrap").text.strip().replace("\n", "")
            formatted_date = format_date(raw_date, year)  # ✅ 날짜 변환
            
            if not formatted_date:
                continue  # 날짜 변환 실패 시 무시
            
            
            wave_power = item.select_one(".date_info2").text.strip()
            zone = "인천권"
            
            ships = item.select(".ships_warp>table")
            for ship in ships:
                ship_name = ship.select_one(".ship_info>div.title").text.strip()
                fish_element = ship.select_one("#fish")
                if fish_element is not None:
                    fish_name = fish_element.text.strip().replace('[', '').replace(']', '')
                else:
                    fish_name = '[]'
                reservation = ship.select_one('.remain').text.strip()
                if "남은자리" in reservation:
                    reservation = ship.select_one('.number.blink_me').text.strip()
                else:
                    reservation = "마감"
                booking_url = f"{base_url}/{year}{month:02d}"  
                    
                data.append([zone,site_name, ship_name, formatted_date, wave_power, fish_name, reservation, booking_url])
              
    # DataFrame 생성
    df = pd.DataFrame(data, columns=['지역','사이트', '선박명', '날짜', '조류세기', '어종', '예약자리','바로가기'])
    return data
def crawl_site_bigboss(site_name, base_url):
    
    data = []

    # 12개월 동안 크롤링
    for month in range(current_month, current_month + 12):
        year = current_year if month <= 12 else current_year + 1
        month = month if month <= 12 else month - 12
        
        # URL 생성
        url = f"{base_url}/{year}{month:02d}"
        response = requests.get(url)
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select(".shipsinfo_daywarp")
               # 날짜 추출
        for item in items:
        # 날짜 및 조류세기
            
            raw_date = item.select_one(".date_wrap").text.strip().replace("\n", "")
            formatted_date = format_date(raw_date, year)  # ✅ 날짜 변환
            
            if not formatted_date:
                continue  # 날짜 변환 실패 시 무시
            
            
            wave_power = item.select_one(".date_info2").text.strip()
            zone = "충청권"
            
            ships = item.select(".ships_warp>table")
            for ship in ships:
                ship_name = ship.select_one(".ship_info>div.title").text.strip()
                fish_element = ship.select_one("#fish")
                if fish_element is not None:
                    fish_name = fish_element.text.strip().replace('[', '').replace(']', '')
                else:
                    fish_name = '[]'
                reservation = ship.select_one('.remain').text.strip()
                if "남은자리" in reservation:
                    reservation = ship.select_one('.number.blink_me').text.strip()
                else:
                    reservation = "마감"
                booking_url = f"{base_url}/{year}{month:02d}"  
                    
                data.append([zone,site_name, ship_name, formatted_date, wave_power, fish_name, reservation, booking_url])
                
    # DataFrame 생성
    df = pd.DataFrame(data, columns=['지역','사이트', '선박명', '날짜', '조류세기', '어종', '예약자리','바로가기'])
    return data 

# ✅ 크롤링 및 MySQL 저장 함수
# ✅ 크롤링 및 MySQL 저장 함수
def crawl_and_save_to_mysql():
    engine = connect_postgres()
    create_table()  # ✅ 테이블 생성 확인

    # 크롤링할 사이트 목록
    sites = {
        "루키나호": "https://lukina.sunsang24.com/ship/schedule_fleet",
        "영종도라이즈호": "https://risefishing.sunsang24.com/ship/schedule_fleet",
        "영종도오뚜기호": "http://ottogi.sunsang24.com/ship/schedule_fleet",
        "슈퍼노바": "https://supernova.sunsang24.com/ship/schedule_fleet",
        "오천빅보스호": "https://bigboss24.sunsang24.com/ship/schedule_fleet"
    }

    # ✅ 첫 번째 사이트에서만 기존 데이터 전체 삭제
    first_site = True

    for site_name, base_url in sites.items():
        print(f"🔍 {site_name} 크롤링 시작...")

        # ✅ 사이트별 데이터 크롤링
        if site_name == "루키나호":
            site_data = crawl_site_lukina(site_name, base_url)
        elif site_name == "영종도라이즈호":
            site_data = crawl_site_rise(site_name, base_url)
        elif site_name == "영종도오뚜기호":
            site_data = crawl_site_ottogi(site_name, base_url)
        elif site_name == "슈퍼노바":
            site_data = crawl_site_supernova(site_name, base_url)
        elif site_name == "오천빅보스호":
            site_data = crawl_site_bigboss(site_name, base_url)

        with engine.connect() as conn:
            transaction = conn.begin()  # ✅ 트랜잭션 시작
            try:
                # ✅ 첫 번째 사이트일 경우만 전체 데이터 삭제 + ID 초기화
                if first_site:
                    conn.execute(text('TRUNCATE TABLE cruise_schedule'))
                    print("✅ 기존 데이터 전체 삭제 및 ID 초기화")
                    first_site = False  # 이후 사이트에서는 삭제하지 않음

                # ✅ 새 데이터 삽입
                for row in site_data:
                    conn.execute(text('''
                        INSERT INTO cruise_schedule 
                        (zone, site_name, ship_name, date, wave_power, fish_name, reservation, booking_url)
                        VALUES (:zone, :site_name, :ship_name, :date, :wave_power, :fish_name, :reservation, :booking_url)
                    '''), {
                        "zone": row[0],
                        "site_name": row[1],
                        "ship_name": row[2],
                        "date": row[3],
                        "wave_power": row[4],
                        "fish_name": row[5],
                        "reservation": row[6],
                        "booking_url": row[7]
                    })

                transaction.commit()  # ✅ 명시적 커밋
                print(f"✅ {site_name} 데이터 저장 완료")

            except Exception as e:
                transaction.rollback()  # ✅ 오류 발생 시 롤백
                print(f"❌ 저장 오류: {e}")


    # ✅ DB에서 데이터 읽어와 출력
    with engine.connect() as conn:
        df = pd.read_sql('SELECT * FROM cruise_schedule ORDER BY date DESC', conn)
    
    return df

def run_crawler():
    df = crawl_and_save_to_mysql()
    print(df)

