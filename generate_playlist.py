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

def get_real_stream_id(match):
    """
    Hàm lấy ID luồng video thực tế (dạng 1791xxxxxx).
    Nếu API có trả về stream_id hoặc fi dạng số thực thì dùng, 
    ngược lại sẽ gọi API detail của trận để lấy chính xác stream_id.
    """
    match_id = match.get("id", "")
    fi = str(match.get("fi", ""))
    
    # Check nếu fi hoặc id đã là chuỗi số luồng thực (ví dụ bắt đầu bằng 1791...)
    if fi.isdigit() and len(fi) >= 9:
        return fi
    
    # Nếu là mã chuỗi hex, thực hiện request lấy chi tiết phòng stream
    try:
        detail_url = f"https://live-api.keonhacaitp.one/storage/livestream/detail/{match_id}.json"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://giovang.tax/"
        }
        res = requests.get(detail_url, headers=headers, timeout=3)
        if res.status_code == 200:
            d_data = res.json()
            # Tìm ID stream thực tế trong response chi tiết
            stream_id = d_data.get("response", {}).get("stream_id") or d_data.get("response", {}).get("room_id")
            if stream_id:
                return str(stream_id)
    except Exception:
        pass

    # Trường hợp fallback dự phòng
    return fi if fi.isdigit() else str(match.get("time_start", ""))

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

    # Ưu tiên sắp xếp: Bóng đá -> Bóng rổ -> Bóng chuyền -> Quần vợt -> Bóng bàn
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

        # Định dạng thời gian múi giờ Việt Nam (UTC+7)
        t_start = match.get("time_start", 0)
        if t_start:
            match_dt = datetime.fromtimestamp(t_start, tz=timezone.utc).astimezone(TZ_VN)
            time_str = match_dt.strftime("%H:%M %d/%m")
        else:
            time_str = f"{match.get('time', '')} {match.get('day_month', '')}".strip()

        blv_str = format_blv(match.get("blv", []))
        is_live = match.get("is_live", False)
        live_dot = "🟢 " if is_live else ""

        # Tiêu đề hiển thị chuẩn 100% theo mẫu M3U của anh
        display_title = f"{live_dot}{time_str} {sport_info['emoji']} {home_name} vs {away_name}{blv_str} [hls]"

        # Lấy chính xác ID luồng phát
        stream_id = get_real_stream_id(match)
        stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{stream_id}_hd/{stream_id}_hd@720p.m3u8"
        
        # Nhóm danh sách kênh theo yêu cầu của anh (Bóng đá đứng đầu)
        group_name = sport_info["group"]

        m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group_name}" , {display_title}')
        m3u_lines.append(f"{stream_url}\n")

    # Xuất file playlist.m3u
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

if __name__ == "__main__":
    fetch_and_generate_m3u()
    
