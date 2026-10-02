import time
import requests

# Bảng ánh xạ icon môn thể thao chuẩn theo mẫu
SPORT_ICONS = {
    "football": "⚽",
    "bongda": "⚽",
    "tennis": "🥎",
    "esport": "🎮",
    "bongchuyen": "🏐",
    "volleyball": "🏐",
    "billiards": "🎱",
    "bida": "🎱",
    "pool": "🎱",
    "basketball": "🏀",
    "bongro": "🏀",
    "f1": "[formula1]",
    "formula1": "[formula1]",
    "mma": "🥊🥋",
    "boxing": "🥊🥋",
    "one": "🥊🥋",
}

# Link HLS video tín hiệu chờ chuẩn (thay cho link freem3u bị hỏng)
WAITING_STREAM = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"


def get_stream_url(match, headers):
    """Lấy link m3u8 phát trực tiếp chuẩn cho từng trận"""
    match_id = match.get("id") or match.get("fi")
    is_live = (
        match.get("is_live") is True
        or match.get("status_code") == "LIVE"
        or match.get("status") == "Đang diễn ra"
    )

    # 1. Ưu tiên link HLS trực tiếp từ API nếu có
    for key in ["hls", "stream_url", "link", "play_url"]:
        url = match.get(key)
        if (
            url
            and isinstance(url, str)
            and url.startswith("http")
            and "no-signal" not in url
        ):
            return url

    # 2. Nếu trận đang LIVE, bóc tách luồng phát thực tế
    if is_live:
        if match_id:
            try:
                detail_api = f"https://live-api.keonhacaitp.one/storage/livestream/detail/{match_id}.json"
                res = requests.get(detail_api, headers=headers, timeout=4)
                if res.status_code == 200:
                    d_res = res.json().get("response", {})
                    for key in ["hls", "stream_url", "link"]:
                        d_url = d_res.get(key)
                        if (
                            d_url
                            and isinstance(d_url, str)
                            and d_url.startswith("http")
                        ):
                            return d_url
            except Exception:
                pass

        time_start = match.get("time_start")
        if time_start:
            return f"https://ftlh5sc02iliv.vcdn.cloud/{time_start}_hd/{time_start}_hd@720p.m3u8"

    # 3. Trận chưa diễn ra -> Trả về link video chờ chuẩn HLS (không bị báo Link lỗi)
    return WAITING_STREAM


def generate_m3u():
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
        print(f"Lỗi gọi API Giờ Vàng: {e}")
        return

    matches = data.get("response", [])
    if not matches:
        print("Không có trận đấu nào.")
        return

    m3u_blocks = ["#EXTM3U"]

    for match in matches:
        # Kiểm tra chính xác trạng thái Trực tiếp
        is_live = (
            match.get("is_live") is True
            or match.get("status_code") == "LIVE"
            or match.get("status") == "Đang diễn ra"
        )

        # CHỈ thêm chấm xanh 🟢 nếu trận đang LIVE
        live_dot = "🟢 " if is_live else ""

        # Thời gian & Ngày
        time_str = match.get("time", "")[:5]
        day_month = match.get("day_month", "")

        # Icon thể thao
        sport_type = str(match.get("type", "football")).lower()
        sport_icon = SPORT_ICONS.get(sport_type, "⚽")

        # Tên đội bóng
        teams = match.get("teams", {})
        home_name = teams.get("home", {}).get("name", "").strip()
        away_name = teams.get("away", {}).get("name", "").strip()

        # Logo
        logo = (
            teams.get("home", {}).get("logo")
            or match.get("league", {}).get("icon")
            or ""
        )

        # Tên BLV
        blv_list = match.get("blv", [])
        blv_part = f" ({blv_list[0]})" if (blv_list and blv_list[0]) else ""

        # Định dạng tiêu đề kênh chuẩn mẫu
        title = f"{live_dot}{time_str} {day_month} {sport_icon} {home_name} vs {away_name}{blv_part} [hls]"

        # Khối EXTINF
        extinf = (
            f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV" , {title}'
        )

        # Lấy luồng phát
        stream_url = get_stream_url(match, headers)

        m3u_blocks.append(f"{extinf}\n{stream_url}")

    # Xuất file giovang.m3u
    content = "\n\n".join(m3u_blocks) + "\n"
    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Đã xuất thành công {len(matches)} trận đấu vào giovang.m3u")


if __name__ == "__main__":
    generate_m3u()
    
