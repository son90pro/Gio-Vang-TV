import time
import requests
from datetime import datetime, timezone, timedelta

TZ_VN = timezone(timedelta(hours=7))

def fetch_and_generate_m3u():
    timestamp = int(time.time())
    # Sử dụng API endpoint chính xác với domain mới
    api_url = f"https://live-api.keonhacaitp.one/storage/livestream/live.json?t={timestamp}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://giovang.uno/"
    }

    try:
        res = requests.get(api_url, headers=headers, timeout=10)
        if res.status_code != 200:
            print(f"Không thể kết nối API, mã lỗi: {res.status_code}")
            return
        
        data = res.json()
        matches = data.get("response", [])
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
        
        # Lấy logo đội nhà hoặc biểu tượng giải đấu
        league = match.get("league", {})
        logo = teams.get("home", {}).get("logo", "") or league.get("icon", "")
        
        time_str = match.get("time", "")
        day_month = match.get("day_month", "")
        t_display = f"{time_str} {day_month}".strip() or "Hôm nay"

        is_live = match.get("is_live", False)
        status_code = match.get("status_code", "")
        status_icon = "🟢 " if (is_live or status_code == "LIVE") else "⏳ "

        # Lấy tên Bình luận viên (BLV)
        blv_list = match.get("blv", [])
        blv_str = ""
        if blv_list:
            blv_name = str(blv_list[0]).replace('blv-', '').capitalize()
            blv_str = f" ({blv_name})"

        # Lấy mã định danh fi chính xác từ JSON
        fi = str(match.get("fi", ""))
        if not fi:
            continue

        # Xây dựng đường dẫn stream .m3u8 chuẩn xác dựa trên fi
        stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{fi}_hd/{fi}_hd@720p.m3u8"

        # Phân loại nhóm thể thao dựa trên trường type
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

    # Thứ tự hiển thị các nhóm trên tivi (Bóng Đá lên đầu)
    display_order = ["Bóng Đá", "Bóng Rổ", "Bóng Chuyền", "Quần Vợt", "Bóng Bàn", "Thể Thao Khác"]
    m3u_lines = ["#EXTM3U\n"]

    for group in display_order:
        for ch in grouped.get(group, []):
            m3u_lines.append(ch["inf"])
            m3u_lines.append(ch["url"] + "\n")

    # Ghi tệp playlist.m3u
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
        
    print(f"Đã cập nhật playlist thành công với tổng số {total_channels} kênh!")

if __name__ == "__main__":
    fetch_and_generate_m3u()
    
