import time
import requests
from datetime import datetime, timezone, timedelta

# Cấu hình múi giờ Việt Nam (UTC+7)
TZ_VN = timezone(timedelta(hours=7))

# Phân loại bộ môn & Icon nhóm
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

def fetch_active_streams():
    """Lấy các link stream đang hoạt động thực tế để map vào trận đang đá"""
    source_url = "https://tinyurl.com/ttthethao6"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    stream_map = {}
    try:
        res = requests.get(source_url, headers=headers, timeout=8)
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
    except Exception:
        pass
    return stream_map

def fetch_all_giovang_schedule():
    """Gom toàn bộ lịch thi đấu từ nhiều endpoint API gốc của Giờ Vàng TV"""
    timestamp = int(time.time())
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://giovang.tax/"
    }
    api_endpoints = [
        f"https://live-api.keonhacaitp.one/storage/livestream/live.json?t={timestamp}",
        f"https://live-api.keonhacaitp.one/storage/livestream/today.json?t={timestamp}",
        f"https://live-api.keonhacaitp.one/storage/livestream/schedule.json?t={timestamp}",
        f"https://live-api.keonhacaitp.one/storage/livestream/next.json?t={timestamp}"
    ]

    all_matches = []
    seen = set()
    for url in api_endpoints:
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                matches = data.get("response", [])
                if isinstance(matches, list):
                    for m in matches:
                        m_id = m.get("id") or m.get("fi")
                        home = m.get("teams", {}).get("home", {}).get("name", "")
                        away = m.get("teams", {}).get("away", {}).get("name", "")
                        key = f"{home}_{away}_{m.get('time_start')}"
                        if key not in seen and home and away:
                            seen.add(key)
                            all_matches.append(m)
        except Exception:
            continue
    return all_matches

def fetch_and_generate_m3u():
    # 1. Lấy toàn bộ lịch thi đấu đầy đủ trong ngày và ngày mai
    matches = fetch_all_giovang_schedule()
    
    # 2. Lấy kho link stream đang chạy thực tế
    active_streams = fetch_active_streams()

    # Nếu API lịch trống, fallback lấy trực tiếp từ nguồn ttthethao6 để playlist không bị rỗng
    if not matches and active_streams:
        m3u_lines = ["#EXTM3U\n"]
        for title, url in active_streams.items():
            m3u_lines.append(f"{title}\n{url}\n")
        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_lines))
        return

    # Sắp xếp ưu tiên: Bóng Đá luôn lên đầu tiên, sau đó theo thời gian
    priority_order = ["football", "basketball", "volleyball", "tennis", "bongban", "badminton"]
    
    def get_sort_key(item):
        stype = item.get("type", "")
        t_start = item.get("time_start", 0)
        if stype in priority_order:
            return (priority_order.index(stype), t_start)
        return (99, t_start)

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

        # Tìm link stream thực tế từ active_streams (dựa vào tên đội bóng)
        stream_url = ""
        for title_key, url_val in active_streams.items():
            if home_name in title_key or away_name in title_key:
                stream_url = url_val
                break

        # Nếu chưa có trong active_streams, dựng link dự phòng chuẩn theo fi/id
        if not stream_url:
            fi = str(match.get("fi", match.get("id", "")))
            if fi.isdigit() and len(fi) >= 9:
                stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{fi}_hd/{fi}_hd@720p.m3u8"
            else:
                stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{t_start}_hd/{t_start}_hd@720p.m3u8"

        group_name = sport_info["group"]

        m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group_name}" , {display_title}')
        m3u_lines.append(f"{stream_url}\n")

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

if __name__ == "__main__":
    fetch_and_generate_m3u()
    
