# -*- coding: utf-8 -*-
"""
BÁ ĐÓNG Engine - Fixed Sport M3U Exporter
"""

import json
import logging
import os
import re
import ssl
import unicodedata
import urllib.parse
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("badong_crawler")

# --- DỮ LIỆU ĐÃ MÃ HÓA TỪ ENGINE ---
_T1 = [50, 46, 46, 42, 41, 96, 117, 117, 46, 50, 46, 46, 116, 42, 59, 61, 63, 41, 116, 62, 63, 44, 117, 46, 46, 46, 46, 116, 55, 105, 47]
_T2 = [50, 46, 46, 42, 41, 96, 117, 117, 34, 63, 55, 46, 44, 116, 42, 59, 61, 63, 41, 116, 62, 63, 44, 117, 41, 53, 41, 117, 54, 117, 98, 14, 16, 20, 14, 20, 99, 16, 14, 14]

def _shield_resolve(data_ints, mask=0x5A):
    return "".join(chr(b ^ mask) for b in data_ints)

TIER1_DEFAULT_URL = _shield_resolve(_T1)
TIER2_DEFAULT_URL = _shield_resolve(_T2)

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def get_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def is_fifa_channel(title, group_name=""):
    check_str = f"{title} {group_name}".lower()
    return "fifa" in check_str

def is_blacklisted_placeholder(url, title=""):
    """Cho phép đi qua cả link no-signal để giữ lại các trận chưa phát sóng"""
    if not url:
        return True
    return False

def detect_sport(title, group_name=""):
    t_lower = f"{title} {group_name}".lower()
    
    # Loại trừ các kênh phim ảnh, truyền hình tổng hợp không phải thể thao
    if any(kw in t_lower for kw in ["movie", "phim", "hbo", "vtv", "vov", "cartoon", "thời sự", "tin tức", "news"]):
        return None

    if "⚽" in title or "football" in t_lower or "bóng đá" in t_lower or " vs " in t_lower or "premier league" in t_lower or "la liga" in t_lower:
        return "Bóng đá"
    if "🏀" in title or "basketball" in t_lower or "bóng rổ" in t_lower or "nba" in t_lower:
        return "Bóng rổ"
    if "🎾" in title or "tennis" in t_lower or "quần vợt" in t_lower or "atp" in t_lower or "wta" in t_lower:
        return "Tennis"
    if "🥊" in title or "ufc" in t_lower or "mma" in t_lower or "boxing" in t_lower or "võ thuật" in t_lower:
        return "Võ thuật & MMA"
    if "🏸" in title or "badminton" in t_lower or "cầu lông" in t_lower:
        return "Cầu lông"
    if "🎮" in title or "esports" in t_lower or "dota" in t_lower or "lol" in t_lower or "t1" in t_lower:
        return "Esports"
    if "🏐" in title or "volleyball" in t_lower or "bóng chuyền" in t_lower:
        return "Bóng chuyền"
    if "🎱" in title or "billiards" in t_lower or "snooker" in t_lower or "bi-a" in t_lower:
        return "Billiards & Bi-a"
    if "🏁" in title or "f1" in t_lower or "formula" in t_lower or "motogp" in t_lower or "đua xe" in t_lower:
        return "Đua xe"
        
    return None

def slugify(text):
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text).lower()
    return re.sub(r'\s+', '_', text.strip())

def parse_m3u_text(content, source_tier="Tier 1"):
    items = []
    lines = content.splitlines()
    curr_attrs = {}
    curr_title = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith("#EXTINF:"):
            curr_attrs = {}
            m_logo = re.search(r'tvg-logo="([^"]*)"', line)
            curr_attrs["logo"] = m_logo.group(1) if m_logo else ""
            
            m_group = re.search(r'group-title="([^"]*)"', line)
            curr_attrs["group"] = m_group.group(1) if m_group else ""
            
            idx = line.rfind(",")
            if idx != -1:
                curr_title = line[idx+1:].strip()
            else:
                curr_title = ""
        elif not line.startswith("#") and (line.startswith("http://") or line.startswith("https://")):
            url = line
            title = curr_title or "Trực tiếp Thể Thao"
            group = curr_attrs.get("group", "Giờ Vàng TV")
            logo = curr_attrs.get("logo", "")
            
            if is_fifa_channel(title, group) or is_blacklisted_placeholder(url, title):
                curr_attrs = {}
                curr_title = ""
                continue
                
            sport_category = detect_sport(title, group)
            if not sport_category:
                curr_attrs = {}
                curr_title = ""
                continue
                
            items.append({
                "title": title,
                "group": group,
                "sport": sport_category,
                "url": url,
                "logo": logo
            })
            curr_attrs = {}
            curr_title = ""
    return items

def fetch_playlist_data():
    ctx = get_ssl_context()
    all_items = []
    
    for url_tier, name in [(TIER1_DEFAULT_URL, "Tier 1"), (TIER2_DEFAULT_URL, "Tier 2")]:
        try:
            logger.info(f"Đang kết nối {name}: {url_tier}")
            req = urllib.request.Request(url_tier, headers={"User-Agent": DEFAULT_UA})
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                content = resp.read().decode("utf-8", errors="ignore")
                items = parse_m3u_text(content, source_tier=name)
                all_items.extend(items)
                logger.info(f"Lấy thành công {len(items)} kênh thể thao từ {name}.")
        except Exception as e:
            logger.warning(f"Lỗi khi cào {name}: {e}")

    return all_items

def save_split_playlists(items):
    sports_dict = {}
    for item in items:
        sport = item["sport"]
        if sport not in sports_dict:
            sports_dict[sport] = []
        sports_dict[sport].append(item)
    
    # Xóa file m3u cũ
    for f_name in os.listdir("."):
        if f_name.endswith(".m3u"):
            try:
                os.remove(f_name)
            except:
                pass

    for sport, sport_items in sports_dict.items():
        filename = f"{slugify(sport)}.m3u"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n\n")
                for item in sport_items:
                    f.write(f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{item["group"]}" , {item["title"]}\n')
                    f.write(f'{item["url"]}\n\n')
            logger.info(f"Đã tạo file: {filename} ({len(sport_items)} kênh)")
        except Exception as e:
            logger.error(f"Lỗi khi ghi file {filename}: {e}")

    try:
        with open("tat_ca_the_thao.m3u", "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n\n")
            for item in items:
                f.write(f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{item["sport"]}" , {item["title"]}\n')
                f.write(f'{item["url"]}\n\n')
        logger.info(f"Đã tạo file tổng: tat_ca_the_thao.m3u ({len(items)} kênh)")
    except Exception as e:
        logger.error(f"Lỗi khi ghi file tổng: {e}")

if __name__ == "__main__":
    print("=== BẮT ĐẦU CÀO VÀ TÁCH FILE M3U ===")
    channels = fetch_playlist_data()
    if channels:
        save_split_playlists(channels)
        print("Hoàn tất tách file M3U thành công!")
    else:
        print("Không tìm thấy kênh nào phù hợp.")
