import time
import requests
from datetime import datetime, timezone, timedelta

# Múi giờ Việt Nam (UTC+7)
TZ_VN = timezone(timedelta(hours=7))

# Phân loại bộ môn & Icon
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

def get_direct_m3u8(match):
    """
    Hàm lấy chính xác link stream m3u8 thực tế
    """
    match_id = match.get("id", "")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://giovang.tax/"
    }

    # 1. Thử lấy từ API room/detail
    try:
        api_detail = f"https://live-api.keonhacaitp.one/storage/livestream/detail/{match_id}.json"
        res = requests.get(api_detail, headers=headers, timeout=3)
        if res.status_code == 200:
            data = res.json().get("response", {})
            stream_url = data.get("stream_url") or data.get("hls") or data.get("play_url")
            if stream_url and "m3u8" in stream_url:
                return stream_url
            
            # Nếu trả về stream_id dạng 1791xxxxxx
            sid = data.get("stream_id") or data.get("room_id")
            if sid:
                return f"https://ftlh5sc02iliv.vcdn.cloud/{sid}_hd/{sid}_hd@720p.m3u8"
    except Exception:
        pass

    # 2. Nếu fi đã là dạng số stream gốc
    fi = str(match.get("fi", ""))
    if fi.isdigit() and len(fi) >= 9:
        return f"https://ftlh5sc02iliv.vcdn.cloud/{fi}_hd/{fi}_hd@720p.m3u8"

    # Fallback mặc định
    return f"https://ftlh5sc02iliv.vcdn.cloud/{match_id}_hd/{match_id}_hd@720p.m3u8"

def fetch_and_generate_m3u():
    timestamp = int(time.time())
    url = f"https://live-api.keonhacaitp.one/storage/livestream/live.json?t={timestamp}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://giovang.tax/"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        matches = data.get("response", [])
    except Exception as e:
        print(f"Lỗi truy vấn API: {e}")
        return

    # Ưu tiên xếp Bóng Đá lên đầu
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

        # Tiêu đề kênh y hệt file mẫu đang chạy tốt
        display_title = f"{live_dot}{time_str} {sport_info['emoji']} {home_name} vs {away_name}{blv_str} [hls]"

        # Lấy link m3u8 thực tế
        stream_url = get_direct_m3u8(match)
        group_name = sport_info["group"]

        # Cấu trúc dòng EXTFINF y hệt file mẫu
        m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group_name}" , {display_title}')
        m3u_lines.append(f"{stream_url}\n")

    # Lưu kết quả
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

if __name__ == "__main__":
    fetch_and_generate_m3u()
    
