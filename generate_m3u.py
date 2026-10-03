import re
import time
import requests

LIVE_API_URL = "https://live-api.keonhacaitp.one/storage/livestream/live.json"
DEFAULT_OFFLINE_STREAM = "https://freem3u.xyz/static/no-signal/low.m3u8"

SPORT_ICONS = {
    "football": "⚽",
    "bongda": "⚽",
    "basketball": "🏀",
    "bongro": "🏀",
    "bongchuyen": "🏐",
    "tennis": "🥎",
    "vothuat": "🥊",
    "esports": "🎮",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://giovang.co",
    "Referer": "https://giovang.co/",
}

def is_match_valid(match):
    status_code = str(match.get("status_code", "")).upper()
    status_text = str(match.get("status", "")).lower()

    finished_keywords = ["FINISHED", "FT", "ENDED", "CANCELLED", "POSTPONED"]
    if status_code in finished_keywords or "kết thúc" in status_text or "hoãn" in status_text:
        return False
    return True

def fetch_matches():
    timestamp = int(time.time())
    url = f"{LIVE_API_URL}?t={timestamp}"

    try:
        response = requests.get(url, headers=HEADERS, timeout=12)
        print(f"[DEBUG] HTTP Status Code API chính: {response.status_code}")
        
        if response.status_code == 200:
            res_json = response.json()
            matches = res_json.get("response", [])
            print(f"[DEBUG] Tổng số trận nhận từ API: {len(matches)}")
            return matches
        else:
            print(f"[ERR] API trả về lỗi {response.status_code}. Phản hồi: {response.text[:200]}")
    except Exception as e:
        print(f"[ERR] Không thể kết nối tới API: {e}")
    return []

def get_real_stream_urls(match):
    match_id = match.get("fi") or match.get("id", "")
    if not match_id:
        return []

    urls = []
    # Danh sách các trang xem trực tiếp chứa mã nhúng luồng m3u8
    candidate_pages = [
        f"https://giovang.co/truc-tiep/{match_id}",
        f"https://giovang.rent/truc-tiep/{match_id}",
        f"https://giovang.co/truc-tiep-match/{match_id}",
    ]

    for page_url in candidate_pages:
        try:
            res = requests.get(page_url, headers=HEADERS, timeout=6)
            if res.status_code == 200:
                # Tìm tất cả link .m3u8 trong HTML trang
                found_urls = re.findall(r'https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*', res.text)
                for u in found_urls:
                    clean_url = u.replace("\\/", "/")
                    if "no-signal" not in clean_url and "freem3u" not in clean_url:
                        urls.append(clean_url)
                
                if urls:
                    print(f"[DEBUG] Bóc tách thành công {len(urls)} link m3u8 từ {page_url}")
                    break
        except Exception as e:
            print(f"[DEBUG] Lỗi cào stream ({page_url}): {e}")

    return list(set(urls))

def generate_m3u():
    matches = fetch_matches()
    m3u_lines = ["#EXTM3U\n"]
    count_added = 0

    for match in matches:
        if not is_match_valid(match):
            continue

        sport_type = str(match.get("type", "football")).lower()
        icon = SPORT_ICONS.get(sport_type, "⚽")

        time_str = match.get("time", "00:00:00")[:5]
        day_month = match.get("day_month", "")

        teams = match.get("teams", {}) or {}
        home_team = teams.get("home", {}) if isinstance(teams, dict) else {}
        away_team = teams.get("away", {}) if isinstance(teams, dict) else {}

        home_name = home_team.get("name", "").strip() if home_team else ""
        away_name = away_team.get("name", "").strip() if away_team else ""

        logo = (
            (home_team.get("logo") if home_team else None)
            or (away_team.get("logo") if away_team else None)
            or match.get("league", {}).get("icon")
            or ""
        )

        blv_list = match.get("blv", [])
        blv_name = blv_list[0] if isinstance(blv_list, list) and blv_list else "BLV"

        is_live = match.get("is_live", False)
        status_code = str(match.get("status_code", "")).upper()
        status_symbol = "🟢 " if (is_live or status_code == "LIVE") else "🟡 "

        # Gọi hàm lấy link m3u8 thật từ trang web
        stream_urls = get_real_stream_urls(match)
        if not stream_urls:
            stream_urls = [DEFAULT_OFFLINE_STREAM]

        title = f"{status_symbol}{time_str} {day_month} {icon} {home_name} vs {away_name} ({blv_name})"

        for idx, stream_url in enumerate(stream_urls):
            display_title = title if len(stream_urls) == 1 else f"{title} - Luồng {idx + 1}"
            
            m3u_lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV", {display_title}')
            m3u_lines.append("#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            m3u_lines.append("#EXTVLCOPT:http-referrer=https://giovang.co/")
            
            if "freem3u.xyz" in stream_url:
                m3u_lines.append(stream_url)
            else:
                m3u_lines.append(f"{stream_url}|Referer=https://giovang.co/&User-Agent=Mozilla/5.0")
            m3u_lines.append("")
        
        count_added += 1

    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"Đã cập nhật danh sách thành công: {count_added} trận (Đang & Sắp diễn ra).")

if __name__ == "__main__":
    generate_m3u()
