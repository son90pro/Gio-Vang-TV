import time
import requests

# URL API của Giờ Vàng TV
LIVE_API_URL = "https://live-api.keonhacaitp.one/storage/livestream/live.json"
DETAIL_API_URL = "https://live-api.keonhacaitp.one/api/fixture-detail/"
DEFAULT_OFFLINE_STREAM = "https://freem3u.xyz/static/no-signal/low.m3u8"

# Bảng ánh xạ icon môn thể thao
SPORT_ICONS = {
    "football": "⚽",
    "bongda": "⚽",
    "basketball": "🏀",
    "bongro": "🏀",
    "bongchuyen": "🏐",
    "tennis": "🥎",
    "vothuat": "🥊🥋",
    "formula1": "[formula1]",
    "esports": "🎮",
    "game": "🎮",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}


def format_blv_name(blv_list):
    """Xử lý định dạng tên BLV"""
    if not blv_list:
        return "BLV"
    blv = blv_list[0] if isinstance(blv_list, list) else str(blv_list)
    blv = blv.replace("blv-", "").replace("blv", "").strip()
    return blv.capitalize() if blv else "BLV"


def get_stream_urls(match_id):
    """Lấy hoặc tạo danh sách luồng phát (FHD, HD, SD)"""
    try:
        # Gọi API chi tiết trận đấu
        res = requests.get(f"{DETAIL_API_URL}{match_id}", headers=HEADERS, timeout=5)
        if res.status_code == 200:
            data = res.json().get("response", {}).get("detail", {})
            # Tìm link CDN từ response API (nếu API có trả về key stream/cdn)
            stream_url = data.get("cdn") or data.get("stream_url") or data.get("hls")
            if stream_url:
                return {"HD": stream_url}
    except Exception:
        pass

    return {"HD": DEFAULT_OFFLINE_STREAM}


def fetch_matches():
    """Lấy danh sách tất cả các trận đấu từ API chính"""
    timestamp = int(time.time())
    url = f"{LIVE_API_URL}?t={timestamp}"

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return response.json().get("response", [])
    except Exception as e:
        print(f"Lỗi khi lấy dữ liệu API: {e}")
    return []


def generate_m3u():
    matches = fetch_matches()

    m3u_lines = ["#EXTM3U\n"]

    for match in matches:
        # 1. Trích xuất thông tin trận đấu
        match_id = match.get("id", "")
        sport_type = match.get("type", "football").lower()
        icon = SPORT_ICONS.get(sport_type, "⚽")

        time_str = match.get("time", "00:00:00")[:5]  # Lấy HH:MM
        day_month = match.get("day_month", "")

        teams = match.get("teams", {})
        home_team = teams.get("home", {})
        away_team = teams.get("away", {})

        home_name = home_team.get("name", "").strip()
        away_name = away_team.get("name", "").strip()

        # Ưu tiên lấy logo đội nhà -> đội khách -> logo giải
        logo = (
            home_team.get("logo")
            or away_team.get("logo")
            or match.get("league", {}).get("icon")
            or ""
        )

        blv_raw = match.get("blv", [])
        blv_name = format_blv_name(blv_raw)

        # Trạng thái trận đấu: 🟢 Đang diễn ra, 🟡 Sắp diễn ra
        is_live = match.get("is_live", False)
        status_code = match.get("status_code", "")
        if is_live or status_code == "LIVE":
            status_symbol = "🟢 "
        else:
            status_symbol = "🟡 " if day_month else ""

        # 2. Lấy link luồng phát
        streams = get_stream_urls(match_id)

        # 3. Tạo entry M3U cho từng luồng (FHD / HD / SD)
        for quality, stream_url in streams.items():
            # Tên hiển thị chuẩn mẫu
            title = f"{status_symbol}{time_str} {day_month} {icon} {home_name} vs {away_name} ({blv_name}) [hls]"

            # Thêm thông tin độ phân giải nếu có nhiều chất lượng
            if len(streams) > 1:
                title += f" [{quality}]"

            extinf = f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV" , {title}'

            m3u_lines.append(extinf)
            m3u_lines.append(stream_url)
            m3u_lines.append("")

    # Ghi ra file giovang.m3u
    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"Đã cập nhật thành công {len(matches)} trận đấu vào giovang.m3u")


if __name__ == "__main__":
    generate_m3u()
    
