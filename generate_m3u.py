import datetime
import json
import time
import urllib.error
import urllib.request
import zoneinfo

# Múi giờ Việt Nam (GMT+7)
TZ_VN = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")

# Các API dữ liệu của hệ thống Giờ Vàng
API_BASE = "https://live-api.keonhacaitp.one/storage/livestream"
ENDPOINTS = [
    f"{API_BASE}/live.json",
    f"{API_BASE}/schedule.json",
    f"{API_BASE}/today.json",
]

# User-Agent & Referer bắt buộc để bypass chống xem lén của server
REFERER_URL = "https://giovang.rent/"
USER_AGENT = (
    "Mozilla/5.0 (Android 16; Mobile; rv:156.0) Gecko/156.0 Firefox/156.0"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": REFERER_URL,
    "Accept": "application/json, text/plain, */*",
}

# Thứ tự ưu tiên hiển thị Môn Thể Thao
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
            "fc ",
        ]
    ):
        return (1, "Bóng Đá")
    if any(k in combined for k in ["bóng chuyền", "volleyball", "asiad"]):
        return (2, "Bóng Chuyền")
    if any(k in combined for k in ["bóng rổ", "basketball", "nba"]):
        return (3, "Bóng Rổ")
    if any(k in combined for k in ["tennis", "quần vợt", "atp", "wta"]):
        return (4, "Quần Vợt")
    if any(k in combined for k in ["esport", "valorant", "lol", "dota", "vct"]):
        return (5, "Esports")

    return (99, "Thể Thao Khác")


def fetch_json(url):
    sep = "&" if "?" in url else "?"
    full_url = f"{url}{sep}t={int(time.time())}"
    req = urllib.request.Request(full_url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Lỗi tải {url}: {e}")
        return None


def get_direct_stream_urls(match_id):
    """Bóc tách luồng .m3u8 trực tiếp từ Detail API"""
    detail_url = f"{API_BASE}/detail/{match_id}.json"
    data = fetch_json(detail_url)

    streams = []
    if data and isinstance(data, dict) and data.get("code") == 0:
        resp = data.get("response", {})
        if isinstance(resp, dict):
            # Lấy danh sách link phát
            links = resp.get("links") or resp.get("play_urls") or []
            if isinstance(links, list) and len(links) > 0:
                for idx, item in enumerate(links):
                    if isinstance(item, dict):
                        q_name = (
                            item.get("name")
                            or item.get("quality")
                            or f"HD{idx+1}"
                        )
                        s_url = (
                            item.get("url")
                            or item.get("link")
                            or item.get("m3u8")
                        )
                        if s_url and ("http" in s_url):
                            streams.append((q_name, s_url))
                    elif isinstance(item, str) and "http" in item:
                        streams.append((f"HD{idx+1}", item))

            # Nếu có single play_url
            if not streams and resp.get("play_url"):
                streams.append(("FHD", resp["play_url"]))

    return streams


def main():
    now_vn = datetime.datetime.now(TZ_VN)

    # Khởi tạo mốc thời gian: Từ 00:00 hôm nay đến 23:59 ngày mai
    today_start = now_vn.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = (today_start + datetime.timedelta(days=2)) - datetime.timedelta(
        seconds=1
    )

    start_ts = int(today_start.timestamp())
    end_ts = int(tomorrow_end.timestamp())

    print(
        f"Đang quét trận đấu từ {today_start.strftime('%d/%m/%Y')} đến"
        f" {tomorrow_end.strftime('%d/%m/%Y')}..."
    )

    all_matches = {}

    # 1. Gom tất cả các trận từ các API
    for ep in ENDPOINTS:
        res = fetch_json(ep)
        if res and isinstance(res, dict):
            items = res.get("response") or res.get("data") or []
            if isinstance(items, list):
                for item in items:
                    m_id = item.get("id") or item.get("fi")
                    if m_id and m_id not in all_matches:
                        all_matches[m_id] = item

    print(f"Tổng số trận quét được từ hệ thống: {len(all_matches)}")

    # 2. Lọc danh sách trận đấu hôm nay & ngày mai
    valid_matches = []
    for m_id, match in all_matches.items():
        ts = match.get("time_start") or 0
        status_code = str(match.get("status_code", "")).upper()
        is_live = match.get("is_live", False) or status_code == "LIVE"

        # Bỏ qua trận đã kết thúc
        if status_code in ["FINISHED", "FT", "ENDED", "CANCELLED"]:
            continue

        # Giữ lại trận đang LIVE hoặc thuộc khoảng thời gian Hôm nay & Ngày mai
        if is_live or (start_ts <= ts <= end_ts) or (ts == 0):
            valid_matches.append(match)

    # 3. Sắp xếp ưu tiên: Môn thể thao -> Trận LIVE lên đầu -> Thời gian tăng dần
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

    # 4. Xuất danh sách ra định dạng M3U chuẩn IPTV
    for match in valid_matches:
        match_id = match.get("id") or match.get("fi")
        sport_type = match.get("type", "")
        league_title = match.get("league", {}).get("title", "Giải đấu")

        teams = match.get("teams", {})
        home_name = teams.get("home", {}).get("name", "Đội nhà").strip()
        away_name = teams.get("away", {}).get("name", "Đội khách").strip()
        home_logo = teams.get("home", {}).get("logo", "")

        prio, group_title = detect_sport(sport_type, league_title, home_name)

        # Lấy thời gian GMT+7
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

        is_live = match.get("is_live") or (
            str(match.get("status_code")).upper() == "LIVE"
        )
        status_tag = "LIVE" if is_live else "Sắp diễn ra"

        # Lấy link m3u8 thực tế từ Detail API
        streams = get_direct_stream_urls(match_id)

        # Nếu chưa tới giờ đá hoặc chưa có stream m3u8, gắn luồng dự phòng
        if not streams:
            streams.append(
                ("HD1", f"https://live-api.keonhacaitp.one/live/{match_id}.m3u8")
            )

        for quality, raw_url in streams:
            title = f"[{time_str}] {home_name} vs {away_name} ({league_title}){blv_str} - [{status_tag}] [{quality}]"

            # Cấu hình Header giải mã dành riêng cho TiviMate & các ứng dụng IPTV
            m3u_lines.append(
                f'#EXTINF:-1 tvg-logo="{home_logo}"'
                f' group-title="{group_title}",{title}'
            )
            m3u_lines.append(f"#EXTVLCOPT:http-referrer={REFERER_URL}")
            m3u_lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")

            # Thêm pipe format cho IPTV Players: url|Referer=...&User-Agent=...
            formatted_url = f"{raw_url}|Referer={REFERER_URL}&User-Agent={urllib.parse.quote(USER_AGENT)}"
            m3u_lines.append(formatted_url)

    # Ghi file
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(
        f"==> Hoàn tất! Đã cập nhật {len(valid_matches)} trận đấu hôm nay &"
        " ngày mai vào playlist.m3u"
    )


if __name__ == "__main__":
    main()
    
