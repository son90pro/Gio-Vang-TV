import time
import requests
import re
from datetime import datetime, timezone, timedelta

# Múi giờ Việt Nam (UTC+7)
TZ_VN = timezone(timedelta(hours=7))

# Mapping Icon môn thể thao và Tên nhóm
SPORT_MAP = {
    "football": {"emoji": "⚽", "group": "Bóng Đá"},
    "basketball": {"emoji": "🏀", "group": "Bóng Rổ"},
    "volleyball": {"emoji": "🏐", "group": "Bóng Chuyền"},
    "tennis": {"emoji": "🥎", "group": "Quần Vợt"},
    "bongban": {"emoji": "🏓", "group": "Bóng Bàn"},
    "badminton": {"emoji": "🏸", "group": "Cầu Lông"},
}

def format_blv(blv_list):
    if not blv_list:
        return ""
    blv = blv_list[0]
    if blv.startswith("blv-"):
        blv = blv.replace("blv-", "").capitalize()
    elif blv.startswith("blv "):
        blv = blv.replace("blv ", "").capitalize()
    return f" ({blv})"

def fetch_m3u_from_source():
    """
    Tải trực tiếp playlist M3U nguồn đang chạy chuẩn từ tinyurl.com/ttthethao6
    để lấy chính xác các link stream 1791xxxxxx đang hoạt động.
    """
    source_url = "https://tinyurl.com/ttthethao6"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    stream_map = {} # Mapping từ tên đội bóng / BLV sang link m3u8 thực tế
    try:
        res = requests.get(source_url, headers=headers, timeout=10)
        if res.status_code == 200:
            lines = res.text.splitlines()
            current_title = ""
            for line in lines:
                line = line.strip()
                if line.startswith("#EXTINF"):
                    current_title = line
                elif line.startswith("http") and "vcdn.cloud" in line:
                    if current_title:
                        stream_map[current_title] = line
                        current_title = ""
    except Exception as e:
        print(f"Lỗi đọc nguồn ttthethao6: {e}")
        
    return stream_map

def fetch_and_generate_m3u():
    timestamp = int(time.time())
    url = f"https://live-api.keonhacaitp.one/storage/livestream/live.json?t={timestamp}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://giovang.tax/"
    }

    # 1. Lấy dữ liệu API trận đấu
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        matches = data.get("response", [])
    except Exception as e:
        print(f"Lỗi truy vấn API: {e}")
        return

    # 2. Lấy dữ liệu stream thực tế từ ttthethao6
    source_streams = fetch_m3u_from_source()

    # 3. Sắp xếp ưu tiên: Bóng Đá -> Bóng Rổ -> Bóng Chuyền -> Quần Vợt -> Bóng Bàn
    priority_order = ["football", "basketball", "volleyball", "tennis", "bongban", "badminton"]
    
    def get_sort_key(item):
        stype = item.get("type", "")
        if stype in priority_order:
            return (priority_order.index(stype), item.get("time_start", 0))
        return (99, item.get("time_start", 0))

    matches.sort(key=get_sort_key)

    m3u_lines = ["#EXTM3U\n"]

    for match in matches:
        sport_type = match.get("type", "")
        sport_info = SPORT_MAP.get(sport_type, {"emoji": "🏆", "group": "Giờ Vàng TV"})
        
        teams = match.get("teams", {})
        home = teams.get("home", {})
        away = teams.get("away", {})
        
        home_name = home.get("name", "")
        away_name = away.get("name", "")
        logo = home.get("logo", "") or match.get("league", {}).get("icon", "")

        # Múi giờ Việt Nam
        t_start = match.get("time_start", 0)
        if t_start:
            match_dt = datetime.fromtimestamp(t_start, tz=timezone.utc).astimezone(TZ_VN)
            time_str = match_dt.strftime("%H:%M %d/%m")
        else:
            time_str = f"{match.get('time', '')} {match.get('day_month', '')}".strip()

        blv_str = format_blv(match.get("blv", []))
        is_live = match.get("is_live", False)
        live_dot = "🟢 " if is_live else ""

        display_title = f"{live_dot}{time_str} {sport_info['emoji']} {home_name} vs {away_name}{blv_str} [hls]"

        # Tìm link m3u8 khớp chính xác từ nguồn ttthethao6
        stream_url = ""
        for title_key, url_val in source_streams.items():
            if home_name in title_key or away_name in title_key:
                stream_url = url_val
                break
        
        # Nếu chưa tìm thấy, dựng link mặc định
        if not stream_url:
            fi = str(match.get("fi", match.get("id", "")))
            stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{fi}_hd/{fi}_hd@720p.m3u8"

        group_name = sport_info["group"]

        # Xuất dòng chuẩn
        m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group_name}" , {display_title}')
        m3u_lines.append(f"{stream_url}\n")

    # Ghi tệp
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

if __name__ == "__main__":
    fetch_and_generate_m3u()
    
