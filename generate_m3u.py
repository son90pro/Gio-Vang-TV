import datetime
import json
import re
import time
import urllib.error
import urllib.request
import zoneinfo

# Múi giờ Việt Nam (GMT+7)
TZ_VN = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Android 16; Mobile; rv:156.0) Gecko/156.0 Firefox/156.0"
    ),
    "Referer": "https://giovang.rent/",
    "Accept": "application/json, text/plain, */*",
}

# Bản đồ phân loại môn thể thao & Thứ tự ưu tiên
SPORT_MAP = {
    "football": (1, "Bóng Đá"),
    "soccer": (1, "Bóng Đá"),
    "bongda": (1, "Bóng Đá"),
    "bong-da": (1, "Bóng Đá"),
    "bongchuyen": (2, "Bóng Chuyền"),
    "volleyball": (2, "Bóng Chuyền"),
    "bong-chuyen": (2, "Bóng Chuyền"),
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

    combined = f"{stype} {league_name} {team_name}".lower()
    if any(
        k in combined
        for k in [
            "bóng đá",
            "football",
            "soccer",
            "v-league",
            "premier league",
            "champions league",
            "asean cup",
            "fifa",
            "u21",
            "u23",
            "giao hữu",
            "fc ",
        ]
    ):
        return (1, "Bóng Đá")
    if any(k in combined for k in ["bóng chuyền", "volleyball", "asiad"]):
        return (2, "Bóng Chuyền")
    if any(k in combined for k in ["bóng rổ", "basketball", "nba"]):
        return (3, "Bóng Rổ")
    if any(k in combined for k in ["tennis", "quần vợt", "atp", "wta", "open"]):
        return (4, "Quần Vợt")
    if any(k in combined for k in ["esport", "valorant", "lol", "dota", "vct"]):
        return (5, "Esports")

    return (99, "Thể Thao Khác")


def fetch_data(url):
    sep = "&" if "?" in url else "?"
    full_url = f"{url}{sep}t={int(time.time())}"
    req = urllib.request.Request(full_url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        return None


def resolve_stream_url(match):
    """Tạo trực tiếp URL vcdn.cloud tốc độ cao không qua request trung gian"""
    # 1. Kiểm tra nếu có sẵn play_url hoặc links trong API
    if match.get("play_url") and "http" in str(match.get("play_url")):
        return str(match["play_url"])

    links = match.get("links") or match.get("play_urls") or []
    if isinstance(links, list):
        for item in links:
            if isinstance(item, dict):
                u = item.get("url") or item.get("link") or item.get("m3u8")
                if u and "http" in str(u):
                    return str(u)
            elif isinstance(item, str) and "http" in item:
                return item

    # 2. Ưu tiên trích xuất ID phòng phát (room_id, stream_id, live_id, fi, id)
    for key in ["room_id", "stream_id", "live_id", "room", "fi", "id"]:
        val = match.get(key)
        if val and str(val).strip().isdigit():
            val_str = str(val).strip()
            if len(val_str) >= 5:
                return f"https://ftlh5sc02iliv.vcdn.cloud/{val_str}_hd/{val_str}_hd@720p.m3u8"

    # 3. Mặc định fallback ID
    m_id = match.get("id") or match.get("fi") or "0"
    return f"https://ftlh5sc02iliv.vcdn.cloud/{m_id}_hd/{m_id}_hd@720p.m3u8"


def main():
    now_vn = datetime.datetime.now(TZ_VN)
    tomorrow_vn = now_vn + datetime.timedelta(days=1)

    d_today_1 = now_vn.strftime("%d-%m-%Y")
    d_today_2 = now_vn.strftime("%Y-%m-%d")
    d_tom_1 = tomorrow_vn.strftime("%d-%m-%Y")
    d_tom_2 = tomorrow_vn.strftime("%Y-%m-%d")

    # Các nguồn API quét toàn bộ trận đấu Hôm nay và Ngày mai
    api_sources = [
        "https://live-api.keonhacaitp.one/storage/livestream/live.json",
        "https://live-api.keonhacaitp.one/storage/livestream/home.json",
        "https://live-api.keonhacaitp.one/storage/livestream/match.json",
        "https://live-api.keonhacaitp.one/storage/livestream/schedule.json",
        f"https://live-api.keonhacaitp.one/storage/livestream/date/{d_today_1}.json",
        f"https://live-api.keonhacaitp.one/storage/livestream/date/{d_tom_1}.json",
        f"https://live-api.keonhacaitp.one/storage/livestream/date/{d_today_2}.json",
        f"https://live-api.keonhacaitp.one/storage/livestream/date/{d_tom_2}.json",
    ]

    all_matches_dict = {}

    # 1. Quét API JSON
    for url in api_sources:
        raw_text = fetch_data(url)
        if raw_text:
            try:
                data = json.loads(raw_text)
                items = data.get("response") or data.get("data") or []
                if isinstance(items, list):
                    for item in items:
                        m_id = item.get("id") or item.get("fi") or item.get("room_id")
                        if m_id and m_id not in all_matches_dict:
                            all_matches_dict[m_id] = item
            except Exception:
                pass

    # 2. Quét HTML dự phòng từ giovang.rent
    html_content = fetch_data("https://giovang.rent/")
    if html_content:
        json_matches = re.findall(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            html_content,
            re.DOTALL,
        )
        if json_matches:
            try:
                data = json.loads(json_matches[0])
                page_props = (
                    data.get("props", {}).get("pageProps", {}).get("matches", [])
                )
                for item in page_props:
                    m_id = item.get("id") or item.get("fi") or item.get("room_id")
                    if m_id and m_id not in all_matches_dict:
                        all_matches_dict[m_id] = item
            except Exception:
                pass

    # 3. Lọc bỏ các trận đã hoàn tất
    valid_matches = []
    for m_id, match in all_matches_dict.items():
        status_code = str(match.get("status_code", "")).upper()
        status_str = str(match.get("status", "")).upper()

        if (
            status_code in ["FINISHED", "FT", "ENDED", "CANCELLED"]
            or "KẾT THÚC" in status_str
        ):
            continue
        valid_matches.append(match)

    # 4. Sắp xếp ưu tiên: Môn thể thao -> Trận LIVE -> Thời gian
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
        ts = m.get("time_start") or 0
        return (sport_prio, is_live, ts)

    valid_matches.sort(key=sort_key)

    m3u_lines = ["#EXTM3U"]

    # 5. Xuất danh sách M3U chuẩn
    for match in valid_matches:
        sport_type = match.get("type", "")
        league_title = match.get("league", {}).get("title", "")

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
        blv_str = f" ({', '.join(blv_list)})" if blv_list else ""

        stream_url = resolve_stream_url(match)

        # Định dạng tên rút gọn: [22:00 01/10] U21 Hy Lạp vs U21 Latvia (BLV Hấu) [HD1]
        title = f"[{time_str}] {home_name} vs {away_name}{blv_str} [HD1]"

        m3u_lines.append(
            f'#EXTINF:-1 tvg-logo="{home_logo}"'
            f' group-title="{group_title}", {title}'
        )
        m3u_lines.append(stream_url)

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(
        f"==> Hoàn tất! Đã xuất {len(valid_matches)} trận đấu vào playlist.m3u"
    )


if __name__ == "__main__":
    main()
    
