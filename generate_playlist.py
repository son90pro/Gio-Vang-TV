import time
import requests

def fetch_and_generate_m3u():
    timestamp = int(time.time())
    api_url = f"https://live-api.keonhacaitp.one/storage/livestream/live.json?t={timestamp}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://giovang.tax/"
    }

    try:
        res = requests.get(api_url, headers=headers, timeout=10)
        if res.status_code != 200:
            print("Không kết nối được API chính!")
            return
        matches = res.json().get("response", [])
    except Exception as e:
        print(f"Lỗi API: {e}")
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
        logo = teams.get("home", {}).get("logo", "") or match.get("league", {}).get("icon", "")
        time_str = match.get("time", "")
        day_month = match.get("day_month", "")
        t_display = f"{time_str} {day_month}".strip() or "Hôm nay"

        is_live = match.get("is_live", False)
        status_code = match.get("status_code", "")
        status_icon = "🟢 " if (is_live or status_code == "LIVE") else "⏳ "

        blv = match.get("blv", [])
        blv_str = f" ({blv[0].replace('blv-', '').capitalize()})" if blv else ""

        # Lọc ra các trường link tiềm năng có sẵn trong API (nếu nhà phát triển có đính kèm)
        stream_url = (
            match.get("stream_url") or 
            match.get("link") or 
            match.get("url") or 
            match.get("hls") or 
            ""
        )

        # Nếu API không chứa sẵn link, ta kiểm tra xem có mã fi/link phụ nào khác không
        if not stream_url:
            fi = str(match.get("fi", match.get("id", "")))
            # Thử cấu trúc đường dẫn chuẩn thường dùng của vcdn nếu trận đang live thực sự
            if is_live or status_code == "LIVE":
                stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{fi}_hd/{fi}_hd@720p.m3u8"
            else:
                # Trận chưa đá thực sự thì bỏ qua hoặc gán link chờ để không làm lỗi tivi
                continue

        # Phân loại nhóm thể thao
        if stype == "football" or "⚽" in stype:
            group, emoji = "Bóng Đá", "⚽"
        elif stype == "basketball" or "🏀" in stype:
            group, emoji = "Bóng Rổ", "🏀"
        elif stype == "volleyball" or "🏐" in sport_type if 'sport_type' in locals() else "volleyball" in stype:
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

    # Thứ tự ưu tiên (Bóng Đá lên đầu)
    display_order = ["Bóng Đá", "Bóng Rổ", "Bóng Chuyền", "Quần Vợt", "Bóng Bàn", "Thể Thao Khác"]
    m3u_lines = ["#EXTM3U\n"]

    for group in display_order:
        for ch in grouped.get(group, []):
            m3u_lines.append(ch["inf"])
            m3u_lines.append(ch["url"] + "\n")

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    print(f"Đã tạo playlist thành công với {total_channels} kênh đang hoạt động!")

if __name__ == "__main__":
    fetch_and_generate_m3u()
    
