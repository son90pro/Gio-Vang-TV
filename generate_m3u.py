import datetime
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zoneinfo

# Múi giờ Việt Nam (GMT+7)
TZ_VN = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")

# Thông tin Request Header
REFERER_URL = "https://giovang.rent/"
USER_AGENT = (
    "Mozilla/5.0 (Android 16; Mobile; rv:156.0) Gecko/156.0 Firefox/156.0"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": REFERER_URL,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Phân loại & Thứ tự ưu tiên hiển thị Môn Thể Thao
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
        with urllib.request.urlopen(req, timeout=12) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        return None


def get_direct_stream_urls(match_id):
    """Lấy link .m3u8 trực tiếp từ Detail API"""
    detail_url = (
        f"https://live-api.keonhacaitp.one/storage/livestream/detail/{match_id}.json"
    )
    raw = fetch_data(detail_url)
    streams = []

    if raw:
        try:
            data = json.loads(raw)
            if data and data.get("code") == 0:
                resp = data.get("response", {})
                if isinstance(resp, dict):
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
                                if s_url and "http" in s_url:
                                    streams.append((q_name, s_url))
                            elif isinstance(item, str) and "http" in item:
                                streams.append((f"HD{idx+1}", item))

                    if not streams and resp.get("play_url"):
                        streams.append(("FHD", resp["play_url"]))
        except Exception:
            pass

    return streams


def main():
    now_vn = datetime.datetime.now(TZ_VN)
    tomorrow_vn = now_vn + datetime.timedelta(days=1)

    # Định dạng ngày phục vụ quét API
    d_today_1 = now_vn.strftime("%d-%m-%Y")  # 01-10-2026
    d_today_2 = now_vn.strftime("%Y-%m-%d")  # 2026-10-01
    d_tom_1 = tomorrow_vn.strftime("%d-%m-%Y")  # 02-10-2026
    d_tom_2 = tomorrow_vn.strftime("%Y-%m-%d")  # 2026-10-02

    # Danh sách tập hợp API quét toàn bộ lịch thi đấu
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

    # 1. Quét dữ liệu từ các API JSON
    for url in api_sources:
        raw_text = fetch_data(url)
        if raw_text:
            try:
                data = json.loads(raw_text)
                items = data.get("response") or data.get("data") or []
                if isinstance(items, list):
                    for item in items:
                        m_id = item.get("id") or item.get("fi")
                        if m_id and m_id not in all_matches_dict:
                            all_matches_dict[m_id] = item
            except Exception:
                pass

    # 2. Quét dự phòng trực tiếp từ HTML trang chủ giovang.rent
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
                    m_id = item.get("id") or item.get("fi")
                    if m_id and m_id not in all_matches_dict:
                        all_matches_dict[m_id] = item
            except Exception:
                pass

    print(f"Tổng số trận quét thành công: {len(all_matches_dict)}")

    # 3. Lọc trận đấu (Bỏ trận đã đá xong)
    valid_matches = []
    for m_id, match in all_matches_dict.items():
        status_code = str(match.get("status_code", "")).upper()
        status_str = str(match.get("status", "")).upper()

        # Bỏ qua trận đã kết thúc
        if (
            status_code in ["FINISHED", "FT", "ENDED", "CANCELLED"]
            or "KẾT THÚC" in status_str
        ):
            continue

        valid_matches.append(match)

    # 4. Sắp xếp ưu tiên:
    # Môn thể thao (Bóng Đá -> Bóng Chuyền -> Bóng Rổ...) -> Trận LIVE -> Thời gian
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

    # 5. Xuất danh sách M3U
    for match in valid_matches:
        match_id = match.get("id") or match.get("fi")
        sport_type = match.get("type", "")
        league_title = match.get("league", {}).get("title", "Giải đấu")

        teams = match.get("teams", {})
        home_name = teams.get("home", {}).get("name", "Đội nhà").strip()
        away_name = teams.get("away", {}).get("name", "Đội khách").strip()
        home_logo = teams.get("home", {}).get("logo", "")

        prio, group_title = detect_sport(sport_type, league_title, home_name)

        # Định dạng thời gian
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

        # Lấy link m3u8
        streams = get_direct_stream_urls(match_id)
        if not streams:
            streams.append(
                ("HD1", f"https://live-api.keonhacaitp.one/live/{match_id}.m3u8")
            )

        for quality, raw_url in streams:
            title = f"[{time_str}] {home_name} vs {away_name} ({league_title}){blv_str} - [{status_tag}] [{quality}]"

            m3u_lines.append(
                f'#EXTINF:-1 tvg-logo="{home_logo}"'
                f' group-title="{group_title}",{title}'
            )
            m3u_lines.append(f"#EXTVLCOPT:http-referrer={REFERER_URL}")
            m3u_lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")

            formatted_url = f"{raw_url}|Referer={REFERER_URL}&User-Agent={urllib.parse.quote(USER_AGENT)}"
            m3u_lines.append(formatted_url)

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(
        f"==> Hoàn tất! Đã xuất {len(valid_matches)} trận đấu (LIVE + Sắp diễn"
        " ra) vào playlist.m3u"
    )


if __name__ == "__main__":
    main()
    
