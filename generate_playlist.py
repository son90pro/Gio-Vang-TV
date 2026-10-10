import requests

def parse_m3u_from_source():
    """
    Tải toàn bộ danh sách trận đấu (bao gồm cả đang diễn ra và sắp diễn ra trong ngày) từ nguồn chuẩn
    """
    source_url = "https://tinyurl.com/ttthethao6"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    matches = []
    try:
        res = requests.get(source_url, headers=headers, timeout=10)
        if res.status_code == 200:
            lines = res.text.splitlines()
            current_inf = ""
            for line in lines:
                line = line.strip()
                if line.startswith("#EXTINF"):
                    current_inf = line
                elif line.startswith("http") and "vcdn.cloud" in line:
                    if current_inf:
                        matches.append({
                            "inf": current_inf,
                            "url": line
                        })
                        current_inf = ""
    except Exception as e:
        print(f"Lỗi đọc nguồn: {e}")
        
    return matches

def fetch_and_generate_m3u():
    raw_matches = parse_m3u_from_source()
    if not raw_matches:
        print("Không tải được danh sách!")
        return

    # Phân nhóm các môn thể thao và ưu tiên Bóng Đá lên đầu tiên
    grouped_channels = {
        "Bóng Đá": [],
        "Bóng Rổ": [],
        "Bóng Chuyền": [],
        "Quần Vợt": [],
        "Bóng Bàn": [],
        "Thể Thao Khác": []
    }

    for item in raw_matches:
        inf_line = item["inf"]
        stream_url = item["url"]

        # Nhận diện bộ môn dựa vào emoji biểu tượng trong tiêu đề
        assigned_group = "Thể Thao Khác"
        if "⚽" in inf_line:
            assigned_group = "Bóng Đá"
        elif "🏀" in inf_line:
            assigned_group = "Bóng Rổ"
        elif "🏐" in inf_line:
            assigned_group = "Bóng Chuyền"
        elif "🥎" in inf_line or "🎾" in inf_line:
            assigned_group = "Quần Vợt"
        elif "🏓" in inf_line:
            assigned_group = "Bóng Bàn"

        # Tự động gán group-title chuẩn vào thẻ EXTINF
        if 'group-title="' in inf_line:
            parts = inf_line.split('group-title="')
            if len(parts) > 1:
                rest = parts[1].split('"', 1)
                new_inf = f'{parts[0]}group-title="{assigned_group}"{rest[1]}'
            else:
                new_inf = inf_line
        else:
            new_inf = inf_line

        grouped_channels[assigned_group].append({
            "inf": new_inf,
            "url": stream_url
        })

    # Thứ tự sắp xếp hiển thị trên ứng dụng IPTV (Bóng Đá luôn đứng đầu)
    display_order = ["Bóng Đá", "Bóng Rổ", "Bóng Chuyền", "Quần Vợt", "Bóng Bàn", "Thể Thao Khác"]

    m3u_lines = ["#EXTM3U\n"]

    for group in display_order:
        channels = grouped_channels.get(group, [])
        for ch in channels:
            m3u_lines.append(ch["inf"])
            m3u_lines.append(ch["url"] + "\n")

    # Ghi ra tệp playlist.m3u
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

if __name__ == "__main__":
    fetch_and_generate_m3u()
    
