import requests
from bs4 import BeautifulSoup
from crawler.utils import format_date, current_year, current_month
def crawl(site_name, base_url):
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
           
    
    return data