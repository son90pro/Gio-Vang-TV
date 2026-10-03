import re
import time
import requests

# URL API của Giờ Vàng TV
LIVE_API_URL = "https://live-api.keonhacaitp.one/storage/livestream/live.json"
DETAIL_API_URL = "https://live-api.keonhacaitp.one/api/fixture-detail/"

# Ánh xạ icon môn thể thao
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

# Headers giả lập trình duyệt web
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://giovang.co",
    "Referer": "https://giovang.co/",
}


def format_blv_name(blv_list):
    """Định dạng tên BLV"""
    if not blv_list:
        return "BLV"
    blv = blv_list[0] if isinstance(blv_list, list) else str(blv_list)
    blv = (
        blv.replace("blv-", "")
        .replace("blv", "")
        .replace("BLV", "")
        .strip()
    )
    return blv.capitalize() if blv else "BLV"


def is_match_valid(match):
    """Lọc bỏ các trận đấu đã kết thúc"""
    status_code = str(match.get("status_code", "")).upper()
    status_text = str(match.get("status", "")).lower()

    # Danh sách trạng thái đã kết thúc cần loại bỏ
    finished_keywords = ["FINISHED", "FT", "ENDED", "CANCELLED", "POSTPONED"]
    if status_code in finished_keywords or "kết thúc" in status_text or "hoãn" in status_text:
        return False

    return True


def get_real_stream_urls(match_id):
    """Gọi API chi tiết để bóc tách link .m3u8 thực tế"""
    urls = []
    try:
        res = requests.get(f"{DETAIL_API_URL}{match_id}", headers=HEADERS, timeout=6)
        if res.status_code == 200:
            res_text = res.text
            # Quét tìm tất cả link .m3u8 trong JSON
            found_urls = re.findall(r'https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*', res_text)
            for u in found_urls:
                clean_url = u.replace("\\/", "/")
                if "no-signal" not in clean_url and "freem3u" not in clean_url:
                    urls.append(clean_url)
    except Exception as e:
        print(f"Lỗi khi lấy stream cho trận {match_id}: {e}")

    return list(set(urls))


def fetch_matches():
    """Lấy danh sách tất cả các trận đấu"""
    timestamp = int(time.time())
    url = f"{LIVE_API_URL}?t={timestamp}"

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return response.json().get("response", [])
    except Exception as e:
        print(f"Lỗi kết nối API chính: {e}")
    return []


def generate_m3u():
    matches = fetch_matches()
    m3u_lines = ["#EXTM3U\n"]
    count_added = 0

    for match in matches:
        # 1. Kiểm tra và bỏ qua trận đã kết thúc
        if not is_match_valid(match):
            continue

        match_id = match.get("fi") or match.get("id", "")
        sport_type = str(match.get("type", "football")).lower()
        icon = SPORT_ICONS.get(sport_type, "⚽")

        time_str = match.get("time", "00:00:00")[:5]
        day_month = match.get("day_month", "")

        teams = match.get("teams", {})
        home_team = teams.get("home", {})
        away_team = teams.get("away", {})

        home_name = home_team.get("name", "").strip() if home_team else ""
        away_name = away_team.get("name", "").strip() if away_team else ""

        logo = (
            (home_team.get("logo") if home_team else None)
            or (away_team.get("logo") if away_team else None)
            or match.get("league", {}).get("icon")
            or ""
        )

        blv_name = format_blv_name(match.get("blv", []))

        is_live = match.get("is_live", False)
        status_code = str(match.get("status_code", "")).upper()

        if is_live or status_code == "LIVE":
            status_symbol = "🟢 "
        else:
            status_symbol = "🟡 "

        # 2. Lấy link luồng phát thực tế
        stream_urls = get_real_stream_urls(match_id)

        # Định danh tiêu đề chuẩn mẫu
        title = f"{status_symbol}{time_str} {day_month} {icon} {home_name} vs {away_name} ({blv_name}) [hls]"

        if stream_urls:
            for idx, stream_url in enumerate(stream_urls):
                display_title = title if len(stream_urls) == 1 else f"{title} - Luồng {idx + 1}"
                
                # Thêm Headers vào M3U để IPTV Player không bị chặn CDN
                m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV" , {display_title}')
                m3u_lines.append("#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
                m3u_lines.append("#EXTVLCOPT:http-referrer=https://giovang.co/")
                # Link kèm Pipe Header hỗ trợ TiviMate/OTT Navigator
                m3u_lines.append(f"{stream_url}|Referer=https://giovang.co/&User-Agent=Mozilla/5.0")
                m3u_lines.append("")
            count_added += 1
        else:
            # Đối với các trận Sắp diễn ra (🟡) chưa có link CDN, giữ link chờ chuẩn
            if status_symbol == "🟡 ":
                m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV" , {title}')
                m3u_lines.append("https://freem3u.xyz/static/no-signal/low.m3u8")
                m3u_lines.append("")
                count_added += 1

    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"Đã cập nhật danh sách thành công: {count_added} trận (Đang & Sắp diễn ra).")


if __name__ == "__main__":
    generate_m3u()
    
