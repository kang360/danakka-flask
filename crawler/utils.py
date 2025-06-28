import re
from datetime import datetime

current_year = datetime.now().year
current_month = datetime.now().month

def format_date(raw_date, year):
    try:
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
        print(f"❌ 날짜 변환 실패: {raw_date} - {e}")
        return None