import time
import requests
from datetime import datetime, timezone, timedelta

# Múi giờ Việt Nam (UTC+7)
TZ_VN = timezone(timedelta(hours=7))

def fetch_and_generate_m3u():
    # Tạo timestamp động hệt như cách trình duyệt web gọi API
    timestamp = int(time.time())
    url = f"https://live-api.keonhacaitp.one/storage/livestream/live.json?t={timestamp}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://giovang.tax/"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Lỗi gọi API: Mã trạng thái {response.status_code}")
            return
        data = response.json()
        matches = data.get("response", [])
    except Exception as e:
        print(f"Lỗi kết nối API: {e}")
        return

    # Phân nhóm các môn thể thao
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
        home = teams.get("home", {}).get("name", "").strip()
        away = teams.get("away", {}).get("name", "").strip()
        
        if not home or not away:
            continue

        logo = teams.get("home", {}).get("logo", "") or match.get("league", {}).get("icon", "")
        
        # Xử lý thời gian hiển thị
        time_str = match.get("time", "")
        day_month = match.get("day_month", "")
        t_display = f"{time_str} {day_month}".strip() or "Hôm nay"

        # Trạng thái trận đấu
        is_live = match.get("is_live", False)
        status_code = match.get("status_code", "")
        status_icon = "🟢 " if (is_live or status_code == "LIVE") else "⏳ "

        # Bình luận viên
        blv_list = match.get("blv", [])
        blv_str = f" ({blv_list[0].replace('blv-', '').capitalize()})" if blv_list else ""

        # Phân loại nhóm môn thể thao chuẩn xác
        if sport_type == "football" or "⚽" in sport_type:
            group, emoji = "Bóng Đá", "⚽"
        elif sport_type == "basketball" or "🏀" in sport_type:
            group, emoji = "Bóng Rổ", "🏀"
        elif sport_type == "volleyball" or "🏐" in sport_type:
            group, emoji = "Bóng Chuyền", "🏐"
        elif sport_type in ["tennis", "bongban"] or any(e in sport_type for e in ["🥎", "🎾", "🏓"]):
            group = "Quần Vợt" if sport_type == "tennis" else "Bóng Bàn"
            emoji = "🥎" if sport_type == "tennis" else "🏓"
        else:
            group, emoji = "Thể Thao Khác", "🏆"

        display_title = f"{status_icon}{t_display} {emoji} {home} vs {away}{blv_str} [hls]"

        # Lấy mã định danh fi hoặc id từ API để cấu thành đường dẫn luồng
        fi = str(match.get("fi", match.get("id", "")))
        stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{fi}_hd/{fi}_hd@720p.m3u8"

        inf_line = f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}" , {display_title}'
        
        grouped[group].append({
            "inf": inf_line,
            "url": stream_url
        })

    # Thứ tự hiển thị ưu tiên (Bóng Đá luôn đứng đầu danh sách)
    display_order = ["Bóng Đá", "Bóng Rổ", "Bóng Chuyền", "Quần Vợt", "Bóng Bàn", "Thể Thao Khác"]

    m3u_lines = ["#EXTM3U\n"]
    total_channels = 0
    
    for group in display_order:
        for ch in grouped.get(group, []):
            m3u_lines.append(ch["inf"])
            m3u_lines.append(ch["url"] + "\n")
            total_channels += 1

    # Lưu tệp playlist.m3u
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    print(f"Đã tạo playlist thành công với {total_channels} kênh độc lập!")

if __name__ == "__main__":
    fetch_and_generate_m3u()
    
