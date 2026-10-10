import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

TZ_VN = timezone(timedelta(hours=7))

def fetch_playlist_from_web_and_sources():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://giovang.tax/"
    }

    # 1. Tải danh sách stream active sống 100% từ ttthethao6 (chứa đủ cả lịch trong ngày)
    active_matches = []
    try:
        res = requests.get("https://tinyurl.com/ttthethao6", headers=headers, timeout=10)
        if res.status_code == 200:
            lines = res.text.splitlines()
            curr_inf = ""
            for line in lines:
                line = line.strip()
                if line.startswith("#EXTINF"):
                    curr_inf = line
                elif line.startswith("http") and "vcdn.cloud" in line:
                    if curr_inf:
                        active_matches.append({"inf": curr_inf, "url": line})
                        curr_inf = ""
    except Exception as e:
        print(f"Lỗi tải ttthethao6: {e}")

    # 2. Cào trực tiếp dữ liệu từ API live.json
    try:
        res_api = requests.get("https://live-api.keonhacaitp.one/storage/livestream/live.json", headers=headers, timeout=10)
        if res_api.status_code == 200:
            api_data = res_api.json().get("response", [])
            for item in api_data:
                home = item.get("teams", {}).get("home", {}).get("name", "")
                away = item.get("teams", {}).get("away", {}).get("name", "")
                if not home or not away:
                    continue
                
                # Kiểm tra xem trận này đã có trong active_matches chưa
                already_exists = any(home in m["inf"] or away in m["inf"] for m in active_matches)
                if not already_exists:
                    stype = item.get("type", "")
                    emoji = "⚽" if stype == "football" else "🏆"
                    logo = item.get("teams", {}).get("home", {}).get("logo", "")
                    time_str = item.get("time", "")
                    blv = item.get("blv", [])
                    blv_str = f" ({blv[0].replace('blv-', '').capitalize()})" if blv else ""
                    
                    fi = str(item.get("fi", item.get("id", "")))
                    stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{fi}_hd/{fi}_hd@720p.m3u8"
                    
                    inf_line = f'#EXTINF:-1 tvg-logo="{logo}" group-title="Bóng Đá" , 🟢 {time_str} {emoji} {home} vs {away}{blv_str} [hls]'
                    active_matches.append({"inf": inf_line, "url": stream_url})
    except Exception as e:
        print(f"Lỗi cào API: {e}")

    # 3. Phân loại chuẩn nhóm thể thao & Đưa Bóng Đá lên ĐẦU TIÊN
    grouped = {
        "Bóng Đá": [],
        "Bóng Rổ": [],
        "Bóng Chuyền": [],
        "Quần Vợt": [],
        "Bóng Bàn": [],
        "Thể Thao Khác": []
    }

    for match in active_matches:
        inf = match["inf"]
        if "⚽" in inf or "Bóng Đá" in inf:
            grp = "Bóng Đá"
        elif "🏀" in inf:
            grp = "Bóng Rổ"
        elif "🏐" in inf:
            grp = "Bóng Chuyền"
        elif "🥎" in inf or "🎾" in inf:
            grp = "Quần Vợt"
        elif "🏓" in inf:
            grp = "Bóng Bàn"
        else:
            grp = "Thể Thao Khác"

        # Đảm bảo group-title chính xác trong thẻ EXTINF
        if 'group-title="' in inf:
            parts = inf.split('group-title="')
            rest = parts[1].split('"', 1)
            new_inf = f'{parts[0]}group-title="{grp}"{rest[1]}'
        else:
            new_inf = inf

        grouped[grp].append({"inf": new_inf, "url": match["url"]})

    # Xuất ra file playlist.m3u
    display_order = ["Bóng Đá", "Bóng Rổ", "Bóng Chuyền", "Quần Vợt", "Bóng Bàn", "Thể Thao Khác"]
    m3u_lines = ["#EXTM3U\n"]

    for grp in display_order:
        for item in grouped.get(grp, []):
            m3u_lines.append(item["inf"])
            m3u_lines.append(item["url"] + "\n")

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    print("Đã tạo thành công playlist.m3u đầy đủ!")

if __name__ == "__main__":
    fetch_playlist_from_web_and_sources()
    
