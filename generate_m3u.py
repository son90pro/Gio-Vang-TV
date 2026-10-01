import datetime
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zoneinfo

TZ_VN = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")

# Các đường dẫn API chuẩn của hệ thống Giờ Vàng
API_URLS = [
    "https://live-api.keonhacaitp.one/storage/livestream/live.json",
]

WEB_URL = "https://giovang.rent/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like"
        " Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
    ),
    "Referer": "https://giovang.rent/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Bản đồ phân loại môn thể thao & Thứ tự ưu tiên
SPORT_MAP = {
    "football": (1, "Bóng Đá"),
    "soccer": (1, "Bóng Đá"),
    "bongda": (1, "Bóng Đá"),
    "bongchuyen": (2, "Bóng Chuyền"),
    "volleyball": (2, "Bóng Chuyền"),
    "basketball": (3, "Bóng Rổ"),
    "bongro": (3, "Bóng Rổ"),
    "tennis": (4, "Quần Vợt"),
    "quanvot": (4, "Quần Vợt"),
    "esport": (5, "Esports"),
    "esports": (5, "Esports"),
    "bongban": (6, "Bóng Bàn"),
}


def detect_sport(sport_type, league_name="", team_name=""):
    stype = str(sport_type).lower().strip()
    if stype in SPORT_MAP:
        return SPORT_MAP[stype]

    text = f"{stype} {league_name} {team_name}".lower()
    if any(
        k in text
        for k in [
            "bóng đá",
            "football",
            "soccer",
            "v-league",
            "premier league",
            "champions league",
            "fc ",
            "united",
        ]
    ):
        return (1, "Bóng Đá")
    if any(k in text for k in ["bóng chuyền", "volleyball"]):
        return (2, "Bóng Chuyền")
    if any(k in text for k in ["bóng rổ", "basketball", "nba"]):
        return (3, "Bóng Rổ")
    if any(k in text for k in ["tennis", "quần vợt", "atp", "wta"]):
        return (4, "Quần Vợt")
    if any(k in text for k in ["esport", "valorant", "lol", "dota", "vct"]):
        return (5, "Esports")

    return (99, "Thể Thao Khác")


def fetch_data(url):
    """Tải dữ liệu từ URL và in log lỗi chi tiết"""
    sep = "&" if "?" in url else "?"
    full_url = f"{url}{sep}t={int(time.time())}"
    print(f"--> Đang tải URL: {full_url}")

    req = urllib.request.Request(full_url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            content = resp.read().decode("utf-8")
            print(f"    [Thành công] HTTP Status: {status}")
            return content
    except urllib.error.HTTPError as e:
        print(f"    [Lỗi HTTP] Code: {e.code} - Reason: {e.reason}")
    except urllib.error.URLError as e:
        print(f"    [Lỗi Kết Nối] Reason: {e.reason}")
    except Exception as e:
        print(f"    [Lỗi Không Xác Định] {e}")

    return None


def parse_html_fallback():
    """Fallback: Bóc tách danh sách trận đấu trực tiếp từ HTML trang web nếu API bị khóa"""
    print("--> Thử nghiệm cào dữ liệu trực tiếp từ trang HTML...")
    html_content = fetch_data(WEB_URL)
    if not html_content:
        return []

    matches = []
    # Tìm đoạn JSON nhúng trong HTML (Next.js / Nuxt / Custom State)
    json_matches = re.findall(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html_content,
        re.DOTALL,
    )
    if json_matches:
        try:
            data = json.loads(json_matches[0])
            # Bóc tách props
            page_props = (
                data.get("props", {}).get("pageProps", {}).get("matches", [])
            )
            if page_props:
                print(
                    f"    Tìm thấy {len(page_props)} trận từ __NEXT_DATA__"
                )
                return page_props
        except Exception as e:
            print(f"    Lỗi parse JSON nhúng HTML: {e}")

    return matches


def main():
    raw_matches = []

    # 1. Thử cào qua API JSON
    for api_url in API_URLS:
        content = fetch_data(api_url)
        if content:
            try:
                data = json.loads(content)
                items = data.get("response") or data.get("data") or []
                if isinstance(items, list) and len(items) > 0:
                    raw_matches.extend(items)
                    print(
                        f"    [OK] Lấy được {len(items)} trận từ API {api_url}"
                    )
            except Exception as e:
                print(f"    Lỗi parse JSON từ API: {e}")

    # 2. Nếu API không trả về dữ liệu, kích hoạt Fallback HTML
    if not raw_matches:
        raw_matches = parse_html_fallback()

    if not raw_matches:
        print(
            "CRITICAL: Không thể lấy dữ liệu từ cả API lẫn Web HTML. Hãy kiểm tra lại log HTTP ở trên."
        )
        sys.exit(1)

    # 3. Lọc trùng lặp & Chuẩn hóa
    unique_matches = {}
    for m in raw_matches:
        m_id = m.get("id") or m.get("fi")
        if m_id and m_id not in unique_matches:
            unique_matches[m_id] = m

    valid_matches = list(unique_matches.values())

    # 4. Sắp xếp ưu tiên môn thể thao & Thời gian
    def sort_key(m):
        sport_prio, _ = detect_sport(
            m.get("type", ""),
            m.get("league", {}).get("title", ""),
            m.get("teams", {}).get("home", {}).get("name", ""),
        )
        is_live = (
            0
            if (m.get("is_live") or str(m.get("status_code")).upper() == "LIVE")
            else 1
        )
        time_start = m.get("time_start") or 0
        return (sport_prio, is_live, time_start)

    valid_matches.sort(key=sort_key)

    # 5. Tạo file Playlist M3U
    m3u_lines = ["#EXTM3U"]

    for match in valid_matches:
        match_id = match.get("id") or match.get("fi")
        sport_type = match.get("type", "")
        league_title = match.get("league", {}).get("title", "Giải đấu")

        teams = match.get("teams", {})
        home_name = teams.get("home", {}).get("name", "Đội nhà").strip()
        away_name = teams.get("away", {}).get("name", "Đội khách").strip()
        home_logo = teams.get("home", {}).get("logo", "")

        prio, group_title = detect_sport(sport_type, league_title, home_name)

        ts = match.get("time_start")
        if ts:
            dt = datetime.datetime.fromtimestamp(ts, tz=TZ_VN)
            time_str = dt.strftime("%H:%M %d/%m")
        else:
            time_str = (
                f"{match.get('time', '')} {match.get('day_month', '')}".strip()
                or "N/A"
            )

        blv_list = match.get("blv", [])
        blv_str = f" [BLV: {', '.join(blv_list)}]" if blv_list else ""
        status = match.get("status") or (
            "LIVE" if match.get("is_live") else "Sắp diễn ra"
        )

        # Trỏ về trang player / m3u8
        play_url = f"https://giovang.rent/live/{match_id}"

        title = f"[{time_str}] {home_name} vs {away_name} ({league_title}){blv_str} - [{status}]"
        extinf = f'#EXTINF:-1 tvg-logo="{home_logo}" group-title="{group_title}",{title}'
        m3u_lines.append(extinf)
        m3u_lines.append(play_url)

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(
        f"==> HOÀN THÀNH: Đã xuất {len(valid_matches)} trận đấu vào file playlist.m3u"
    )


if __name__ == "__main__":
    main()
    
