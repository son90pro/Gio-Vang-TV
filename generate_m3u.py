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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://giovang.rent",
    "Referer": "https://giovang.rent/",
}

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def get_sport_emoji(sport_type, league="", team=""):
    """Tự động phân loại icon môn thể thao chuẩn như mẫu M3U"""
    s = f"{sport_type} {league} {team}".lower()
    if any(
        k in s
        for k in [
            "basketball",
            "bóng rổ",
            "nba",
            "aces",
            "fever",
            "cbf9424df17d6e06d655dca78651d329",
        ]
    ):
        return "🏀"
    if any(k in s for k in ["volleyball", "bóng chuyền"]):
        return "🏐"
    if any(
        k in s
        for k in [
            "baseball",
            "bóng chày",
            "braves",
            "phillies",
            "IPmhSoEa-hvtJM6zJ",
        ]
    ):
        return "⚾"
    if any(
        k in s
        for k in [
            "tennis",
            "quần vợt",
            "softball",
            "beijing open",
            "open vs",
            "wta",
            "atp",
        ]
    ):
        return "🥎"
    if any(
        k in s
        for k in [
            "esport",
            "esports",
            "lol",
            "dota",
            "valorant",
            "đài bắc",
            "edg",
            "global esports",
        ]
    ):
        return "🎮"
    if any(k in s for k in ["billiards", "bida", "pool", "men vs", "spain man"]):
        return "🎱"
    if any(
        k in s
        for k in [
            "f1",
            "formula1",
            "grand prix",
            "bahrain",
            "gulf air",
            "formula 1",
        ]
    ):
        return "🏎️"
    if any(
        k in s
        for k in [
            "american football",
            "nfl",
            "steelers",
            "browns",
            "pittburgh",
            "cleveland",
        ]
    ):
        return "🏈"
    return "⚽"


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
    except Exception:
        pass
    return None


def extract_room_id(match):
    """Bắt chính xác room_id từ mọi cấu trúc JSON của Giờ Vàng"""
    match_str = json.dumps(match)

    for key in [
        "room_id",
        "room_num",
        "live_id",
        "stream_id",
        "room",
        "id",
        "match_id",
    ]:
        val = match.get(key)
        if val and str(val).isdigit() and len(str(val)) >= 6:
            return str(val).strip()

    for sub_key in ["servers", "channels", "links", "sources", "streams"]:
        sub_list = match.get(sub_key)
        if isinstance(sub_list, list):
            for item in sub_list:
                if isinstance(item, dict):
                    for k in ["room_id", "id", "stream_id", "live_id", "room"]:
                        v = item.get(k)
                        if v and str(v).isdigit() and len(str(v)) >= 6:
                            return str(v).strip()

    room_matches = re.findall(
        r'"(?:room_id|stream_id|live_id|room_num|room)"\s*:\s*"?(\d{6,11})"?',
        match_str,
    )
    if room_matches:
        return room_matches[0]

    return None


def extract_stream_link(match):
    """Trích xuất luồng vcdn trực tiếp hoặc no-signal chuẩn"""
    status_code = str(match.get("status_code", "")).upper()
    status_str = str(match.get("status", "")).upper()
    is_live = (
        match.get("is_live") == 1
        or match.get("is_live") is True
        if "is_live" in match
        else False
    )

    room_id = extract_room_id(match)

    # Nếu trận đấu đang LIVE hoặc có room_id phát trực tiếp
    if (
        is_live or status_code in ["LIVE", "1"] or "ĐANG LIVE" in status_str
    ) and room_id:
        return f"https://ftlh5sc02iliv.vcdn.cloud/{room_id}_hd/{room_id}_hd@720p.m3u8"

    if room_id and is_live:
        return f"https://ftlh5sc02iliv.vcdn.cloud/{room_id}_hd/{room_id}_hd@720p.m3u8"

    # Trận chưa diễn ra
    return "https://freem3u.xyz/static/no-signal/low.m3u8"


def extract_matches_from_html(html_content):
    matches = []
    if not html_content:
        return matches

    json_matches = re.findall(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html_content,
        re.DOTALL,
    )
    if json_matches:
        try:
            data = json.loads(json_matches[0])
            page_props = data.get("props", {}).get("pageProps", {})

            for key in [
                "matches",
                "schedules",
                "liveMatches",
                "homeData",
                "scheduleData",
                "allMatches",
                "data",
                "list",
            ]:
                val = page_props.get(key, [])
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            matches.append(item)
                elif isinstance(val, dict):
                    for sub_k in ["matches", "items", "rows", "list"]:
                        sub_v = val.get(sub_k, [])
                        if isinstance(sub_v, list):
                            for item in sub_v:
                                if isinstance(item, dict):
                                    matches.append(item)
        except Exception:
            pass
    return matches


