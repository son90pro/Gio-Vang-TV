import datetime
import json
import re
import ssl
import time
import urllib.error
import urllib.request
import zoneinfo
from concurrent.futures import ThreadPoolExecutor, as_completed

# Múi giờ Việt Nam (GMT+7)
TZ_VN = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")

# Giả lập Header trình duyệt thực tế để tránh Cloudflare chặn IP Runner
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://giovang.rent",
    "Referer": "https://giovang.rent/",
    "Sec-Ch-Ua": (
        '"Chromium";v="128", "Not=A?Brand";v="24", "Google Chrome";v="128"'
    ),
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}

# Tạo SSL Context bỏ qua kiểm tra chứng chỉ (tránh lỗi trên GitHub Runner)
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

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
    if any(k in combined for k in ["bóng rổ", "basketball", "nba", "euro"]):
        return (3, "Bóng Rổ")
    if any(k in combined for k in ["tennis", "quần vợt", "atp", "wta", "open"]):
        return (4, "Quần Vợt")
    if any(k in combined for k in ["esport", "valorant", "lol", "dota", "vct"]):
        return (5, "Esports")

    return (99, "Thể Thao Khác")


def fetch_url(url, timeout=12):
    sep = "&" if "?" in url else "?"
    full_url = f"{url}{sep}t={int(time.time())}"
    req = urllib.request.Request(full_url, headers=HEADERS)
    try:
        with urllib.request.urlopen(
            req, timeout=timeout, context=SSL_CTX
        ) as resp:
            if resp.status == 200:
                text = resp.read().decode("utf-8", errors="ignore")
                return text.replace("\\/", "/")
    except urllib.error.HTTPError as e:
        print(f"  [!] HTTP {e.code} cho URL: {url}", flush=True)
    except Exception as e:
        print(f"  [!] Lỗi kết nối ({type(e).__name__}) cho URL: {url}", flush=True)
    return None


def fetch_detail_api(match_id):
    url = f"https://live-api.keonhacaitp.one/storage/livestream/detail/{match_id}.json"
    raw = fetch_url(url, timeout=10)
    return match_id, raw


