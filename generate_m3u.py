import re
import time
import requests

# Bảng ánh xạ icon môn thể thao
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

# Link tín hiệu chờ chuẩn giúp TiviMate không báo lỗi
NO_SIGNAL_URL = "https://freem3u.xyz/static/no-signal/low.m3u8"


def clean_blv_name(blv_data):
    """Xử lý định dạng tên BLV theo chuẩn mẫu"""
    if not blv_data:
        return ""
    name = blv_data[0] if isinstance(blv_data, list) else str(blv_data)
    name = name.strip()
    if not name:
        return ""
    return f"({name})"


def fetch_live_m3u8(match_id, headers):
    """Lấy link .m3u8 thực tế khi trận đấu đang phát LIVE"""
    if not match_id:
        return None

    # 1. Gọi API chi tiết của trận đấu
    try:
        detail_url = f"https://live-api.keonhacaitp.one/storage/livestream/detail/{match_id}.json"
        r = requests.get(detail_url, headers=headers, timeout=4)
        if r.status_code == 200:
            d = r.json().get("response", {})
            for key in [
                "hls",
                "stream_url",
                "link",
                "play_url",
                "m3u8",
                "link_embed",
            ]:
                val = d.get(key)
                if (
                    val
                    and isinstance(val, str)
                    and val.startswith("http")
                    and ".m3u8" in val
                ):
                    return val
    except Exception:
        pass

    # 2. Cào mã nguồn trang xem trực tiếp nếu API không trả về
    web_urls = [
        f"https://giovang.rent/xem-truc-tiep/{match_id}",
        f"https://giovang.rent/live/{match_id}",
        f"https://giovang.rent/?p={match_id}",
    ]
    for w_url in web_urls:
        try:
            r = requests.get(w_url, headers=headers, timeout=4)
            if r.status_code == 200:
                found = re.findall(r'https?://[^\s"\'<>]+?\.m3u8', r.text)
                if found:
                    return found[0]
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
        print("Không tìm thấy danh sách trận đấu.")
        return

    m3u_entries = ["#EXTM3U"]

    for match in matches:
        match_id = match.get("id") or match.get("fi")
        is_live = (
            match.get("is_live") is True
            or match.get("status_code") == "LIVE"
            or match.get("status") == "Đang diễn ra"
        )

        # Lấy luồng stream trực tiếp
        stream_url = None
        if is_live:
            # Kiểm tra trong object match từ live.json
            for k in ["hls", "stream_url", "link", "play_url"]:
                val = match.get(k)
                if (
                    val
                    and isinstance(val, str)
                    and val.startswith("http")
                    and ".m3u8" in val
                ):
                    stream_url = val
                    break

            if not stream_url:
                stream_url = fetch_live_m3u8(match_id, headers)

        # Quyết định Ký hiệu màu & URL stream
        if is_live and stream_url and stream_url != NO_SIGNAL_URL:
            status_icon = "🟢 "
        elif is_live:
            status_icon = "🟡 "
            stream_url = NO_SIGNAL_URL
        else:
            status_icon = ""
            stream_url = NO_SIGNAL_URL

        # Thời gian, môn thể thao, tên đội
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

        # Tên BLV
        blv_part = clean_blv_name(match.get("blv"))
        if blv_part:
            blv_part = f" {blv_part}"

        # Đóng gói dòng thông tin kênh
        title = f"{status_icon}{time_str} {day_month} {sport_icon} {home_name} vs {away_name}{blv_part} [hls]"
        extinf = f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV" , {title}'

        m3u_entries.append(f"{extinf}\n{stream_url}")

    # Tạo file .m3u đúng định dạng có dòng trống phân cách giữa các trận
    full_m3u = "\n\n".join(m3u_entries) + "\n"

    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write(full_m3u)

    print(f"Đã xuất thành công {len(matches)} trận đấu ra file giovang.m3u")


if __name__ == "__main__":
    generate_m3u()
    
