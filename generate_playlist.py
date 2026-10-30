import time
import requests
from datetime import datetime, timezone, timedelta

TZ_VN = timezone(timedelta(hours=7))

def fetch_and_generate_m3u():
    timestamp = int(time.time())
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://giovang.uno/"
    }

    # Các endpoint tiềm năng của API để gom cả trận live lẫn lịch thi đấu
    endpoints = [
        f"https://live-api.keonhacaitp.one/storage/livestream/live.json?t={timestamp}",
        f"https://live-api.keonhacaitp.one/storage/livestream/schedule.json?t={timestamp}",
        f"https://live-api.keonhacaitp.one/storage/livestream/fixtures.json?t={timestamp}",
        f"https://live-api.keonhacaitp.one/storage/livestream/matches.json?t={timestamp}"
    ]

    all_matches = []
    seen_ids = set()

    # Quét vét cạn các endpoint để lấy đầy đủ dữ liệu
    for url in endpoints:
        try:
            res = requests.get(url, headers=headers, timeout=8)
            if res.status_code == 200:
                data = res.json()
                matches = data.get("response", data) if isinstance(data, dict) else data
                if isinstance(matches, list):
                    for m in matches:
                        m_id = str(m.get("fi", m.get("id", "")))
                        if m_id and m_id not in seen_ids:
                            seen_ids.add(m_id)
                            all_matches.append(m)
        except Exception:
            continue

    # Xác định ngày hôm nay và ngày mai theo giờ Việt Nam
    now_vn = datetime.now(TZ_VN)
    current_date_str = now_vn.strftime("%d-%m-%Y") # Định dạng: DD-MM-YYYY (VD: 30-10-2026)
    tomorrow_vn = now_vn + timedelta(days=1)
    tomorrow_date_str = tomorrow_vn.strftime("%d-%m-%Y")

    grouped = {
        "Bóng Đá": [],
        "Bóng Rổ": [],
        "Bóng Chuyền": [],
        "Quần Vợt": [],
        "Bóng Bàn": [],
        "Thể Thao Khác": []
    }

    total_channels = 0

    for match in all_matches:
        teams = match.get("teams", {})
        home = teams.get("home", {}).get("name", "").strip()
        away = teams.get("away", {}).get("name", "").strip()
        if not home or not away:
            continue

        # Lọc ưu tiên các trận trong ngày hôm nay hoặc ngày mai (hoặc đang LIVE)
        match_date = match.get("date", "")
        is_live = match.get("is_live", False)
        status_code = match.get("status_code", "")
        
        if match_date and match_date not in [current_date_str, tomorrow_date_str] and not is_live and status_code != "LIVE":
            continue

        stype = match.get("type", "")
        league = match.get("league", {})
        logo = teams.get("home", {}).get("logo", "") or league.get("icon", "")
        
        time_str = match.get("time", "")
        day_month = match.get("day_month", "")
        t_display = f"{time_str} {day_month}".strip() or "Hôm nay"

        if is_live or status_code == "LIVE":
            status_icon = "🟢 "
        elif status_code in ["FT", "Kết thúc"]:
            status_icon = "🏁 "
        else:
            status_icon = "⏳ "

        blv_list = match.get("blv", [])
        blv_str = ""
        if blv_list:
            blv_name = str(blv_list[0]).replace('blv-', '').capitalize()
            blv_str = f" ({blv_name})"

        fi = str(match.get("fi", match.get("id", "")))
        if not fi:
            continue

        stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{fi}_hd/{fi}_hd@720p.m3u8"

        # Phân loại nhóm thể thao
        if stype == "football" or "⚽" in stype:
            group, emoji = "Bóng Đá", "⚽"
        elif stype == "basketball" or "🏀" in stype:
            group, emoji = "Bóng Rổ", "🏀"
        elif stype == "volleyball" or "🏐" in stype:
            group, emoji = "Bóng Chuyền", "🏐"
        elif stype in ["tennis", "bongban"] or any(e in stype for e in ["🥎", "🎾", "🏓"]):
            group = "Quần Vợt" if stype == "tennis" else "Bóng Bàn"
            emoji = "🥎" if stype == "tennis" else "🏓"
        else:
            group, emoji = "Thể Thao Khác", "🏆"

        display_title = f"{status_icon}{t_display} {emoji} {home} vs {away}{blv_str} [hls]"
        inf_line = f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}" , {display_title}'

        grouped[group].append({
            "inf": inf_line,
            "url": stream_url
        })
        total_channels += 1

    display_order = ["Bóng Đá", "Bóng Rổ", "Bóng Chuyền", "Quần Vợt", "Bóng Bàn", "Thể Thao Khác"]
    m3u_lines = ["#EXTM3U\n"]

    for group in display_order:
        for ch in grouped.get(group, []):
            m3u_lines.append(ch["inf"])
            m3u_lines.append(ch
            
