import datetime
import json
import time
import urllib.error
import urllib.request
import zoneinfo

# Múi giờ Việt Nam
TZ_VN = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")

# Base API
API_BASE = "https://live-api.keonhacaitp.one/storage/livestream"

# Headers giả lập Browser
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Android 16; Mobile; rv:156.0) Gecko/156.0 Firefox/156.0"
    ),
    "Referer": "https://giovang.rent/",
    "Accept": "application/json, text/plain, */*",
}

# Bản đồ phân loại môn thể thao & Thứ tự ưu tiên
SPORT_MAP = {
    # 1. Bóng đá (Ưu tiên số 1)
    "football": (1, "Bóng Đá"),
    "soccer": (1, "Bóng Đá"),
    "bongda": (1, "Bóng Đá"),
    "bong-da": (1, "Bóng Đá"),
    "fb": (1, "Bóng Đá"),
    # 2. Bóng chuyền (Ưu tiên số 2)
    "bongchuyen": (2, "Bóng Chuyền"),
    "volleyball": (2, "Bóng Chuyền"),
    "bong-chuyen": (2, "Bóng Chuyền"),
    "vb": (2, "Bóng Chuyền"),
    # 3. Bóng rổ
    "basketball": (3, "Bóng Rổ"),
    "bongro": (3, "Bóng Rổ"),
    "bong-ro": (3, "Bóng Rổ"),
    "bb": (3, "Bóng Rổ"),
    # 4. Quần vợt
    "tennis": (4, "Quần Vợt"),
    "quanvot": (4, "Quần Vợt"),
    "quan-vot": (4, "Quần Vợt"),
    # 5. Esports
    "esport": (5, "Esports"),
    "esports": (5, "Esports"),
    "e-sports": (5, "Esports"),
    # 6. Bóng bàn
    "bongban": (6, "Bóng Bàn"),
    "tabletennis": (6, "Bóng Bàn"),
    "table-tennis": (6, "Bóng Bàn"),
}


def detect_sport(sport_type, league_name="", team_name=""):
    """Nhận diện môn thể thao kể cả khi API trả về type lạ/trống"""
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
            "serie a",
            "la liga",
            "bundesliga",
            "fc ",
            "united",
        ]
    ):
        return (1, "Bóng Đá")
    if any(k in combined for k in ["bóng chuyền", "volleyball"]):
        return (2, "Bóng Chuyền")
    if any(k in combined for k in ["bóng rổ", "basketball", "nba"]):
        return (3, "Bóng Rổ")
    if any(k in combined for k in ["tennis", "quần vợt", "atp", "wta", "open"]):
        return (4, "Quần Vợt")
    if any(
        k in combined
        for k in ["esport", "valorant", "lol", "dota", "csgo", "vct"]
    ):
        return (5, "Esports")

    return (99, "Thể Thao Khác")


