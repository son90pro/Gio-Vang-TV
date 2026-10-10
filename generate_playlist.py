import requests

def fetch_and_generate_m3u():
    source_url = "https://tinyurl.com/ttthethao6"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        res = requests.get(source_url, headers=headers, timeout=10)
        if res.status_code != 200:
            print("Không tải được dữ liệu từ nguồn!")
            return
        lines = res.text.splitlines()
    except Exception as e:
        print(f"Lỗi kết nối: {e}")
        return

    channels = []
    current_inf = ""
    
    # Đọc và bóc tách danh sách các trận đấu đang phát sóng
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF"):
            current_inf = line
        elif line.startswith("http") and "vcdn.cloud" in line:
            if current_inf:
                channels.append({
                    "inf": current_inf,
                    "url": line
                })
                current_inf = ""

    # Phân nhóm các môn thể thao và ưu tiên Bóng Đá lên đầu
    grouped = {
        "Bóng Đá": [],
        "Bóng Rổ": [],
        "Bóng Chuyền": [],
        "Quần Vợt": [],
        "Bóng Bàn": [],
        "Thể Thao Khác": []
    }

    for ch in channels:
        inf = ch["inf"]
        if "⚽" in inf:
            group = "Bóng Đá"
        elif "🏀" in inf:
            group = "Bóng Rổ"
        elif "🏐" in inf:
            group = "Bóng Chuyền"
        elif "🥎" in inf or "🎾" in inf:
            group = "Quần Vợt"
        elif "🏓" in inf:
            group = "Bóng Bàn"
        else:
            group = "Thể Thao Khác"

        # Gán group-title chuẩn để ứng dụng IPTV tự động phân loại giao diện
        if 'group-title="' in inf:
            parts = inf.split('group-title="')
            if len(parts) > 1:
                rest = parts[1].split('"', 1)
                ch["inf"] = f'{parts[0]}group-title="{group}"{rest[1]}'
        
        grouped[group].append(ch)

    # Thứ tự hiển thị các nhóm trên tivi (Bóng Đá luôn ở vị trí đầu tiên)
    display_order = ["Bóng Đá", "Bóng Rổ", "Bóng Chuyền", "Quần Vợt", "Bóng Bàn", "Thể Thao Khác"]

    m3u_lines = ["#EXTM3U\n"]
    for group in display_order:
        for ch in grouped.get(group, []):
            m3u_lines.append(ch["inf"])
            m3u_lines.append(ch["url"] + "\n")

    # Lưu kết quả ra tệp playlist.m3u
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    print(f"Đã cập nhật playlist thành công với {len(channels)} kênh!")

if __name__ == "__main__":
    fetch_and_generate_m3u()
    
