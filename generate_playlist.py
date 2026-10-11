import time
import requests
from datetime import datetime, timezone, timedelta

TZ_VN = timezone(timedelta(hours=7))

# Danh sách các nguồn M3U tổng hợp uy tín, ổn định cao từ cộng đồng IPTV
BACKUP_PLAYLISTS = [
    # Thêm các nguồn stream thể thao công khai, ổn định tại đây
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/vn_sports.m3u",
]

def fetch_external_sports():
    """ Tải và trích xuất các kênh thể thao uy tín từ nguồn ngoài để bổ sung """
    extra_channels = []
    for url in BACKUP_PLAYLISTS:
        try:
            res = requests.get(url, timeout=8)
            if res.status_code == 200:
                lines = res.text.splitlines()
                current_inf = ""
                for line in lines:
                    line = line.strip()
                    if line.startswith("#EXTINF:"):
                        current_inf = line
                    elif line and not line.startswith("#") and current_inf:
                        extra_channels.append({
                            "inf": current_inf,
                            "url": line
                        })
                        current_inf = ""
        except Exception:
            pass
    return extra_channels

def fetch_and_generate_m3u():
    timestamp = int(time.time())
    api_url = f"https://live-api.keonhacaitp.one/storage/livestream/live.json?t={timestamp}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://giovang.tax/"
    }

    grouped = {
        "Bóng Đá": [],
        "Bóng Rổ": [],
        "Bóng Chuyền": [],
        "Quần Vợt": [],
        "Bóng Bàn": [],
        "Thể Thao Khác": []
    }

    total_channels = 0

    # 1. Lấy dữ liệu từ nguồn Giờ Vàng (nếu có trận active)
    try:
        res = requests.get(api_url, headers=headers, timeout=10)
        if res.status_code == 200:
            matches = res.json().get("response", [])
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

                match_id = match.get("fi") or match.get("id") or match.get("match_id") or ""
                if not match_id:
                    continue

                stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{match_id}_hd/{match_id}_hd@720p.m3u8"

                # Phân loại nhóm thể thao
                if stype == "football" or "⚽" in stype:
                    group = "Bóng Đá"
                    emoji = "⚽"
                elif stype == "basketball" or "🏀" in stype:
                    group = "Bóng Rổ"
                    emoji = "🏀"
                elif stype == "volleyball" or "🏐" in stype:
                    group = "Bóng Chuyền"
                    emoji = "🏐"
                elif stype in ["tennis", "bongban"] or any(e in stype for e in ["🥎", "🎾", "🏓"]):
                    group = "Quần Vợt" if stype == "tennis" else "Bóng Bàn"
                    emoji = "🥎" if stype == "tennis" else "🏓"
                else:
                    group = "Thể Thao Khác"
                    emoji = "🏆"

                display_title = f"{status_icon}{t_display} {emoji} {home} vs {away}{blv_str} [hls]"
                inf_line = f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}" , {display_title}'

                grouped[group].append({
                    "inf": inf_line,
                    "url": stream_url
                })
                total_channels += 1
    except Exception as e:
        print(f"Lỗi khi lấy dữ liệu chính: {e}")

    # 2. Gộp thêm nguồn thể thao dự phòng uy tín bên ngoài vào nhóm tương ứng
    external_channels = fetch_external_sports()
    for ch in external_channels:
        grouped["Thể Thao Khác"].append(ch)
        total_channels += 1

    # Xuất file playlist.m3u hoàn chỉnh
    display_order = ["Bóng Đá", "Bóng Rổ", "Bóng Chuyền", "Quần Vợt", "Bóng Bàn", "Thể Thao Khác"]
    m3u_lines = ["#EXTM3U\n"]

    for group in display_order:
        for ch in grouped.get(group, []):
            m3u_lines.append(ch["inf"])
            m3u_lines.append(ch["url"] + "\n")

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    print(f"Đã gộp và tạo playlist thành công với tổng số {total_channels} kênh!")

if __name__ == "__main__":
    fetch_and_generate_m3u()
    
