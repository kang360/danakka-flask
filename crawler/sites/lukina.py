import requests
from bs4 import BeautifulSoup
from crawler.utils import format_date, current_year, current_month

def crawl(site_name, base_url):
    data = []
    for month in range(current_month, current_month + 12):
        year = current_year if month <= 12 else current_year + 1
        m = month if month <= 12 else month - 12
        url = f"{base_url}/{year}{m:02d}"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        items = soup.select(".shipsinfo_daywarp")
        for item in items:
            raw_date = item.select_one(".date_info").text.strip().replace("\n", "")
            formatted_date = format_date(raw_date, year)
            if not formatted_date:
                continue

            wave_power = item.select_one(".date_info2").text.strip()
            zone = "인천권"

            ships = item.select(".small_event_wrap")
            for ship in ships:
                ship_name = ship.select_one(".ship_info>.title").text.strip()
                fish_name = ship.select_one(".fishspecies").text.replace("어종 :", "").split("/")[0].strip() if ship.select_one(".fishspecies") else "[]"
                reservation = ship.select_one(".number.blink_me.n_blue.f_20").text.strip() if ship.select_one(".number.blink_me.n_blue.f_20") else "마감"
                booking_url = f"{base_url}/{year}{m:02d}"

                data.append([zone, site_name, ship_name, formatted_date, wave_power, fish_name, reservation, booking_url])
    return data