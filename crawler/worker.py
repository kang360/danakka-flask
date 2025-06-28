import sys
import os

# 상위 폴더 경로를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from app import check_reservation_alerts
from crawler import run_crawler
import time
if __name__ == "__main__":
    print("📦 Render Worker: 크롤링 실행 시작")
    run_crawler()
    print("✅ 크롤링 완료")
    time.sleep(600)
    print("🔔 예약 상태 확인 및 이메일 발송 시작")
    check_reservation_alerts()
    print("✅ 예약 상태 확인 및 이메일 발송 완료")