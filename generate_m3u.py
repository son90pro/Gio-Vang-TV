import datetime
import json
import re
import time
import urllib.error
import urllib.request
import zoneinfo
from concurrent.futures import ThreadPoolExecutor, as_completed

# Múi giờ Việt Nam (GMT+7)
TZ_VN = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Android 16; Mobile; rv:156.0) Gecko/156.0 Firefox/156.0"
    ),
    "Referer": "https://giovang.rent/",
    "Accept": "application/json, text/plain, */*",
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
        with urllib.request.urlopen(req, timeout=6) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        return None


def fetch_detail(match_id):
    url = f"https://live-api.keonhacaitp.one/storage/livestream/detail/{match_id}.json"
    raw = fetch_data(url)
    return match_id, raw


def extract_stream_url(match, detail_raw=None):
    """
    Trích xuất link vcdn.cloud hoặc .m3u8 thực tế từ Detail API.
    Nếu chưa có tín hiệu, trả về link no-signal chuẩn của Giờ Vàng TV.
    """
    # 1. Tìm room_id hoặc link trực tiếp trong dữ liệu Detail API
    if detail_raw:
        # Regex tìm trực tiếp link .m3u8 trong phản hồi
        m3u8_matches = re.findall(r'https?://[^\s"\'\>]+?\.m3u8', detail_raw)
        for m_url in m3u8_matches:
            if "no-signal" not in m_url:
                return m_url

        try:
            data = json.loads(detail_raw)
            resp = data.get("response") or data.get("data") or data
            if isinstance(resp, dict):
                # Kiểm tra thuộc tính play_url
                p_url = (
                    resp.get("play_url")
                    or resp.get("stream_url")
                    or resp.get("link")
                )
                if p_url and "http" in str(p_url) and "no-signal" not in str(p_url):
                    return str(p_url)

                # Kiểm tra danh sách links
                links = (
                    resp.get("links")
                    or resp.get("play_urls")
                    or resp.get("servers")
                    or []
                )
                if isinstance(links, list):
                    for l in links:
                        if isinstance(l, dict):
                            u = l.get("url") or l.get("link") or l.get("m3u8")
                            if u and "http" in str(u) and "no-signal" not in str(u):
                                return str(u)
                        elif isinstance(l, str) and "http" in l and "no-signal" not in l:
                            return l

                # Trích xuất room_id dạng số (ví dụ: 1790862754)
                for k in [
                    "room_id",
                    "stream_id",
                    "live_id",
                    "room_num",
                    "room",
                    "fi_id",
                    "id",
                ]:
                    val = resp.get(k)
                    if val and str(val).isdigit() and len(str(val)) >= 6:
                        room_id = str(val).strip()
                        return f"https://ftlh5sc02iliv.vcdn.cloud/{room_id}_hd/{room_id}_hd@720p.m3u8"
        except Exception:
            pass

    # 2. Kiểm tra thuộc tính room_id từ chính match object
    for k in ["room_id", "stream_id", "live_id", "room"]:
        val = match.get(k)
        if val and str(val).isdigit() and len(str(val)) >= 6:
            room_id = str(val).strip()
            return f"https://ftlh5sc02iliv.vcdn.cloud/{room_id}_hd/{room_id}_hd@720p.m3u8"

    # 3. Luồng mặc định khi chưa có tín hiệu phát trực tiếp
    return "https://freem3u.xyz/static/no-signal/low.m3u8"


