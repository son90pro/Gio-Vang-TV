import time
import requests
from datetime import datetime, timezone, timedelta

TZ_VN = timezone(timedelta(hours=7))

def get_api_stream_link(fi_id):
    """ Truy vấn trực tiếp API chi tiết trận đấu để lấy link stream chuẩn từ máy chủ """
    if not fi_id:
        return None
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://giovang.tax/"
    }
    
    # Thử gọi vào các endpoint API lưu trữ luồng của hạ tầng này
    endpoints = [
        f"https://live-api.keonhacaitp.one/storage/livestream/match.json?fi={fi_id}",
        f"https://live-api.keonhacaitp.one/storage/livestream/detail.json?fi={fi_id}"
    ]
    
    for url in endpoints:
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                # Tìm kiếm mọi trường có khả năng chứa link vcdn hoặc m3u8 trong JSON trả về
                response_data = data.get("response", data)
                if isinstance(response_data, dict):
                    for key in ["stream_url", "link", "url", "hls", "file"]:
                        val = response_data.get(key)
                        if val and isinstance(val, str) and "m3u8" in val:
                            return val.replace('\\/', '/')
        except Exception:
            continue
            
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
            print("Không kết nối được API chính!")
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

        # Lấy mã định danh trận đấu
        fi = str(match.get("fi", match.get("id", "")))
        
        # Lấy link stream thực tế qua API chi tiết trận đấu
        stream_url = get_api_stream_link(fi)
        
        # Nếu trận chưa có link active thực sự qua API, bỏ qua để không làm gián đoạn tivi bằng link chết
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

_grouped = grouped[group]
        _grouped.append({
            "inf": inf_line,
            "url": stream_url
        })
        total_channels += 1

    # Thứ tự hiển thị ưu tiên (Bóng Đá đứng đầu)
    display_order = ["Bóng Đá", "Bóng Rổ", "Bóng Chuyền", "Quần Vợt", "Bóng Bàn", "Thể Thao Khác"]
    m3u_lines = ["#EXTM3U\n"]

    for group in display_order:
        for ch in grouped.get(group, []):
            m3u_lines.append(ch["inf"])
            m3u_lines.append(ch["url"] + "\n")

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    print(f"Đã cập nhật playlist thành công với {total_channels} kênh chuẩn xác!")

if __name__ == "__main__":
    fetch_and_generate_m3u()
    
