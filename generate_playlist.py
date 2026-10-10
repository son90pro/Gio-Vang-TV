import time
import requests
import re
from datetime import datetime, timezone, timedelta

# Cấu hình múi giờ Việt Nam (UTC+7)
TZ_VN = timezone(timedelta(hours=7))

# Phân loại nhóm môn thể thao
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

def get_active_streams_from_site():
    """
    Quét trực tiếp trang chủ giovang.tax để lấy toàn bộ link m3u8 đang hoạt động thực tế
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://giovang.tax/"
    }
    active_streams = {}
    try:
        res = requests.get("https://giovang.tax/", headers=headers, timeout=10)
        if res.status_code == 200:
            # Tìm tất cả link .m3u8 chứa vcdn.cloud trên trang
            found_urls = re.findall(r'https?://[^\s<>"]+vcdn\.cloud[^\s<>"]+\.m3u8', res.text)
            for u in found_urls:
                # Trích xuất mã số luồng (ví dụ 1791xxxxxx)
                m_id = re.search(r'(1791\d+)', u)
                if m_id:
                    active_streams[m_id.group(1)] = u
    except Exception as e:
        print(f"Lỗi quét trang chủ: {e}")
        
    return active_streams

def fetch_and_generate_m3u():
    timestamp = int(time.time())
    api_url = f"https://live-api.keonhacaitp.one/storage/livestream/live.json?t={timestamp}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://giovang.tax/"
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        data = response.json()
        matches = data.get("response", [])
    except Exception as e:
        print(f"Lỗi truy vấn API: {e}")
        return

    # Lấy danh sách link stream thật đang phát từ web
    active_streams = get_active_streams_from_site()

    # Sắp xếp ưu tiên: Bóng Đá lên đầu tiên, sau đó theo thời gian
    priority_order = ["football", "basketball", "volleyball", "tennis", "bongban", "badminton"]
    
    def get_sort_key(item):
        stype = item.get("type", "")
        time_start = item.get("time_start", 0)
        if stype in priority_order:
            return (priority_order.index(stype), time_start)
        return (99, time_start)

    matches.sort(key=get_sort_key)

    m3u_lines = ["#EXTM3U\n"]
    now_vn = datetime.now(TZ_VN)

    for match in matches:
        sport_type = match.get("type", "")
        sport_info = SPORT_MAP.get(sport_type, {"emoji": "🏆", "group": "Giờ Vàng TV"})
        
        teams = match.get("teams", {})
        home = teams.get("home", {})
        away = teams.get("away", {})
        
        home_name = home.get("name", "")
        away_name = away.get("name", "")
        if not home_name or not away_name:
            continue

        logo = home.get("logo", "") or match.get("league", {}).get("icon", "")

        # Định dạng múi giờ Việt Nam
        t_start = match.get("time_start", 0)
        if t_start:
            match_dt = datetime.fromtimestamp(t_start, tz=timezone.utc).astimezone(TZ_VN)
            time_str = match_dt.strftime("%H:%M %d/%m")
            match_date = match_dt.date()
        else:
            time_str = f"{match.get('time', '')} {match.get('day_month', '')}".strip()
            match_date = now_vn.date()

        is_live = match.get("is_live", False)
        status_code = match.get("status_code", "")
        
        if is_live or status_code == "LIVE":
            status_icon = "🟢 "
        elif match_date > now_vn.date():
            status_icon = "📅 "
        else:
            status_icon = "⏳ "

        blv_str = format_blv(match.get("blv", []))
        display_title = f"{status_icon}{time_str} {sport_info['emoji']} {home_name} vs {away_name}{blv_str} [hls]"

        # Khớp nối link stream chuẩn
        stream_url = ""
        fi = str(match.get("fi", match.get("id", "")))
        
        # Kiểm tra xem mã fi có khớp với stream active nào không
        for sid, u in active_streams.items():
            if sid in fi or fi in sid:
                stream_url = u
                break
        
        # Nếu chưa khớp trực tiếp nhưng trận đang live, lấy luồng active khả dụng
        if not stream_url:
            if active_streams and is_live:
                stream_url = list(active_streams.values())[0]
            else:
                if fi.isdigit() and len(fi) >= 9:
                    stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{fi}_hd/{fi}_hd@720p.m3u8"
                else:
                    stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{t_start}_hd/{t_start}_hd@720p.m3u8"

        group_name = sport_info["group"]

        m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group_name}" , {display_title}')
        m3u_lines.append(f"{stream_url}\n")

    # Lưu tệp playlist.m3u
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

if __name__ == "__main__":
    fetch_and_generate_m3u()
    
