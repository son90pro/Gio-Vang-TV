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

NO_SIGNAL_URL = "https://freem3u.xyz/static/no-signal/low.m3u8"

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
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        return None


def get_direct_stream_urls(match, match_id):
    """Bóc tách luồng trực tiếp hoặc tự động tạo URL CDN vcdn.cloud"""
    streams = []

    # 1. Kiểm tra trực tiếp trong object match nếu API cấp sẵn
    links = match.get("links") or match.get("play_urls") or []
    if isinstance(links, list):
        for idx, item in enumerate(links):
            if isinstance(item, dict):
                q_name = item.get("name") or item.get("quality") or f"HD{idx+1}"
                s_url = item.get("url") or item.get("link") or item.get("m3u8")
                if s_url and "http" in s_url:
                    streams.append((q_name, s_url))
            elif isinstance(item, str) and "http" in item:
                streams.append((f"HD{idx+1}", item))

    if not streams and match.get("play_url"):
        p_url = match["play_url"]
        if "http" in p_url:
            streams.append(("FHD", p_url))

    # 2. Lấy dữ liệu từ Detail API nếu chưa có
    if not streams:
        detail_url = (
            f"https://live-api.keonhacaitp.one/storage/livestream/detail/{match_id}.json"
        )
        raw = fetch_data(detail_url)
        if raw:
            try:
                data = json.loads(raw)
                if data and data.get("code") == 0:
                    resp = data.get("response", {})
                    if isinstance(resp, dict):
                        d_links = (
                            resp.get("links") or resp.get("play_urls") or []
                        )
                        if isinstance(d_links, list):
                            for idx, item in enumerate(d_links):
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

    # 3. Tự động dựng đường dẫn CDN vcdn.cloud theo chuẩn Giờ Vàng TV nếu chưa có luồng
    if not streams and match_id:
        clean_id = str(match_id).strip()
        if clean_id.isdigit():
            vcdn_url = f"https://ftlh5sc02iliv.vcdn.cloud/{clean_id}_hd/{clean_id}_hd@720p.m3u8"
            streams.append(("HD1", vcdn_url))

    return streams


def main():
    now_vn = datetime.datetime.now(TZ_VN)
    tomorrow_vn = now_vn + datetime.timedelta(days=1)

    d_today_1 = now_vn.strftime("%d-%m-%Y")
    d_today_2 = now_vn.strftime("%Y-%m-%d")
    d_tom_1 = tomorrow_vn.strftime("%d-%m-%Y")
    d_tom_2 = tomorrow_vn.strftime("%Y-%m-%d")

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

    for match in valid_matches:
        match_id = match.get("id") or match.get("fi")
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

        streams = get_direct_stream_urls(match, match_id)

        if not streams:
            streams.append(("HD1", NO_SIGNAL_URL))

        for quality, stream_url in streams:
            title = (
                f"[{time_str}] {home_name} vs {away_name}{blv_str} [{quality}]"
            )

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
    
