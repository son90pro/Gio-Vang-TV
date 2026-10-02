import re
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

# Bảng chuẩn hóa tên BLV theo mẫu
BLV_MAP = {
    "blv-vit": "Vịt",
    "blv vit": "Vịt",
    "blv-sun": "Sún",
    "blv sun": "Sún",
    "blv mù": "Mù",
    "blv-mu": "Mù",
    "blv hấu": "BLV Hấu",
    "blv-hau": "BLV Hấu",
    "blvhau": "BLV Hấu",
    "riko": "Riko",
    "blvtuimu": "blvtuimu",
}


def format_blv(blv_data):
    """Xử lý định dạng tên BLV chuẩn mẫu (Tên_BLV)"""
    if not blv_data:
        return ""

    raw = blv_data[0] if isinstance(blv_data, list) else str(blv_data)
    raw = raw.strip()

    if not raw:
        return ""

    # Kiểm tra trong bảng map
    low_raw = raw.lower()
    if low_raw in BLV_MAP:
        return f"({BLV_MAP[low_raw]})"

    return f"({raw})"


def get_live_stream_url(match, headers):
    """Hàm đa tầng tìm link .m3u8 trực tiếp để xem được trên TiviMate"""
    match_id = match.get("id") or match.get("fi")

    # Cách 1: Kiểm tra trực tiếp các key link trong API nếu có
    for key in ["hls", "stream_url", "link", "play_url", "embed"]:
        url = match.get(key)
        if url and isinstance(url, str) and url.startswith("http"):
            return url

    # Cách 2: Gọi API detail của Giờ Vàng TV bằng match_id
    if match_id:
        detail_api = f"https://live-api.keonhacaitp.one/storage/livestream/detail/{match_id}.json"
        try:
            res = requests.get(detail_api, headers=headers, timeout=5)
            if res.status_code == 200:
                d_data = res.json()
                d_res = d_data.get("response", {})
                for key in ["hls", "stream_url", "link", "play_url"]:
                    url = d_res.get(key)
                    if url and isinstance(url, str) and url.startswith("http"):
                        return url
        except Exception:
            pass

        # Cách 3: Cào trang web phòng xem live trực tiếp
        web_urls = [
            f"https://giovang.rent/xem-truc-tiep/{match_id}",
            f"https://giovang.rent/live/{match_id}",
            f"https://giovang.rent/?p={match_id}",
        ]
        for w_url in web_urls:
            try:
                res = requests.get(w_url, headers=headers, timeout=5)
                if res.status_code == 200:
                    # Tìm link m3u8 trong thẻ <video> hoặc mã nguồn JavaScript
                    found = re.findall(
                        r'https?://[^\s"\'<>]+?\.m3u8', res.text
                    )
                    if found:
                        return found[0]
            except Exception:
                pass

    # Cách 4: Tự dựng link VCDN dựa trên time_start nếu trận đấu đang phát Trực tiếp
    is_live = (
        match.get("is_live") is True
        or match.get("status_code") == "LIVE"
        or match.get("status") == "Đang diễn ra"
    )
    time_start = match.get("time_start")

    if is_live and time_start:
        return f"https://ftlh5sc02iliv.vcdn.cloud/{time_start}_hd/{time_start}_hd@720p.m3u8"

    # Trận chưa diễn ra hoặc hết giờ -> Dùng link no-signal
    return "https://freem3u.xyz/static/no-signal/low.m3u8"


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
        print(f"Lỗi kết nối API: {e}")
        return

    matches = data.get("response", [])
    if not matches:
        print("Không có dữ liệu trận đấu.")
        return

    m3u_blocks = ["#EXTM3U"]

    for match in matches:
        # 1. Trạng thái Live (🟢)
        is_live = (
            match.get("is_live") is True
            or match.get("status_code") == "LIVE"
            or match.get("status") == "Đang diễn ra"
        )
        live_symbol = "🟢 " if is_live else ""

        # 2. Thời gian & Ngày tháng
        raw_time = match.get("time", "")
        time_str = raw_time[:5] if len(raw_time) >= 5 else raw_time
        day_month = match.get("day_month", "")

        # 3. Icon thể thao
        sport_type = str(match.get("type", "football")).lower()
        sport_icon = SPORT_ICONS.get(sport_type, "⚽")

        # 4. Tên đội bóng
        teams = match.get("teams", {})
        home_name = teams.get("home", {}).get("name", "").strip()
        away_name = teams.get("away", {}).get("name", "").strip()

        # 5. Logo đội bóng (ưu tiên logo đội nhà, fallback sang logo giải)
        logo = (
            teams.get("home", {}).get("logo")
            or match.get("league", {}).get("icon")
            or ""
        )

        # 6. BLV
        blv_str = format_blv(match.get("blv"))
        blv_part = f" {blv_str}" if blv_str else ""

        # 7. Lấy link stream trực tiếp
        stream_url = get_live_stream_url(match, headers)

        # 8. Ghép tiêu đề chuẩn mẫu: , 🟢 HH:MM DD/MM ⚽ Đội A vs Đội B (BLV) [hls]
        title = f"{live_symbol}{time_str} {day_month} {sport_icon} {home_name} vs {away_name}{blv_part} [hls]"

        # Khối kênh chuẩn M3U (có khoảng trống sau dấu phẩy `, `)
        extinf = f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV" , {title}'

        # Lưu thành block (tiêu đề + link)
        m3u_blocks.append(f"{extinf}\n{stream_url}")

    # Ghép các block lại với khoảng trống dòng đúng như file mẫu
    full_m3u_content = "\n\n".join(m3u_blocks) + "\n"

    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write(full_m3u_content)

    print(f"Đã xuất thành công {len(matches)} trận đấu ra file giovang.m3u")


if __name__ == "__main__":
    generate_m3u()
    
