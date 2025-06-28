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
    #df = pd.DataFrame(data, columns=['지역','사이트', '선박명', '날짜', '조류세기', '어종', '예약자리','바로가기'])
    return data