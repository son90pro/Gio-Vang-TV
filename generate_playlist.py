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

def fetch_all_giovang_matches():
    """
    Truy vấn đồng thời tất cả các endpoint API chính thức của hệ thống Giờ Vàng TV 
    để gom trọn vẹn lịch thi đấu hôm nay và ngày mai một cách độc lập.
    """
    timestamp = int(time.time())
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://giovang.tax/"
    }
    
    # Danh sách các luồng API dự phòng của hệ thống để gom đủ lịch
    api_endpoints = [
        f"https://live-api.keonhacaitp.one/storage/livestream/live.json?t={timestamp}",
        f"https://live-api.keonhacaitp.one/storage/livestream/today.json?t={timestamp}",
        f"https://live-api.keonhacaitp.one/storage/livestream/schedule.json?t={timestamp}",
        f"https://live-api.keonhacaitp.one/storage/livestream/list.json?t={timestamp}"
    ]

    all_matches = []
    seen_ids = set()

    for url in api_endpoints:
        try:
            res = requests.get(url, headers=headers, timeout=6)
            if res.status_code == 200:
                data = res.json()
                matches = data.get("response", [])
                if isinstance(matches, list):
                    for m in matches:
                        # Lấy mã định danh duy nhất của trận đấu
                        m_id = m.get("id") or m.get("fi")
                        home_team = m.get("teams", {}).get("home", {}).get("name", "")
                        match_key = f"{m_id}_{home_team}"
                        
                        if match_key not in seen_ids and home_team:
                            seen_ids.add(match_key)
                            all_matches.append(m)
        except Exception:
            continue

    return all_matches

def fetch_and_generate_m3u():
    matches = fetch_all_giovang_matches()
    if not matches:
        print("Không lấy được dữ liệu từ API gốc!")
        return

    # Sắp xếp ưu tiên: Bóng Đá luôn đứng đầu tiên, sau đó sắp xếp theo thời gian
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
            today_date = now_vn.date()
        else:
            time_str = f"{match.get('time', '')} {match.get('day_month', '')}".strip()
            match_date = now_vn.date()
            today_date = now_vn.date()

        # Phân biệt trạng thái icon
        is_live = match.get("is_live", False)
        status_code = match.get("status_code", "")
        
        if is_live or status_code == "LIVE":
            status_icon = "🟢 "  # Đang diễn ra
        elif match_date > today_date:
            status_icon = "📅 "  # Lịch ngày mai
        else:
            status_icon = "⏳ "  # Sắp diễn ra trong ngày

        blv_str = format_blv(match.get("blv", []))
        display_title = f"{status_icon}{time_str} {sport_info['emoji']} {home_name} vs {away_name}{blv_str} [hls]"

        # Trích xuất mã ID luồng phát chuẩn xác từ thông tin trận đấu
        stream_id = match.get("stream_id") or match.get("room_id")
        if not stream_id:
            fi = str(match.get("fi", ""))
            # Nếu fi là số chuẩn luồng vcdn
            if fi.isdigit() and len(fi) >= 9:
                stream_id = fi
            else:
                # Nếu fi là mã hex, ưu tiên dùng time_start hoặc id nếu là số
                t_val = str(match.get("time_start", ""))
                stream_id = t_val if t_val.isdigit() else match.get("id", "")

        stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{stream_id}_hd/{stream_id}_hd@720p.m3u8"
        group_name = sport_info["group"]

        # Xuất dòng cấu trúc M3U
        m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group_name}" , {display_title}')
        m3u_lines.append(f"{stream_url}\n")

    # Lưu kết quả ra file playlist.m3u
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

if __name__ == "__main__":
    fetch_and_generate_m3u()
    