def extract_stream_link(match, detail_raw=None):
    if detail_raw:
        m3u8_matches = re.findall(r'https?://[^\s"\'\>]+?\.m3u8', detail_raw)
        for m_url in m3u8_matches:
            if "no-signal" not in m_url:
                return m_url

        try:
            data = json.loads(detail_raw)
            resp = data.get("response") or data.get("data") or data
            if isinstance(resp, dict):
                p_url = (
                    resp.get("play_url")
                    or resp.get("stream_url")
                    or resp.get("link")
                )
                if (
                    p_url
                    and "http" in str(p_url)
                    and "no-signal" not in str(p_url)
                ):
                    return str(p_url)

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
                            if (
                                u
                                and "http" in str(u)
                                and "no-signal" not in str(u)
                            ):
                                return str(u)
                        elif (
                            isinstance(l, str)
                            and "http" in l
                            and "no-signal" not in l
                        ):
                            return l

                for k in [
                    "room_id",
                    "stream_id",
                    "live_id",
                    "room_num",
                    "room",
                    "id",
                ]:
                    v = resp.get(k)
                    if v and str(v).isdigit() and len(str(v)) >= 6:
                        rid = str(v).strip()
                        return f"https://ftlh5sc02iliv.vcdn.cloud/{rid}_hd/{rid}_hd@720p.m3u8"
        except Exception:
            pass

    for k in ["room_id", "stream_id", "live_id", "room"]:
        v = match.get(k)
        if v and str(v).isdigit() and len(str(v)) >= 6:
            rid = str(v).strip()
            return f"https://ftlh5sc02iliv.vcdn.cloud/{rid}_hd/{rid}_hd@720p.m3u8"

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

    print("[1/5] Đang quét dữ liệu từ các API nguồn...", flush=True)
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {
            executor.submit(fetch_url, url): url for url in api_sources
        }
        for future in as_completed(future_to_url):
            raw_text = future.result()
            if raw_text:
                try:
                    data = json.loads(raw_text)
                    items = (
                        data.get("response")
                        or data.get("data")
                        or (data if isinstance(data, list) else [])
                    )
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict):
                                m_id = (
                                    item.get("id")
                                    or item.get("fi")
                                    or item.get("room_id")
                                )
                                if m_id and m_id not in all_matches_dict:
                                    all_matches_dict[m_id] = item
                except Exception as e:
                    print(f"  [!] Lỗi parse JSON từ API: {e}", flush=True)

    print("[2/5] Đang cào dữ liệu từ Giovang.rent...", flush=True)
    html_content = fetch_url("https://giovang.rent/", timeout=15)
    if html_content:
        json_matches = re.findall(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            html_content,
            re.DOTALL,
        )
        if json_matches:
            try:
                data = json.loads(json_matches[0])
                page_props = data.get("props", {}).get("pageProps", {})

                candidates = []
                for key in ["matches", "schedules", "liveMatches", "homeData"]:
                    val = page_props.get(key, [])
                    if isinstance(val, list):
                        candidates.extend(val)

                for item in candidates:
                    if isinstance(item, dict):
                        m_id = (
                            item.get("id")
                            or item.get("fi")
                            or item.get("room_id")
                        )
                        if m_id and m_id not in all_matches_dict:
                            all_matches_dict[m_id] = item
            except Exception as e:
                print(f"  [!] Lỗi parse __NEXT_DATA__: {e}", flush=True)

    print(f"--> Tổng số trận cào được: {len(all_matches_dict)}", flush=True)

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

    print(
        f"[3/5] Đã lọc còn {len(valid_matches)} trận đang & sắp diễn ra.",
        flush=True,
    )

    print("[4/5] Đang giải mã luồng video trực tiếp...", flush=True)
    detail_results = {}
    match_ids = [
        (m.get("id") or m.get("fi"))
        for m in valid_matches
        if (m.get("id") or m.get("fi"))
    ]

    with ThreadPoolExecutor(max_workers=15) as executor:
        future_to_id = {
            executor.submit(fetch_detail_api, mid): mid for mid in match_ids
        }
        for future in as_completed(future_to_id):
            mid, raw = future.result()
            if raw:
                detail_results[mid] = raw

    def sort_key(m):
        sport_prio, _ = detect_sport(
            m.get("type", ""),
            m.get("league", {}).get("title", "")
            if isinstance(m.get("league"), dict)
            else "",
            m.get("teams", {}).get("home", {}).get("name", "")
            if isinstance(m.get("teams"), dict)
            else "",
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
    live_count = 0

    for match in valid_matches:
        sport_type = match.get("type", "")
        league_obj = match.get("league")
        league_title = (
            league_obj.get("title", "") if isinstance(league_obj, dict) else ""
        )

        teams = match.get("teams") if isinstance(match.get("teams"), dict) else {}
        home_name = (
            teams.get("home", {}).get("name", "Đội nhà").strip()
            if isinstance(teams.get("home"), dict)
            else "Đội nhà"
        )
        away_name = (
            teams.get("away", {}).get("name", "Đội khách").strip()
            if isinstance(teams.get("away"), dict)
            else "Đội khách"
        )
        home_logo = (
            teams.get("home", {}).get("logo", "")
            if isinstance(teams.get("home"), dict)
            else ""
        )

        prio, group_title = detect_sport(sport_type, league_title, home_name)

        ts = match.get("time_start")
        if ts:
            try:
                dt = datetime.datetime.fromtimestamp(int(ts), tz=TZ_VN)
                time_str = dt.strftime("%H:%M %d/%m")
            except Exception:
                time_str = "N/A"
        else:
            time_str = (
                f"{match.get('time', '')} {match.get('day_month', '')}".strip()
                or "N/A"
            )

        blv_list = match.get("blv", [])
        blv_str = (
            f" ({', '.join(blv_list)})"
            if (isinstance(blv_list, list) and blv_list)
            else ""
        )

        m_id = match.get("id") or match.get("fi")
        detail_raw = detail_results.get(m_id)

        stream_url = extract_stream_link(match, detail_raw)

        is_live_match = (
            match.get("is_live")
            or str(match.get("status_code")).upper() == "LIVE"
            or "no-signal" not in stream_url
        )

        if "no-signal" not in stream_url:
            live_count += 1

        status_icon = "🟢 " if is_live_match else "🟡 "
        title = f"{status_icon}[{time_str}] {home_name} vs {away_name}{blv_str} [HD1]"

        m3u_lines.append(
            f'#EXTINF:-1 tvg-logo="{home_logo}" group-title="{group_title}", {title}'
        )
        m3u_lines.append(stream_url)

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(
        f"[5/5] Hoàn tất! Đã cập nhật tổng cộng {len(valid_matches)} trận"
        f" ({live_count} trận có luồng video trực tiếp).",
        flush=True,
    )


if __name__ == "__main__":
    main()
    
