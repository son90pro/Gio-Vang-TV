import time
import requests

def fetch_and_generate_m3u():
    timestamp = int(time.time())
    url = f"https://live-api.keonhacaitp.one/storage/livestream/live.json?t={timestamp}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://giovang.tax/"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print("Không tải được dữ liệu từ API live.json!")
            return
        data = response.json()
        matches = data.get("response", [])
    except Exception as e:
        print(f"Lỗi truy vấn API: {e}")
        return

    # Tải thêm danh sách link stream active từ nguồn phụ để map cho chính xác trận đang live
    active_streams = {}
    try:
        res = requests.get("https://tinyurl.com/ttthethao6", headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        if res.status_code == 200:
            lines = res.text.splitlines()
            c_title = ""
            for line in lines:
                line = line.strip()
                if line.startswith("#EXTINF"):
                    c_title = line
                elif line.startswith("http") and "vcdn.cloud" in line:
                    if c_title:
                        active_streams[c_title] = line
                        c_title = ""
    except Exception:
        pass

    # Phân nhóm các môn thể thao và ưu tiên Bóng Đá lên đầu tiên
    grouped = {
        "Bóng Đá": [],
        "Bóng Rổ": [],
        "Bóng Chuyền": [],
        "Quần Vợt": [],
        "Bóng Bàn": [],
        "Thể Thao Khác": []
    }

    for match in matches:
        sport_type = match.get("type", "")
        teams = match.get("teams", {})
        home = teams.get("home", {}).get("name", "")
        away = teams.get("away", {}).get("name", "")
        
        if not home or not away:
            continue

        logo = teams.get("home", {}).get("logo", "") or match.get("league", {}).get("icon", "")
        
        # Thời gian
        time_str = match.get("time", "")
        day_month = match.get("day_month", "")
        t_display = f"{time_str} {day_month}".strip()
        if not t_display:
            t_display = "Hôm nay"

        # Trạng thái Live hay Sắp diễn ra
        is_live = match.get("is_live", False)
        status_icon = "🟢 " if is_live else "⏳ "

        # BLV
        blv_list = match.get("blv", [])
        blv_str = f" ({blv_list[0].replace('blv-', '').capitalize()})" if blv_list else ""

        # Xác định nhóm môn thể thao
        if sport_type == "football" or "⚽" in sport_type:
            group = "Bóng Đá"
            emoji = "⚽"
        elif sport_type == "basketball" or "🏀" in sport_type:
            group = "Bóng Rổ"
            emoji = "🏀"
        elif sport_type == "volleyball" or "🏐" in sport_type:
            group = "Bóng Chuyền"
            emoji = "🏐"
        elif sport_type in ["tennis", "bongban", "badminton"] or any(e in sport_type for e in ["🥎", "🎾", "🏓", "🏸"]):
            group = "Quần Vợt" if "tennis" in sport_type else "Bóng Bàn"
            emoji = "🥎" if "tennis" in sport_type else "🏓"
        else:
            group = "Thể Thao Khác"
            emoji = "🏆"

        display_title = f"{status_icon}{t_display} {emoji} {home} vs {away}{blv_str} [hls]"

        # Tìm link stream thật
        stream_url = ""
        for title_key, url_val in active_streams.items():
            if home in title_key or away in title_key:
                stream_url = url_val
                break

        # Nếu chưa có trong active_streams, dùng link chuẩn dự phòng theo fi/id
        if not stream_url:
            fi = str(match.get("fi", match.get("id", "")))
            if fi.isdigit() and len(fi) >= 9:
                stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{fi}_hd/{fi}_hd@720p.m3u8"
            else:
                stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{match.get('time_start', 0)}_hd/{match.get('time_start', 0)}_hd@720p.m3u8"

        inf_line = f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}" , {display_title}'
        
        grouped[group].append({
            "inf": inf_line,
            "url": stream_url
        })

    # Thứ tự hiển thị (Bóng Đá đứng đầu)
    display_order = ["Bóng Đá", "Bóng Rổ", "Bóng Chuyền", "Quần Vợt", "Bóng Bàn", "Thể Thao Khác"]

    m3u_lines = ["#EXTM3U\n"]
    for group in display_order:
        for ch in grouped.get(group, []):
            m3u_lines.append(ch["inf"])
            m3u_lines.append(ch["url"] + "\n")

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    print("Đã tạo playlist thành công với toàn bộ danh sách (Live + Sắp diễn ra)!")

if __name__ == "__main__":
    fetch_and_generate_m3u()
    
