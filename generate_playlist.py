import requests

# Sử dụng nguồn danh sách phát tổng hợp chuẩn, đầy đủ trận và chạy ổn định
SOURCE_URL = "https://thtt.pages.dev/tttt.m3u"

def fetch_and_generate_m3u():
    print(f"Đang tải danh sách từ nguồn chuẩn: {SOURCE_URL}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(SOURCE_URL, headers=headers, allow_redirects=True, timeout=15)
        if res.status_code == 200:
            content = res.text
            
            # Ghi nội dung playlist chuẩn vào tệp playlist.m3u cho tivi
            with open("playlist.m3u", "w", encoding="utf-8") as f:
                f.write(content)
            
            channels_count = sum(1 for line in content.splitlines() if line.startswith("#EXTINF:"))
            print(f"Đã cập nhật playlist thành công với tổng số {channels_count} kênh!")
        else:
            print(f"Không thể tải dữ liệu, mã lỗi HTTP: {res.status_code}")
    except Exception as e:
        print(f"Lỗi kết nối khi tải playlist: {e}")

if __name__ == "__main__":
    fetch_and_generate_m3u()
