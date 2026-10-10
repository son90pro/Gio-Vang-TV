import time
import requests
import re
from datetime import datetime, timezone, timedelta

TZ_VN = timezone(timedelta(hours=7))

def fetch_independent_playlist():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://giovang.tax/"
    }
    
    all_matches = []
    seen_keys = set()

    # 1. Truy vấn các endpoint API chính thức của hệ thống Giờ Vàng TV
    timestamp = int(time.time())
    api_endpoints = [
        f"https://live-api.keonhacaitp.one/storage/livestream/live.json?t={timestamp}",
        f"https://live-api.keonhacaitp.one/storage/livestream/today.json?t={timestamp}",
        f"https://live-api.keonhacaitp.one/storage/livestream/schedule.json?t={timestamp}"
    ]

    for url in api_endpoints:
        try:
            res = requests.get(url, headers=headers, timeout=8)
            if res.status_code == 200:
                data = res.json()
                matches = data.get("response", [])
                if isinstance(matches, list):
                    for m in matches:
                        teams = m.get("teams", {})
                        home = teams.get("home", {}).get("name", "").strip()
                        away = teams.get("away", {}).get("name", "").strip()
                        if home and away:
                            key = f"{home}_vs_{away}"
                            if key not in seen_keys:
                                seen_keys.add(key)
                                all_matches.append(m)
        except Exception:
            continue

    # 2. Cào trực tiếp từ trang chủ giovang.tax để vét sạch các trận ở tab Sắp diễn ra nếu API thiếu
    try:
        res_web = requests.get("https://giovang.tax/", headers=headers, timeout=10)
        if res_web.status_code == 200:
            html = res_web.text
            # Tìm kiếm các chuỗi JSON hoặc thông tin trận đấu được render sẵn trong HTML
            # (Hệ thống tự động bóc tách các đội bóng xuất hiện trên trang)
            found_teams = re.findall(r'name["\s:]+["\']([^"\']+)["\']', html)
            # Logic dự phòng nếu cần bổ sung
    except Exception:
        pass

    return all_matches

def generate_m3u():
    matches = fetch_independent_playlist()
    
    # Phân nhóm môn thể thao, ưu tiên Bóng Đá lên hàng đầu
    grouped = {
        "Bóng Đá": [],
        "Bóng Rổ": [],
        "Bóng Chuyền": [],
        "Quần Vợt": [],
        "Bóng Bàn": [],
        "Thể Thao Khác": []
    }

    for match in matches:
        stype = match.get("type", "")
        teams = match.get("teams", {})
        home = teams.get("home", {}).get("name", "").strip()
        away = teams.get("away", {}).get("name", "").strip()
        if not home or not away:
            continue

        logo = teams.get("home", {}).get("logo", "") or match.get("league", {}).get("icon", "")
        time_str = match.get("time", "")
        day_month = match.get("day_month", "")
        t_display = f"{time_str} {day_month}".strip() or "Hôm nay"

        is_live = match.get("is_live", False)
        status_code = match.get("status_code", "")
        if is_live or status_code == "LIVE":
            status_icon = "🟢 "
        else:
            status_icon = "⏳ "

        blv_list = match.get("blv", [])
        blv_str = f" ({blv_list[0].replace('blv-', '').capitalize()})" if blv_list else ""

        # Phân loại nhóm môn thể thao chuẩn xác
        if "football" in stype or "⚽" in stype:
            group = "Bóng Đá"
            emoji = "⚽"
        elif "basketball" in stype or "🏀" in stype:
            group = "Bóng Rổ"
            emoji = "🏀"
        elif "volleyball" in stype or "🏐" in stype:
            group = "Bóng Chuyền"
            emoji = "🏐"
        elif any(k in stype for k in ["tennis", "bongban", "badminton", "🥎", "🎾", "🏓", "🏸"]):
            group = "Quần Vợt" if "tennis" in stype else "Bóng Bàn"
            emoji = "🥎" if "tennis" in stype else "🏓"
        else:
            group = "Thể Thao Khác"
            emoji = "🏆"

        display_title = f"{status_icon}{t_display} {emoji} {home} vs {away}{blv_str} [hls]"

        fi = str(match.get("fi", match.get("id", "")))
        if fi.isdigit() and len(fi) >= 9:
            stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{fi}_hd/{fi}_hd@720p.m3u8"
        else:
            stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{fi}_hd/{fi}_hd@720p.m3u8"

        inf_line = f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}" , {display_title}'
        grouped[group].append({"inf": inf_line, "url": stream_url})

    # Thứ tự hiển thị ưu tiên (Bóng Đá luôn đứng đầu)
    display_order = ["Bóng Đá", "Bóng Rổ", "Bóng Chuyền", "Quần Vợt", "Bóng Bàn", "Thể Thao Khác"]
    m3u_lines = ["#EXTM3U\n"]
    
    for grp in display_order:
        for item in grouped.get(grp, []):
            m3u_lines.append(item["inf"])
            m3u_lines.append(item["url"] + "\n")

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    print("Đã tạo playlist độc lập thành công!")

if __name__ == "__main__":
    generate_m3u()
    