def main():
    now_vn = datetime.datetime.now(TZ_VN)
    tomorrow_vn = now_vn + datetime.timedelta(days=1)
    yesterday_vn = now_vn - datetime.timedelta(days=1)

    d_today_1 = now_vn.strftime("%d-%m-%Y")
    d_today_2 = now_vn.strftime("%Y-%m-%d")
    d_tom_1 = tomorrow_vn.strftime("%d-%m-%Y")
    d_tom_2 = tomorrow_vn.strftime("%Y-%m-%d")
    d_yes_1 = yesterday_vn.strftime("%d-%m-%Y")
    d_yes_2 = yesterday_vn.strftime("%Y-%m-%d")

    # Quét tất cả nguồn API chứa trận đấu Đang diễn ra & Sắp diễn ra
    api_sources = [
        "https://live-api.keonhacaitp.one/storage/livestream/live.json",
        "https://live-api.keonhacaitp.one/storage/livestream/home.json",
        "https://live-api.keonhacaitp.one/storage/livestream/match.json",
        "https://live-api.keonhacaitp.one/storage/livestream/schedule.json",
        f"https://live-api.keonhacaitp.one/storage/livestream/date/{d_today_1}.json",
        f"https://live-api.keonhacaitp.one/storage/livestream/date/{d_tom_1}.json",
        f"https://live-api.keonhacaitp.one/storage/livestream/date/{d_yes_1}.json",
        f"https://live-api.keonhacaitp.one/storage/livestream/date/{d_today_2}.json",
        f"https://live-api.keonhacaitp.one/storage/livestream/date/{d_tom_2}.json",
        f"https://live-api.keonhacaitp.one/storage/livestream/date/{d_yes_2}.json",
    ]

    all_matches_dict = {}

    # 1. Tải danh sách trận đấu song song (Multi-threading)
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {
            executor.submit(fetch_data, url): url for url in api_sources
        }
        for future in as_completed(future_to_url):
            raw_text = future.result()
            if raw_text:
                try:
                    data = json.loads(raw_text)
                    items = data.get("response") or data.get("data") or []
                    if isinstance(items, list):
                        for item in items:
                            m_id = (
                                item.get("id")
                                or item.get("fi")
                                or item.get("room_id")
                            )
                            if m_id and m_id not in all_matches_dict:
                                all_matches_dict[m_id] = item
                except Exception:
                    pass

    # 2. Bổ sung dữ liệu từ trang chủ giovang.rent
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

    # 3. Lọc danh sách: Giữ lại trận Đang diễn ra & Sắp diễn ra (Loại bỏ trận Đã kết thúc)
    valid_matches = []
    for m_id, match in all_matches_dict.items():
        status_code = str(match.get("status_code", "")).upper()
        status_str = str(match.get("status", "")).upper()

        if (
            status_code in ["FINISHED", "FT", "ENDED", "CANCELLED"]
            or "KẾT THÚC" in status_str
            or "ĐÃ HỦY" in status_str
        ):
            continue
        valid_matches.append(match)

    # 4. Truy vấn đồng thời Detail API để lấy ID luồng phát trực tiếp
    detail_results = {}
    match_ids = [
        (m.get("id") or m.get("fi"))
        for m in valid_matches
        if (m.get("id") or m.get("fi"))
    ]

    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_id = {
            executor.submit(fetch_detail, mid): mid for mid in match_ids
        }
        for future in as_completed(future_to_id):
            mid, raw = future.result()
            if raw:
                detail_results[mid] = raw

    # 5. Sắp xếp danh sách: Môn thể thao -> Trận LIVE lên trước -> Thời gian
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

    # 6. Xuất playlist M3U
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

        m_id = match.get("id") or match.get("fi")
        detail_raw = detail_results.get(m_id)

        stream_url = extract_stream_url(match, detail_raw)

        is_live_match = (
            match.get("is_live")
            or str(match.get("status_code")).upper() == "LIVE"
        )
        status_icon = "🟢 " if is_live_match else "🟡 "

        # Định dạng tiêu đề: 🟢 [22:00 01/10] U21 Hy Lạp vs U21 Latvia (BLV Hấu) [HD1]
        title = (
            f"{status_icon}[{time_str}] {home_name} vs {away_name}{blv_str} [HD1]"
        )

        m3u_lines.append(
            f'#EXTINF:-1 tvg-logo="{home_logo}"'
            f' group-title="{group_title}", {title}'
        )
        m3u_lines.append(stream_url)

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(
        f"==> Thành công! Đã xuất {len(valid_matches)} trận đấu vào playlist.m3u"
    )


if __name__ == "__main__":
    main()
