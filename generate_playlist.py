import time
import requests
from datetime import datetime, timezone, timedelta

# Cấu hình múi giờ Việt Nam (UTC+7)
TZ_VN = timezone(timedelta(hours=7))

# Mapping Icon môn thể thao và Tên nhóm
SPORT_MAP = {
    "football": {"emoji": "⚽", "group": "Bóng Đá"},
    "basketball": {"emoji": "🏀", "group": "Bóng Rổ"},
    "volleyball": {"emoji": "🏐", "group": "Bóng Chuyền"},
    "tennis": {"emoji": "🎾", "group": "Quần Vợt"},
    "bongban": {"emoji": "🏓", "group": "Bóng Bàn"},
    "badminton": {"emoji": "🏸", "group": "Cầu Lông"},
}

def format_blv(blv_list):
    if not blv_list:
        return ""
    blv = blv_list[0]
    # Làm sạch tiền tố blv- nếu có
    if blv.startswith("blv-"):
        blv = blv.replace("blv-", "").capitalize()
    return f" ({blv})"

def fetch_and_generate_m3u():
    # Thêm timestamp tránh cache API
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

    # Sắp xếp ưu tiên: Bóng đá đứng đầu, các môn khác nối tiếp
    priority_order = ["football", "basketball", "volleyball", "tennis", "bongban", "badminton"]
    
    def get_sort_key(item):
        stype = item.get("type", "")
        if stype in priority_order:
            return (priority_order.index(stype), item.get("time_start", 0))
        return (99, item.get("time_start", 0))

    matches.sort(key=get_sort_key)

    m3u_lines = ['#EXTM3U x-tvg-url=""']

    # Dòng tiêu đề cập nhật thời gian
    now_vn = datetime.now(TZ_VN)
    updated_str = now_vn.strftime("%d/%m %H:%M")
    m3u_lines.append(f'#EXTINF:-1 group-title="Giờ Vàng TV" tvg-logo="https://giovang.tax/favicon.ico",Updated {updated_str}')
    m3u_lines.append("https://giovang.tax/wp-content/themes/GioVang/assets/tvc/tvc_gem88.mp4")

    for match in matches:
        sport_type = match.get("type", "")
        sport_info = SPORT_MAP.get(sport_type, {"emoji": "🏆", "group": "Thể Thao Khác"})
        
        # Lấy thông tin đội bóng & logo
        teams = match.get("teams", {})
        home = teams.get("home", {})
        away = teams.get("away", {})
        
        home_name = home.get("name", "")
        away_name = away.get("name", "")
        logo = home.get("logo", "") or match.get("league", {}).get("icon", "")

        # Định dạng thời gian theo UTC+7
        time_start = match.get("time_start", 0)
        if time_start:
            match_dt = datetime.fromtimestamp(time_start, tz=timezone.utc).astimezone(TZ_VN)
            time_str = match_dt.strftime("%H:%M %d/%m")
        else:
            time_str = f"{match.get('time', '')} {match.get('day_month', '')}".strip()

        # BLV
        blv_str = format_blv(match.get("blv", []))

        # Trạng thái đang diễn ra (chấm xanh)[span_0](start_span)[span_0](end_span)
        is_live = match.get("is_live", False)
        live_dot = "🟢 " if is_live else ""

        # Tên hiển thị chuẩn định dạng mẫu
        display_title = f"{live_dot}{time_str} {sport_info['emoji']} {home_name} vs {away_name}{blv_str} [hls]"

        # ID luồng / Link phát sóng
        match_id = match.get("id", "")
        
        # Cấu trúc link stream HLS dự phòng theo luồng thực tế của hệ thống
        stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{match_id}_hd/{match_id}_hd@720p.m3u8"

        group_name = sport_info["group"]

        m3u_lines.append(f'#EXTINF:-1 tvg-id="{match_id}" tvg-logo="{logo}" group-title="{group_name}",{display_title}')
        m3u_lines.append(stream_url)

    # Ghi nội dung ra file playlist.m3u
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

if __name__ == "__main__":
    fetch_and_generate_m3u()

