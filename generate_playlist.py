import time
import requests
import re
from datetime import datetime, timezone, timedelta

TZ_VN = timezone(timedelta(hours=7))

def get_real_stream_url(detail_slug):
    """ Truyen cập vào trang chi tiết trận đấu trên giovang.tax để bóc lấy Session ID 1791xxxxxx thực sự """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://giovang.tax/"
    }
    url = f"https://giovang.tax/{detail_slug}"
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            # Tìm chuỗi chứa link vcdn.cloud có dạng 1791xxxxxx
            match = re.search(r'https?://[^\s<>"]+vcdn\.cloud/[^\s<>"]*(1791\d+)[^\s<>"]*\.m3u8', res.text)
            if match:
                sid = match.group(1)
                return f"https://ftlh5sc02iliv.vcdn.cloud/{sid}_hd/{sid}_hd@720p.m3u8"
    except Exception:
        pass
    return None

def fetch_and_generate_m3u():
    timestamp = int(time.time())
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://giovang.tax/"
    }

    # Lấy danh sách trận từ API chính thức
    try:
        res = requests.get(f"https://live-api.keonhacaitp.one/storage/livestream/live.json?t={timestamp}", headers=headers, timeout=8)
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

    for m in matches:
        teams = m.get("teams", {})
        home = teams.get("home", {}).get("name", "")
        away = teams.get("away", {}).get("name", "")
        if not home or not away:
            continue

        stype = m.get("type", "")
        logo = teams.get("home", {}).get("logo", "") or m.get("league", {}).get("icon", "")
        time_str = m.get("time", "")
        blv = m.get("blv", [])
        blv_str = f" ({blv[0].replace('blv-', '').capitalize()})" if blv else ""

        # Xác định nhóm
        if stype == "football":
            group, emoji = "Bóng Đá", "⚽"
        elif stype == "basketball":
            group, emoji = "Bóng Rổ", "🏀"
        elif stype == "volleyball":
            group, emoji = "Bóng Chuyền", "🏐"
        elif stype in ["tennis", "bongban"]:
            group = "Quần Vợt" if stype == "tennis" else "Bóng Bàn"
            emoji = "🥎" if stype == "tennis" else "🏓"
        else:
            group, emoji = "Thể Thao Khác", "🏆"

        title = f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}" , 🟢 {time_str} {emoji} {home} vs {away}{blv_str} [hls]'

        # Bóc tách link stream thực tế 100% tự chủ
        slug = m.get("slug") or f"truc-tiep-{home.lower().replace(' ', '-')}-vs-{away.lower().replace(' ', '-')}"
        stream_url = get_real_stream_url(slug)
        
        # Nếu chưa bóc được (do trận chưa lên sóng), mới dùng link đệm fi
        if not stream_url:
            fi = str(m.get("fi", m.get("id", "")))
            stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{fi}_hd/{fi}_hd@720p.m3u8"

        grouped[group].append({"inf": title, "url": stream_url})

    # Sắp xếp Bóng Đá lên đầu
    display_order = ["Bóng Đá", "Bóng Rổ", "Bóng Chuyền", "Quần Vợt", "Bóng Bàn", "Thể Thao Khác"]
    m3u_lines = ["#EXTM3U\n"]
    for grp in display_order:
        for ch in grouped.get(grp, []):
            m3u_lines.append(ch["inf"])
            m3u_lines.append(ch["url"] + "\n")

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

if __name__ == "__main__":
    fetch_and_generate_m3u()
