import datetime
import json
import time
import urllib.request
import zoneinfo

# API URLs
API_LIST = "https://live-api.keonhacaitp.one/storage/livestream/live.json"
API_DETAIL = (
    "https://live-api.keonhacaitp.one/storage/livestream/detail/{}.json"
)

# Headers giả lập Browser
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Android 16; Mobile; rv:156.0) Gecko/156.0 Firefox/156.0"
    ),
    "Referer": "https://giovang.rent/",
}

# Thứ tự ưu tiên môn thể thao & Tên hiển thị Group M3U
SPORT_PRIORITY = {
    "football": (1, "Bóng Đá"),
    "soccer": (1, "Bóng Đá"),
    "bongda": (1, "Bóng Đá"),
    "bongchuyen": (2, "Bóng Chuyền"),
    "volleyball": (2, "Bóng Chuyền"),
    "basketball": (3, "Bóng Rổ"),
    "bongro": (3, "Bóng Rổ"),
    "tennis": (4, "Quần Vợt"),
    "quanvot": (4, "Quần Vợt"),
    "esport": (5, "Esports"),
    "esports": (5, "Esports"),
    "bongban": (6, "Bóng Bàn"),
    "tabletennis": (6, "Bóng Bàn"),
}


def get_sport_info(sport_type):
    key = str(sport_type).lower().strip()
    return SPORT_PRIORITY.get(key, (99, "Thể Thao Khác"))


def fetch_json(url):
    # Thêm timestamp chống cache
    full_url = f"{url}?t={int(time.time())}"
    req = urllib.request.Request(full_url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"Lỗi khi tải URL {url}: {e}")
        return None


def format_vn_time(timestamp):
    if not timestamp:
        return "N/A"
    tz = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
    dt = datetime.datetime.fromtimestamp(timestamp, tz=tz)
    return dt.strftime("%H:%M %d/%m/%Y")


def main():
    data = fetch_json(API_LIST)
    if not data or data.get("code") != 0:
        print("Không thể lấy dữ liệu danh sách trận đấu.")
        return

    matches = data.get("response", [])

    # Sắp xếp theo ưu tiên Môn thể thao (Bóng đá lên đầu), sau đó theo thời gian
    matches.sort(
        key=lambda x: (
            get_sport_info(x.get("type", ""))[0],
            x.get("time_start", 0),
        )
    )

    m3u_lines = ["#EXTM3U"]

    for match in matches:
        sport_type = match.get("type", "")
        priority, group_title = get_sport_info(sport_type)

        match_id = match.get("id") or match.get("fi")
        league = match.get("league", {}).get("title", "Giải đấu")

        teams = match.get("teams", {})
        home_name = teams.get("home", {}).get("name", "Đội nhà").strip()
        away_name = teams.get("away", {}).get("name", "Đội khách").strip()
        home_logo = teams.get("home", {}).get("logo", "")

        blv_list = match.get("blv", [])
        blv_str = (
            f" [BLV: {', '.join(blv_list)}]" if blv_list else " [BLV: Không]"
        )

        time_vn = format_vn_time(match.get("time_start"))
        status = match.get("status", "LIVE")

        # Lấy luồng phát chi tiết từ API Detail
        detail_data = fetch_json(API_DETAIL.format(match_id))
        streams = []

        if detail_data and detail_data.get("code") == 0:
            resp_detail = detail_data.get("response", {})
            if isinstance(resp_detail, dict):
                links = resp_detail.get("links") or resp_detail.get(
                    "play_urls", []
                )
                if isinstance(links, list) and len(links) > 0:
                    for idx, link_item in enumerate(links):
                        if isinstance(link_item, dict):
                            q_name = (
                                link_item.get("name")
                                or link_item.get("quality")
                                or f"HD{idx+1}"
                            )
                            stream_url = (
                                link_item.get("url")
                                or link_item.get("link")
                                or link_item.get("m3u8")
                            )
                            if stream_url:
                                streams.append((q_name, stream_url))
                        elif isinstance(link_item, str):
                            streams.append((f"HD{idx+1}", link_item))
                elif resp_detail.get("play_url"):
                    streams.append(("FHD", resp_detail["play_url"]))

        # Nếu không lấy được luồng trực tiếp m3u8 từ Detail, fallback về trang player
        if not streams:
            streams.append(("Trực tiếp", f"https://giovang.rent/live/{match_id}"))

        # Ghi thông tin từng luồng vào M3U
        for quality, stream_url in streams:
            display_title = f"[{time_vn}] {home_name} vs {away_name} ({league}){blv_str} - [{status}] [{quality}]"
            extinf_header = f'#EXTINF:-1 tvg-logo="{home_logo}" group-title="{group_title}",{display_title}'

            m3u_lines.append(extinf_header)
            m3u_lines.append(stream_url)

    # Xuất file playlist.m3u
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(
        f"Đã cập nhật thành công {len(matches)} trận đấu vào file playlist.m3u"
    )


if __name__ == "__main__":
    main()
  