def main():
    now_vn = datetime.datetime.now(TZ_VN)

    api_sources = [
        "https://live-api.keonhacaitp.one/storage/livestream/home.json",
        "https://live-api.keonhacaitp.one/storage/livestream/match.json",
        "https://live-api.keonhacaitp.one/storage/livestream/schedule.json",
        "https://live-api.keonhacaitp.one/storage/livestream/live.json",
    ]

    for i in range(-1, 3):
        day = now_vn + datetime.timedelta(days=i)
        d1 = day.strftime("%d-%m-%Y")
        d2 = day.strftime("%Y-%m-%d")
        api_sources.append(
            f"https://live-api.keonhacaitp.one/storage/livestream/date/{d1}.json"
        )
        api_sources.append(
            f"https://live-api.keonhacaitp.one/storage/livestream/date/{d2}.json"
        )

    web_sources = [
        "https://giovang.rent/",
        "https://giovang.rent/lich-thi-dau",
        "https://giovang.city/",
    ]

    all_matches_dict = {}

    # 1. Cào API
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
                                    or item.get("slug")
                                )
                                if m_id and m_id not in all_matches_dict:
                                    all_matches_dict[m_id] = item
                except Exception:
                    pass

    # 2. Cào Trang chủ HTML Giờ Vàng
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {
            executor.submit(fetch_url, url): url for url in web_sources
        }
        for future in as_completed(future_to_url):
            html_text = future.result()
            if html_text:
                extracted = extract_matches_from_html(html_text)
                for item in extracted:
                    m_id = (
                        item.get("id")
                        or item.get("fi")
                        or item.get("room_id")
                        or item.get("slug")
                    )
                    if m_id and m_id not in all_matches_dict:
                        all_matches_dict[m_id] = item

    # 3. Lọc lấy các trận đang và sắp diễn ra
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

    def sort_key(m):
        is_live = (
            0
            if (m.get("is_live") or str(m.get("status_code")).upper() == "LIVE")
            else 1
        )
        ts = m.get("time_start") or 0
        return (is_live, ts)

    valid_matches.sort(key=sort_key)

    m3u_lines = ["#EXTM3U\n"]

    for match in valid_matches:
        teams = match.get("teams") if isinstance(match.get("teams"), dict) else {}
        home_name = (
            teams.get("home", {}).get("name", "").strip()
            if isinstance(teams.get("home"), dict)
            else ""
        )
        away_name = (
            teams.get("away", {}).get("name", "").strip()
            if isinstance(teams.get("away"), dict)
            else ""
        )

        if not home_name and not away_name:
            match_name = match.get("title") or match.get("name") or "Trận đấu"
        else:
            match_name = f"{home_name} vs {away_name}"

        logo = ""
        if isinstance(teams.get("home"), dict) and teams.get("home", {}).get(
            "logo"
        ):
            logo = teams["home"]["logo"]
        elif isinstance(match.get("league"), dict) and match.get(
            "league", {}
        ).get("logo"):
            logo = match["league"]["logo"]

        ts = match.get("time_start")
        if ts:
            try:
                dt = datetime.datetime.fromtimestamp(int(ts), tz=TZ_VN)
                time_str = dt.strftime("%H:%M %d/%m")
            except Exception:
                time_str = now_vn.strftime("%H:%M %d/%m")
        else:
            time_str = (
                f"{match.get('time', '')} {match.get('day_month', '')}".strip()
                or now_vn.strftime("%H:%M %d/%m")
            )

        blv_list = match.get("blv", [])
        if isinstance(blv_list, list) and blv_list:
            blv_str = f" ({', '.join(blv_list)})"
        elif isinstance(blv_list, str) and blv_list:
            blv_str = f" ({blv_list})"
        else:
            blv_str = ""

        sport_type = match.get("type") or match.get("sport_type") or ""
        league_title = (
            match.get("league", {}).get("title", "")
            if isinstance(match.get("league"), dict)
            else ""
        )
        emoji = get_sport_emoji(sport_type, league_title, match_name)

        stream_url = extract_stream_link(match)
        is_no_signal = "no-signal" in stream_url

        if not is_no_signal:
            status_icon = "🟢 "
        else:
            status_icon = "🟡 " if "07:00" in time_str or "05:00" in time_str else ""

        title = f"{status_icon}{time_str} {emoji} {match_name}{blv_str} [hls]"

        m3u_lines.append(
            f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV" , {title}'
        )
        m3u_lines.append(stream_url)
        m3u_lines.append("")

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(
        f"Hoàn tất! Đã tạo playlist.m3u chuẩn với {len(valid_matches)} trận"
        " đấu.",
        flush=True,
    )


if __name__ == "__main__":
    main()
    
