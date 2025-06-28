from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import pandas as pd
import sys
from crawler.sites import lukina, rise, ottogi, supernova, bigboss
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

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

def run_crawler():
    engine = connect_postgres()
    first_site = True

    sites = {
        "루키나호": ("https://lukina.sunsang24.com/ship/schedule_fleet", lukina),
        "영종도라이즈호": ("https://risefishing.sunsang24.com/ship/schedule_fleet", rise),
        "영종도오뚜기호": ("http://ottogi.sunsang24.com/ship/schedule_fleet", ottogi),
        "슈퍼노바": ("https://supernova.sunsang24.com/ship/schedule_fleet", supernova),
        "오천빅보스호": ("https://bigboss24.sunsang24.com/ship/schedule_fleet", bigboss)
    }

    for site_name, (base_url, module) in sites.items():
        print(f"🔍 {site_name} 크롤링 시작...")
        site_data = module.crawl(site_name, base_url)

        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                if first_site:
                    conn.execute(text('TRUNCATE TABLE cruise_schedule RESTART IDENTITY'))
                    print("✅ 기존 데이터 전체 삭제 및 ID 초기화")
                    first_site = False

                insert_data = [
                    {
                        "zone": row[0],
                        "site_name": row[1],
                        "ship_name": row[2],
                        "date": row[3],
                        "wave_power": row[4],
                        "fish_name": row[5],
                        "reservation": row[6],
                        "booking_url": row[7]
                    }
                    for row in site_data
                ]

                conn.execute(text('''
                    INSERT INTO cruise_schedule 
                    (zone, site_name, ship_name, date, wave_power, fish_name, reservation, booking_url)
                    VALUES (:zone, :site_name, :ship_name, :date, :wave_power, :fish_name, :reservation, :booking_url)
                '''), insert_data)

                transaction.commit()
                print(f"✅ {site_name} 데이터 저장 완료")
            except Exception as e:
                transaction.rollback()
                print(f"❌ 저장 오류: {e}")

    with engine.connect() as conn:
        df = pd.read_sql('SELECT * FROM cruise_schedule ORDER BY date DESC', conn)
    print(df)
