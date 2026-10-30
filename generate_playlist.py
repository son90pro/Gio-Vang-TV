import time
import requests

def fetch_and_generate_m3u():
    timestamp = int(time.time())
    api_url = f"https://live-api.keonhacaitp.one/storage/livestream/live.json?t={timestamp}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://giovang.uno/"
    }

    print(f"Đang gọi API: {api_url}")
    try:
        res = requests.get(api_url, headers=headers, timeout=10)
        if res.status_code != 200:
            print(f"Không thể kết nối API, mã lỗi: {res.status_code}")
            return
        
        data = res.json()
        matches = data.get("response", [])
        print(f"API trả về tổng số {len(matches)} trận đấu thô.")
    except Exception as e:
        print(f"Lỗi kết nối API: {e}")
        return

    grouped = {
        "Bóng Đá": [],
        "Bóng Rổ": [],
        "Bóng Chuyền": [],
        "Quần Vợt": [],
        "Bóng Bàn": [],
        "Thể Thao Khác": []
    }

    total_channels = 0

    for match in matches:
        teams = match.get("teams", {})
        home = teams.get("home", {}).get("name", "").strip()
        away = teams.get("away", {}).get("name", "").strip()
        if not home or not away:
            continue

        stype = match.get("type", "")
        league = match.get("league", {})
        logo = teams.get("home", {}).get("logo", "") or league.get("icon", "")
        
        time_str = match.get("time", "")
        day_month = match.get("day_month", "")
        t_display = f"{time_str} {day_month}".strip() or "Hôm nay"

        is_live = match.get("is_live", False)
        status_code = match.get("status_code", "")
        
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
            m3u_lines.append(ch["inf"] + "\n")
            m3u_lines.append(ch["url"] + "\n")

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.writelines(m3u_lines)
        
    print(f"Đã cập nhật playlist thành công với tổng số {total_channels} kênh!")

if __name__ == "__main__":
    fetch_and_generate_m3u()
    
