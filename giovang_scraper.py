import json
import sys
import requests

# API target và Cloudflare Worker Proxy
API_TARGET = "https://live-api.keonhacaitp.one/storage/livestream/live.json"
WORKER_PROXY = f"https://vsc-proxy.sonnguyen90pro.workers.dev/?url={API_TARGET}"

TYPE_MAP = {
    "football": "Bóng đá",
    "basketball": "Bóng rổ",
    "rugby": "Bóng bầu dục / NFL",
    "bongchay": "Bóng chày",
    "caulong": "Cầu lông / Trái cầu",
}

def get_group_title(sport_type, league_title=""):
    return TYPE_MAP.get(str(sport_type).lower(), league_title or "Giờ Vàng TV")

def generate_m3u():
    print("Đang lấy dữ liệu Giờ Vàng TV qua Worker Proxy...")
    response = requests.get(WORKER_PROXY, timeout=15)
    response.raise_for_status()
    
    res_json = response.json()
    data = res_json.get("response", []) if isinstance(res_json, dict) else []
    
    # IN TOÀN BỘ CẤU TRÚC JSON CỦA 2 TRẬN ĐẦU TIÊN RA LOG ĐỂ SOI
    print("\n" + "="*20 + " GIỜ VÀNG API RAW DATA " + "="*20)
    if data:
        print(json.dumps(data[:2], indent=2, ensure_ascii=False))
    else:
        print("Không lấy được dữ liệu trận đấu!")
    print("="*60 + "\n")

    m3u_content = "#EXTM3U\n\n"
    count = 0
    
    for match in data:
        teams = match.get("teams", {})
        home_name = teams.get("home", {}).get("name", "").strip()
        away_name = teams.get("away", {}).get("name", "").strip()
        
        if not home_name or not away_name:
            continue
            
        match_name = f"{home_name} vs {away_name}"
        logo_url = teams.get("home", {}).get("logo", "")
        sport_type = match.get("type", "")
        league_title = match.get("league", {}).get("title", "")
        group_title = get_group_title(sport_type, league_title)
        
        time_raw = match.get("time", "")[:5]
        day_month = match.get("day_month", "")
        time_str = f"{time_raw} {day_month}".strip()

        # Tạm thời để link no-signal trong lúc lấy log
        stream_url = "https://freem3u.xyz/static/no-signal/low.m3u8"

        m3u_content += f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="{group_title}" , 🟢 {time_str} ⚽ {match_name} [hls]\n'
        m3u_content += f'{stream_url}\n\n'
        count += 1
        
    with open("giovang.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)
    print(f"Đã xuất file giovang.m3u tạm thời.")

if __name__ == "__main__":
    try:
        generate_m3u()
    except Exception as e:
        print(f"Lỗi khi chạy script Giờ Vàng: {e}", file=sys.stderr)
        sys.exit(1)
        
