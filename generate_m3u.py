import time
import requests

# Bảng ánh xạ icon môn thể thao chuẩn
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

# Map tên BLV gọn đẹp theo đúng mẫu của anh Sơn
BLV_NAME_MAP = {
    "blv-vit": "Vịt",
    "blv vit": "Vịt",
    "blv-sun": "Sún",
    "blv sun": "Sún",
    "blv-diec": "Điếc",
    "blv diec": "Điếc",
    "blv-beo": "Bee",
    "blv beo": "Bee",
    "blv mù": "Mù",
    "blv-mu": "Mù",
    "blv mu": "Mù",
}

NO_SIGNAL_URL = "https://freem3u.xyz/static/no-signal/low.m3u8"


def clean_blv(blv_data):
    """Rút gọn tên BLV đúng chuẩn mẫu"""
    if not blv_data:
        return ""
    raw = blv_data[0] if isinstance(blv_data, list) else str(blv_data)
    raw = raw.strip()
    if not raw:
        return ""

    low_raw = raw.lower()
    if low_raw in BLV_NAME_MAP:
        return f"({BLV_NAME_MAP[low_raw]})"

    return f"({raw})"


def get_match_stream_url(match, headers):
    """Lấy link .m3u8 trực tiếp từ match object hoặc gọi API detail"""
    # 1. Kiểm tra các field link có sẵn trong live.json
    for key in ["hls", "stream_url", "play_url", "link"]:
        val = match.get(key)
        if (
            val
            and isinstance(val, str)
            and val.startswith("http")
            and ".m3u8" in val
        ):
            return val

    # 2. Nếu là trận LIVE mà chưa có link, gọi API detail để lấy luồng vcdn thực tế
    match_id = match.get("id") or match.get("fi")
    if match_id:
        try:
            detail_url = f"https://live-api.keonhacaitp.one/storage/livestream/detail/{match_id}.json"
            res = requests.get(detail_url, headers=headers, timeout=4)
            if res.status_code == 200:
                data = res.json().get("response", {})
                for key in ["hls", "stream_url", "play_url", "link"]:
                    val = data.get(key)
                    if (
                        val
                        and isinstance(val, str)
                        and val.startswith("http")
                        and ".m3u8" in val
                    ):
                        return val
        except Exception:
            pass

    return None


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
        print(f"Lỗi khi tải API: {e}")
        return

    matches = data.get("response", [])
    if not matches:
        print("Không có trận đấu nào.")
        return

    m3u_blocks = ["#EXTM3U"]

    for match in matches:
        is_live = (
            match.get("is_live") is True
            or match.get("status_code") == "LIVE"
            or match.get("status") == "Đang diễn ra"
        )

        stream_url = None
        if is_live:
            stream_url = get_match_stream_url(match, headers)

        # Xác định biểu tượng trạng thái và URL stream
        if is_live and stream_url and "no-signal" not in stream_url:
            status_icon = "🟢 "
        elif is_live:
            status_icon = "🟡 "
            stream_url = NO_SIGNAL_URL
        else:
            status_icon = ""
            stream_url = NO_SIGNAL_URL

        # Thời gian, môn thể thao & tên đội
        time_str = match.get("time", "")[:5]
        day_month = match.get("day_month", "")

        sport_type = str(match.get("type", "football")).lower()
        sport_icon = SPORT_ICONS.get(sport_type, "⚽")

        teams = match.get("teams", {})
        home_name = teams.get("home", {}).get("name", "").strip()
        away_name = teams.get("away", {}).get("name", "").strip()

        logo = (
            teams.get("home", {}).get("logo")
            or match.get("league", {}).get("icon")
            or ""
        )

        blv_str = clean_blv(match.get("blv"))
        blv_part = f" {blv_str}" if blv_str else ""

        title = f"{status_icon}{time_str} {day_month} {sport_icon} {home_name} vs {away_name}{blv_part} [hls]"
        extinf = f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV" , {title}'

        # Cấu trúc 2 dòng gọn gàng như mẫu
        m3u_blocks.append(f"{extinf}\n{stream_url}")

    # Đóng gói file M3U cách nhau đúng 1 dòng trống
    full_content = "\n\n".join(m3u_blocks) + "\n"

    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write(full_content)

    print(f"Đã xuất thành công {len(matches)} trận vào file giovang.m3u")


if __name__ == "__main__":
    generate_m3u()
    
