import json
import re
import requests

def get_sport_icon(text=""):
    t = str(text).lower()
    if any(k in t for k in ['tennis', 'quần vợt']):
        return "🥎"
    elif any(k in t for k in ['basketball', 'bóng rổ']):
        return "🏀"
    elif any(k in t for k in ['volleyball', 'bóng chuyền']):
        return "🏐"
    elif any(k in t for k in ['baseball', 'bóng chày', 'kt wiz']):
        return "⚾"
    elif any(k in t for k in ['table tennis', 'ping pong', 'bóng bàn', 'lind']):
        return "🏓"
    elif any(k in t for k in ['lol', 'game', 'esports', 'dota', 'csgo']):
        return "🎮"
    elif any(k in t for k in ['badminton', 'cầu lông']):
        return "🏸"
    else:
        return "⚽"

def extract_matches(node, results):
    if isinstance(node, list):
        for item in node:
            extract_matches(item, results)
    elif isinstance(node, dict):
        if any(k in node for k in ['home_team', 'home', 'away_team', 'away', 'match_name', 'teams', 'play_url', 'm3u8', 'time']):
            results.append(node)
        for k, v in node.items():
            if isinstance(v, (list, dict)):
                extract_matches(v, results)

def generate_m3u_and_json():
    target_url = "https://live-api.keonhacaitp.one/storage/livestream/live.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://giovang.love/"
    }

    try:
        print("Đang kết nối lấy dữ liệu Giờ Vàng TV...")
        response = requests.get(target_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            with open('giovang.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            m3u_content = "#EXTM3U\n\n"
            count = 0
            seen_links = set()

            matches_list = []
            extract_matches(data, matches_list)
            print(f"Tìm thấy tổng cộng {len(matches_list)} mục trận đấu từ Giờ Vàng TV.")

            for match in matches_list:
                if not isinstance(match, dict):
                    continue

                # 1. Bóc tách đội nhà (Home)
                home_data = match.get("home_team") or match.get("home") or match.get("home_name") or ""
                home_name = ""
                home_logo = ""
                if isinstance(home_data, dict):
                    home_name = home_data.get("name", "")
                    home_logo = home_data.get("logo", "")
                elif isinstance(home_data, str):
                    home_name = home_data

                # 2. Bóc tách đội khách (Away)
                away_data = match.get("away_team") or match.get("away") or match.get("away_name") or ""
                away_name = ""
                away_logo = ""
                if isinstance(away_data, dict):
                    away_name = away_data.get("name", "")
                    away_logo = away_data.get("logo", "")
                elif isinstance(away_data, str):
                    away_name = away_data

                raw_title = match.get("title") or match.get("name") or match.get("match_name") or ""
                
                teams_str = ""
                if home_name and away_name:
                    teams_str = f"{home_name} vs {away_name}"
                elif " vs " in raw_title.lower():
                    teams_str = raw_title
                else:
                    teams_str = raw_title if raw_title and len(raw_title) > 3 else ""

                if not teams_str:
                    continue  # Bỏ qua nếu không xác định được tên cặp đấu

                # 3. Lấy thời gian (Giờ & Ngày tháng)
                time_val = match.get("time") or match.get("start_time") or match.get("hour") or match.get("match_time") or ""
                date_val = match.get("date") or match.get("match_date") or ""
                
                time_str = "14:45"
                if time_val:
                    t_match = re.search(r'(\d{2}[:h]\d{2})', str(time_val))
                    if t_match:
                        time_str = t_match.group(1).replace('h', ':')
                    else:
                        time_str = str(time_val)[:5]

                date_str = "03/11"
                if date_val:
                    d_match = re.search(r'(\d{2}[-/]\d{2})', str(date_val))
                    if d_match:
                        date_str = d_match.group(1).replace('-', '/')

                # 4. Tên BLV chuẩn
                blv_name = match.get("blv") or match.get("caster") or match.get("server_name") or match.get("author") or "gtv"
                if isinstance(blv_name, dict):
                    blv_name = blv_name.get("name", "gtv")
                blv_str = str(blv_name).lower().strip()
                blv_tag = f"blv-{blv_str}" if not blv_str.startswith("blv") else blv_str

                # 5. Logo & Icon thể thao
                tournament = match.get("tournament") or match.get("league") or match.get("competition") or ""
                sport_icon = get_sport_icon(str(tournament) + " " + teams_str)
                
                logo = home_logo or match.get("logo") or match.get("icon") or ""
                if not logo or not str(logo).startswith("http"):
                    logo = "https://images.keovip88.net/images/teams/default.png"

                # 6. Bóc tách link stream thực tế (m3u8, play_url, flv...)
                streams = []
                for u_key in ["play_url", "url", "stream_url", "m3u8", "link", "flv", "live_url"]:
                    val = match.get(u_key)
                    if isinstance(val, str) and val.startswith("http"):
                        streams.append((val, blv_tag))

                for sk in ["streams", "links", "servers", "sources", "quality"]:
                    arr = match.get(sk)
                    if isinstance(arr, list):
                        for s in arr:
                            if isinstance(s, str) and s.startswith("http"):
                                streams.append((s, blv_tag))
                            elif isinstance(s, dict):
                                s_url = s.get("url") or s.get("link") or s.get("m3u8") or s.get("flv") or ""
                                s_name = s.get("name") or s.get("title") or blv_tag
                                if s_url.startswith("http"):
                                    streams.append((s_url, s_name))

                # Fallback tìm kiếm link stream dạng m3u8 / flv bên trong dict
                if not streams:
                    for sub_k, sub_v in match.items():
                        if isinstance(sub_v, str) and sub_v.startswith("http") and any(ext in sub_v.lower() for ext in ['.m3u8', '.flv', 'vcdn.cloud']):
                            streams.append((sub_v, blv_tag))

                # Nếu trận sắp diễn ra chưa có link stream live, dùng link placeholder để hiển thị đầy đủ trên TV
                if not streams:
                    streams.append(("https://freem3u.xyz/static/no-signal/low.m3u8", blv_tag))

                # Ghi ra file M3U theo đúng chuẩn mẫu yêu cầu
                for s_url, tag in streams:
                    if s_url not in seen_links:
                        seen_links.add(s_url)

                        display_title = f"🟢 {time_str} {date_str} {sport_icon} {teams_str} ({tag}) [hls]"

                        m3u_content += f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV" , {display_title}\n'
                        m3u_content += '#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Mobile Safari/537.36\n'
                        m3u_content += '#EXTVLCOPT:http-referrer=https://giovang.love/\n'
                        m3u_content += f'{s_url}\n\n'
                        count += 1

            with open('playlist.m3u', 'w', encoding='utf-8') as f:
                f.write(m3u_content)
                
            print(f"Đã tạo xong Giờ Vàng TV với {count} luồng chuẩn xác tuyệt đối!")
            
        else:
            print(f"Lỗi HTTP: {response.status_code}")
            
    except Exception as e:
        print(f"Lỗi: {e}")

if __name__ == "__main__":
    generate_m3u_and_json()
    