def fetch_json(url):
    """Tải dữ liệu JSON và chống cache bằng Timestamp"""
    sep = "&" if "?" in url else "?"
    full_url = f"{url}{sep}t={int(time.time())}"
    req = urllib.request.Request(full_url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def main():
    now_vn = datetime.datetime.now(TZ_VN)

    # Tính mốc thời gian hôm nay và ngày mai (chuẩn múi giờ VN)
    today_iso = now_vn.strftime("%Y-%m-%d")
    tomorrow_vn = now_vn + datetime.timedelta(days=1)
    tomorrow_iso = tomorrow_vn.strftime("%Y-%m-%d")

    start_today_ts = int(
        now_vn.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    )
    end_tomorrow_ts = int(
        tomorrow_vn.replace(
            hour=23, minute=59, second=59, microsecond=0
        ).timestamp()
    )

    # Quét tất cả các endpoint có thể chứa danh sách trận đấu
    endpoints = [
        f"{API_BASE}/live.json",
        f"{API_BASE}/today.json",
        f"{API_BASE}/schedule.json",
        f"{API_BASE}/matches.json",
        f"{API_BASE}/date/{today_iso}.json",
        f"{API_BASE}/date/{tomorrow_iso}.json",
    ]

    all_matches_dict = {}

    for url in endpoints:
        res = fetch_json(url)
        if not res or not isinstance(res, dict):
            continue

        items = res.get("response") or res.get("data") or []
        if isinstance(items, list):
            for item in items:
                match_id = item.get("id") or item.get("fi")
                if match_id and match_id not in all_matches_dict:
                    all_matches_dict[match_id] = item

    print(f"Tổng số trận tìm thấy từ API: {len(all_matches_dict)}")

    # Lọc các trận hợp lệ (Đang Live + Sắp diễn ra trong hôm nay và ngày mai)
    valid_matches = []
    for match_id, match in all_matches_dict.items():
        time_start = match.get("time_start") or 0
        status_code = str(match.get("status_code", "")).upper()
        is_live = match.get("is_live", False) or status_code == "LIVE"

        # Bỏ qua trận đã kết thúc
        if status_code in ["FINISHED", "FT", "ENDED", "CANCELLED"]:
            continue

        # Giữ lại nếu đang LIVE hoặc trong khoảng thời gian Hôm nay -> Ngày mai
        if is_live or (start_today_ts <= time_start <= end_tomorrow_ts):
            valid_matches.append(match)

    # Sắp xếp ưu tiên:
    # 1. Môn thể thao (Bóng Đá -> Bóng Chuyền -> Bóng Rổ -> Quần Vợt...)
    # 2. Trạng thái Trận đấu (Trận LIVE lên đầu)
    # 3. Thời gian diễn ra (sớm lên trước)
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

        # Định dạng thời gian GMT+7
        ts = match.get("time_start")
        if ts:
            dt = datetime.datetime.fromtimestamp(ts, tz=TZ_VN)
            time_str = dt.strftime("%H:%M %d/%m")
        else:
            time_str = (
                f"{match.get('time', '')} {match.get('day_month', '')}".strip()
                or "N/A"
            )

        # Bình luận viên
        blv_list = match.get("blv", [])
        blv_str = f" [BLV: {', '.join(blv_list)}]" if blv_list else ""

        # Trạng thái
        status = match.get("status") or (
            "LIVE" if match.get("is_live") else "Sắp diễn ra"
        )

        # Lấy luồng phát chi tiết
        streams = []
        detail_url = f"{API_BASE}/detail/{match_id}.json"
        detail_res = fetch_json(detail_url)

        if (
            detail_res
            and isinstance(detail_res, dict)
            and detail_res.get("code") == 0
        ):
            resp_detail = detail_res.get("response", {})
            if isinstance(resp_detail, dict):
                links = (
                    resp_detail.get("links")
                    or resp_detail.get("play_urls")
                    or []
                )
                if isinstance(links, list) and len(links) > 0:
                    for idx, link_item in enumerate(links):
                        if isinstance(link_item, dict):
                            q_name = (
                                link_item.get("name")
                                or link_item.get("quality")
                                or f"HD{idx+1}"
                            )
                            s_url = (
                                link_item.get("url")
                                or link_item.get("link")
                                or link_item.get("m3u8")
                            )
                            if s_url:
                                streams.append((q_name, s_url))
                        elif isinstance(link_item, str):
                            streams.append((f"HD{idx+1}", link_item))
                elif resp_detail.get("play_url"):
                    streams.append(("FHD", resp_detail["play_url"]))

        # Fallback nếu không bóc tách được m3u8 trực tiếp
        if not streams:
            streams.append(
                ("Trực tiếp", f"https://giovang.rent/live/{match_id}")
            )

        # Thêm thông tin vào playlist M3U
        for quality, s_url in streams:
            title = f"[{time_str}] {home_name} vs {away_name} ({league_title}){blv_str} - [{status}] [{quality}]"
            extinf = f'#EXTINF:-1 tvg-logo="{home_logo}" group-title="{group_title}",{title}'
            m3u_lines.append(extinf)
            m3u_lines.append(s_url)

    # Xuất file M3U
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(
        f"Đã xuất thành công {len(valid_matches)} trận đấu hợp lệ vào playlist.m3u"
    )


if __name__ == "__main__":
    main()
    
