import time
import requests

# Bảng ánh xạ icon môn thể thao theo type từ API
SPORT_ICONS = {
    "football": "⚽",
    "bongda": "⚽",
    "tennis": "🥎",
    "esport": "🎮",
    "bongchuyen": "🏐",
    "volleyball": "🏐",
    "billiards": "🎱",
    "bida": "🎱",
    "basketball": "🏀",
    "bongro": "🏀",
    "f1": "[formula1]",
    "formula1": "[formula1]",
    "mma": "🥊🥋",
    "boxing": "🥊🥋",
}


def clean_blv_name(blv_list):
    """Xử lý hiển thị tên BLV đúng định dạng mẫu"""
    if not blv_list:
        return ""

    blv_str = blv_list[0] if isinstance(blv_list, list) else str(blv_list)
    blv_str = blv_str.strip()

    if blv_str.lower().startswith("blv-"):
        name = blv_str[4:]
    elif blv_str.lower().startswith("blv "):
        name = blv_str[4:]
    else:
        name = blv_str

    return f"({name})"


def fetch_and_generate():
    timestamp = int(time.time())
    api_url = f"https://live-api.keonhacaitp.one/storage/livestream/live.json?t={timestamp}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://giovang.rent/",
    }

    try:
        res = requests.get(api_url, headers=headers, timeout=15)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print(f"Lỗi khi lấy dữ liệu API: {e}")
        return

    matches = data.get("response", [])
    m3u_lines = ["#EXTM3U\n"]

    for match in matches:
        # Check trạng thái live
        is_live = (
            match.get("is_live") is True
            or match.get("status_code") == "LIVE"
            or match.get("status") == "Đang diễn ra"
        )
        live_dot = "🟢 " if is_live else ""

        # Thời gian & Ngày
        time_str = match.get("time", "")[:5]  # HH:MM
        day_month = match.get("day_month", "")

        # Icon thể thao
        sport_type = match.get("type", "football")
        sport_icon = SPORT_ICONS.get(str(sport_type).lower(), "⚽")

        # Đội bóng
        teams = match.get("teams", {})
        home_name = teams.get("home", {}).get("name", "").strip()
        away_name = teams.get("away", {}).get("name", "").strip()

        # Logo đội bóng (ưu tiên logo đội nhà, fallback sang logo giải đấu)
        logo = (
            teams.get("home", {}).get("logo")
            or match.get("league", {}).get("icon")
            or ""
        )

        # Tên BLV
        blv_name = clean_blv_name(match.get("blv", []))
        blv_part = f" {blv_name}" if blv_name else ""

        # Xử lý Luồng phát HLS (.m3u8)
        stream_url = match.get("stream_url") or match.get("hls") or match.get("link")

        if not stream_url:
            time_start = match.get("time_start")
            # Tự động dựng luồng vcdn nếu trận đang diễn ra
            if is_live and time_start:
                stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{time_start}_hd/{time_start}_hd@720p.m3u8"
            else:
                stream_url = "https://freem3u.xyz/static/no-signal/low.m3u8"

        # Đóng gói tiêu đề kênh chuẩn TiviMate
        title = f"{live_dot}{time_str} {day_month} {sport_icon} {home_name} vs {away_name}{blv_part} [hls]"

        extinf = (
            f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV" , {title}'
        )
        m3u_lines.append(extinf)
        m3u_lines.append(f"{stream_url}\n")

    # Ghi file giovang.m3u
    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"Đã cập nhật danh sách {len(matches)} trận đấu vào giovang.m3u")


if __name__ == "__main__":
    fetch_and_generate()
    
