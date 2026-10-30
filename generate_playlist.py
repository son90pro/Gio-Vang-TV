import time
import requests

def fetch_and_generate_m3u():
    timestamp = int(time.time())
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://giovang.uno/"
    }

    # Quét đồng thời các endpoint chứa toàn bộ lịch thi đấu và trận live của hệ thống
    endpoints = [
        f"https://live-api.keonhacaitp.one/storage/livestream/home.json?t={timestamp}",
        f"https://live-api.keonhacaitp.one/storage/livestream/matches.json?t={timestamp}",
        f"https://live-api.keonhacaitp.one/storage/livestream/schedule.json?t={timestamp}",
        f"https://live-api.keonhacaitp.one/storage/livestream/live.json?t={timestamp}"
    ]

    all_matches = []
    seen_ids = set()

    for url in endpoints:
        try:
            res = requests.get(url, headers=headers, timeout=8)
            if res.status_code == 200:
                data = res.json()
                matches = []
                if isinstance(data, dict):
                    matches = data.get("response", data.get("matches", data.get("data", [])))
                    if not matches and "response" in data:
                        matches = data["response"]
                elif isinstance(data, list):
                    matches = data

                if isinstance(matches, list):
                    for m in matches:
                        m_id = str(m.get("fi", m.get("id", "")))
                        if m_id and m_id not in seen_ids:
                            seen_ids.add(m_id)
                            all_matches.append(m)
        except Exception:
            continue

    print(f"Tổng hợp được tổng số {len(all_matches)} trận đấu từ hệ thống.")

    m3u_lines = ["#EXTM3U\n"]
    total_channels = 0

    for match in all_matches:
        teams = match.get("teams", {})
        home = teams.get("home", {}).get("name", "").strip()
        away = teams.get("away", {}).get("name", "").strip()
        
        # Xử lý trường hợp sự kiện đặc biệt (như F1, Võ thuật không có cấu trúc home vs away chuẩn)
        if not home or not away:
            title_alt = match.get("title", match.get("name", ""))
            if title_alt:
                home = title_alt
                away = ""
            else:
                continue

        league = match.get("league", {})
        logo = teams.get("home", {}).get("logo", "") or league.get("icon", "")
        
        time_str = match.get("time", "")
        if len(time_str) > 5:
            time_str = time_str[:5]
            
        day_month = match.get("day_month", "")
        t_display = f"{time_str} {day_month}".strip() or "Hôm nay"

        is_live = match.get("is_live", False)
        status_code = match.get("status_code", "")
        
        if is_live or status_code == "LIVE" or status_code == "Đang diễn ra":
            status_icon = "🟢 "
        else:
            status_icon = ""

        # Nhận diện biểu tượng môn thể thao
        stype = match.get("type", "").lower()
        if "basketball" in stype or "bóng rổ" in stype:
            emoji = "🏀"
        elif "volleyball" in stype or "bóng chuyền" in stype:
            emoji = "🏐"
        elif "tennis" in stype or "quần vợt" in stype:
            emoji = "🎾"
        elif "f1" in stype or "formula" in stype:
            emoji = "🏎️"
        elif "box" in stype or "one" in stype or "mma" in stype or "🥊" in stype:
            emoji = "🥊"
        elif "game" in stype or "esport" in stype:
            emoji = "🎮"
        else:
            emoji = "⚽"

        blv_list = match.get("blv", [])
        blv_str = ""
        if blv_list:
            blv_name = str(blv_list[0]).replace('blv-', '').capitalize()
            blv_str = f" ({blv_name})"

        fi = str(match.get("fi", match.get("id", "")))
        if not fi:
            continue

        # Xây dựng đường dẫn stream chuẩn vcdn
        stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{fi}_hd/{fi}_hd@720p.m3u8"

        # Gom nhóm toàn bộ vào chung group "Giờ Vàng TV" đúng yêu cầu
        match_title_str = f"{status_icon}{t_display} {emoji} {home}"
        if away:
            match_title_str += f" vs {away}"
        match_title_str += f"{blv_str} [hls]"

        inf_line = f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV" , {match_title_str}'

        m3u_lines.append(inf_line + "\n")
        m3u_lines.append(stream_url + "\n")
        total_channels += 1

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.writelines(m3u_lines)
        
    print(f"Đã cập nhật playlist thành công với tổng số {total_channels} kênh!")

if __name__ == "__main__":
    fetch_and_generate_m3u()
    
