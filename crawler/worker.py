from crawler import run_crawler
from app import check_reservation_alerts
import time

if __name__ == "__main__":
    print("📦 Render Worker: 크롤링 실행 시작")
    run_crawler()
    print("✅ 크롤링 완료")
    time.sleep(600)
    print("🔔 예약 상태 확인 및 이메일 발송 시작")
    check_reservation_alerts()
    print("✅ 예약 상태 확인 및 이메일 발송 완료")