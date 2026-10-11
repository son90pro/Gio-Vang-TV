import time
import requests
import re
from datetime import datetime, timezone, timedelta

TZ_VN = timezone(timedelta(hours=7))

def get_live_stream_url(match_item):
    """ Trích xuất hoặc dò tìm link .m3u8 chứa session động từ dữ liệu trận đấu """
    # Kiểm tra xem API có sẵn link hay không
    for key in ["stream_url", "link", "url", "hls"]:
        val = match_item.get(key)
        if val and isinstance(val, str) and "m3u8" in val:
            return val.replace('\\/', '/')
            
    # Nếu không có sẵn, lấy mã định danh fi hoặc id để gọi API chi tiết
    fi = str(match_item.get("fi", match_item.get("id", "")))
    if not fi:
        return None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://giovang.tax/"
    }
    
    endpoints = [
        f"https://live-api.keonhacaitp.one/storage/livestream/match.json?fi={fi}",
        f"https://live-api.keonhacaitp.one/storage/livestream/detail.json?fi={fi}"
    ]

    for url in endpoints:
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                text_data = res.text
                # Quét tìm kiếm chuỗi .m3u8 hoặc vcdn.cloud xuất hiện trong phản hồi JSON/HTML
                match = re.search(r'(https?://[^\s<>"]+vcdn\.cloud/[^\s<>"]+\.m3u8)', text_data)
                if match:
                    return match.group(1).replace('&quot;', '').replace('\\/', '/')
        except Exception:
            continue
            
    # Fallback theo chuẩn session động nếu trận đang phát sóng trực tiếp (LIVE)
    is_live = match_item.get("is_live", False)
    status_code = match_item.get("status_code", "")
    if is_live or status_code == "LIVE":
        # Sử dụng fi làm mã định danh luồng trực tiếp
        return f"https://ftlh5sc02iliv.vcdn.cloud/{fi}_hd/{fi}_hd@720p.m3u8"
        
    return None

def fetch_and_generate_m3u():
    timestamp = int(time.time())
    api_url = f"https://live-api.keonhacaitp.one/storage/livestream/live.json?t={timestamp}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://giovang.tax/"
    }

    try:
        res = requests.get(api_url, headers=headers, timeout=10)
        if res.status_code != 200:
            print("Không tải được danh sách từ API chính!")
            return
        matches = res.json().get("response", [])
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
        logo = teams.get("home", {}).get("logo", "") or match.get("league", {}).get("icon", "")
        time_str = match.get("time", "")
        day_month = match.get("day_month", "")
        t_display = f"{time_str} {day_month}".strip() or "Hôm nay"

        is_live = match.get("is_live", False)
        status_code = match.get("status_code", "")
        status_icon = "🟢 " if (is_live or status_code == "LIVE") else "⏳ "

        blv = match.get("blv", [])
        blv_str = f" ({blv[0].replace('blv-', '').capitalize()})" if blv else ""

        # Lấy link stream chuẩn xác có chứa session động
        stream_url = get_live_stream_url(match)
        if not stream_url:
            continue

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

    # Sắp xếp hiển thị ưu tiên (Bóng Đá lên đầu)
    display_order = ["Bóng Đá", "Bóng Rổ", "Bóng Chuyền", "Quần Vợt", "Bóng Bàn", "Thể Thao Khác"]
    m3u_lines = ["#EXTM3U\n"]

    for group in display_order:
        for ch in grouped.get(group, []):
            m3u_lines.append(ch["inf"])
            m3u_lines.append(ch["url"] + "\n")

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    print(f"Đã cập nhật playlist thành công với {total_channels} kênh độc lập!")

if __name__ == "__main__":
    fetch_and_generate_m3u()
    
