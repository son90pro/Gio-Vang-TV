import requests

SOURCE_URL = "https://thtt.pages.dev/tttt.m3u"

def fetch_and_generate_m3u():
    print(f"Đang tải danh sách trực tiếp từ nguồn: {SOURCE_URL}")
    try:
        res = requests.get(SOURCE_URL, timeout=15)
        if res.status_code == 200:
            content = res.text
            
            # Ghi nội dung playlist chuẩn vào tệp đích
            with open("playlist.m3u", "w", encoding="utf-8") as f:
                f.write(content)
            
            # Đếm số lượng kênh dựa trên thẻ #EXTINF
            channels_count = sum(1 for line in content.splitlines() if line.startswith("#EXTINF:"))
            print(f"Đã cập nhật playlist thành công với tổng số {channels_count} kênh!")
        else:
            print(f"Không thể tải dữ liệu, mã lỗi: {res.status_code}")
    except Exception as e:
        print(f"Lỗi kết nối khi tải playlist: {e}")

if __name__ == "__main__":
    fetch_and_generate_m3u()
