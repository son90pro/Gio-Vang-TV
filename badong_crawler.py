# -*- coding: utf-8 -*-
"""
BÁ ĐÓNG Engine - Standalone M3U Exporter
"""

import json
import logging
import os
import re
import ssl
import urllib.parse
import urllib.request
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("badong_crawler")

# --- DỮ LIỆU ĐÃ MÃ HÓA TỪ CODE CỦA ANH ---
_T1 = [50, 46, 46, 42, 41, 96, 117, 117, 46, 50, 46, 46, 116, 42, 59, 61, 63, 41, 116, 62, 63, 44, 117, 46, 46, 46, 46, 116, 55, 105, 47]
_T2 = [50, 46, 46, 42, 41, 96, 117, 117, 34, 63, 55, 46, 44, 116, 42, 59, 61, 63, 41, 116, 62, 63, 44, 117, 41, 53, 41, 117, 54, 117, 98, 14, 16, 20, 14, 20, 99, 16, 14, 14]

def _shield_resolve(data_ints, mask=0x5A):
    return "".join(chr(b ^ mask) for b in data_ints)

TIER1_DEFAULT_URL = _shield_resolve(_T1)
TIER2_DEFAULT_URL = _shield_resolve(_T2)

_REF_DATA = [33, 120, 54, 51, 44, 63, 104, 116, 62, 53, 55, 59, 51, 52, 57, 62, 52, 116, 57, 57, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 34, 54, 32, 116, 62, 53, 55, 59, 51, 52, 49, 43, 46, 116, 57, 57, 117, 120, 118, 120, 54, 51, 44, 63, 104, 116, 42, 40, 53, 104, 57, 62, 52, 54, 51, 44, 63, 116, 57, 53, 55, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 34, 54, 32, 116, 62, 53, 55, 59, 51, 52, 49, 43, 46, 116, 57, 57, 117, 120, 118, 120, 54, 51, 44, 63, 104, 116, 32, 47, 52, 62, 40, 51, 34, 55, 63, 62, 51, 59, 42, 51, 42, 63, 54, 51, 52, 63, 116, 57, 53, 55, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 34, 54, 32, 116, 62, 53, 55, 59, 51, 52, 49, 43, 46, 116, 57, 57, 117, 120, 118, 120, 44, 107, 116, 54, 51, 44, 63, 41, 46, 40, 63, 59, 55, 56, 53, 52, 61, 116, 46, 44, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 34, 54, 32, 116, 62, 53, 55, 59, 51, 52, 49, 43, 46, 116, 57, 57, 117, 120, 118, 120, 34, 54, 32, 116, 62, 53, 55, 59, 51, 52, 49, 43, 46, 116, 57, 57, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 34, 54, 32, 116, 62, 53, 55, 59, 51, 52, 49, 43, 46, 116, 57, 57, 117, 120, 118, 120, 99, 107, 42, 116, 62, 53, 55, 59, 51, 52, 49, 43, 46, 116, 57, 57, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 99, 107, 42, 116, 62, 53, 55, 59, 51, 52, 49, 43, 46, 116, 57, 57, 117, 120, 118, 120, 54, 51, 44, 63, 106, 111, 116, 55, 63, 47, 52, 61, 116, 59, 42, 42, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 57, 53, 54, 59, 46, 44, 109, 109, 116, 54, 51, 44, 63, 117, 120, 118, 120, 54, 51, 44, 63, 106, 111, 116, 55, 51, 63, 49, 61, 53, 116, 59, 42, 42, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 57, 53, 54, 59, 46, 44, 109, 109, 116, 54, 51, 44, 63, 117, 120, 118, 120, 41, 46, 59, 116, 44, 52, 40, 63, 41, 116, 57, 53, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 41, 53, 57, 53, 54, 51, 44, 63, 42, 116, 57, 44, 117, 120, 118, 120, 42, 47, 54, 54, 116, 52, 51, 47, 63, 41, 116, 54, 51, 44, 63, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 41, 47, 46, 56, 53, 52, 61, 116, 52, 63, 46, 117, 120, 118, 120, 42, 47, 54, 54, 116, 52, 51, 47, 40, 116, 54, 51, 44, 63, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 41, 47, 46, 56, 53, 52, 61, 116, 52, 63, 46, 117, 120, 118, 120, 41, 47, 46, 56, 53, 52, 61, 116, 52, 63, 46, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 41, 47, 46, 56, 53, 52, 61, 116, 52, 63, 46, 117, 120, 118, 120, 60, 54, 44, 116, 54, 59, 47, 46, 50, 59, 51, 46, 44, 116, 57, 57, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 41, 98, 46, 44, 57, 49, 57, 116, 46, 53, 42, 117, 120, 118, 120, 50, 54, 41, 116, 54, 59, 47, 46, 50, 59, 51, 46, 44, 116, 57, 57, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 41, 98, 46, 44, 57, 49, 57, 116, 46, 53, 42, 117, 120, 118, 120, 41, 46, 55, 99, 63, 63, 105, 110, 108, 109, 104, 109, 109, 107, 98, 116, 41, 46, 40, 63, 59, 55, 116, 50, 62, 42, 54, 59, 35, 54, 51, 52, 49, 116, 57, 53, 55, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 54, 51, 44, 63, 116, 57, 50, 47, 53, 51, 57, 50, 51, 63, 52, 116, 46, 44, 117, 120, 118, 120, 41, 46, 55, 99, 63, 63, 105, 110, 108, 109, 104, 109, 109, 107, 98, 116, 60, 42, 54, 59, 35, 116, 50, 62, 42, 54, 59, 35, 54, 51, 52, 49, 116, 57, 53, 55, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 54, 51, 44, 63, 116, 57, 50, 47, 53, 51, 57, 50, 51, 63, 52, 116, 46, 44, 117, 120, 118, 120, 45, 46, 35, 51, 106, 111, 104, 111, 116, 63, 62, 61, 63, 55, 59, 34, 57, 62, 52, 116, 53, 40, 61, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 41, 49, 116, 55, 63, 62, 51, 59, 41, 46, 59, 46, 51, 53, 52, 116, 54, 51, 44, 63, 117, 120, 118, 120, 42, 47, 54, 54, 116, 62, 51, 61, 51, 46, 59, 54, 57, 62, 52, 116, 52, 63, 46, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 42, 50, 59, 54, 59, 52, 61, 116, 54, 51, 44, 63, 117, 120, 118, 120, 42, 47, 54, 54, 107, 116, 62, 51, 61, 51, 46, 59, 54, 57, 62, 52, 116, 52, 63, 46, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 42, 50, 59, 54, 59, 52, 61, 116, 54, 51, 44, 63, 117, 120, 118, 120, 54, 51, 54, 51, 44, 63, 107, 116, 63, 47, 116, 57, 57, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 42, 50, 59, 54, 59, 52, 61, 116, 54, 51, 44, 63, 117, 120, 118, 120, 63, 56, 59, 57, 54, 53, 60, 63, 52, 116, 53, 40, 61, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 54, 51, 44, 63, 41, 42, 53, 40, 46, 116, 51, 53, 116, 44, 52, 117, 120, 118, 120, 45, 52, 57, 62, 52, 50, 54, 41, 119, 61, 54, 53, 56, 59, 54, 116, 63, 56, 59, 57, 54, 53, 60, 63, 52, 116, 53, 40, 61, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 54, 51, 44, 63, 41, 42, 53, 40, 46, 116, 51, 53, 116, 44, 52, 117, 120, 118, 120, 57, 62, 52, 119, 61, 54, 53, 56, 59, 54, 116, 63, 56, 59, 57, 54, 53, 60, 63, 52, 116, 53, 40, 61, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 54, 51, 44, 63, 41, 42, 53, 40, 46, 116, 51, 53, 116, 44, 52, 117, 120, 118, 120, 57, 62, 52, 107, 119, 61, 54, 53, 56, 59, 54, 116, 63, 56, 59, 57, 54, 53, 60, 63, 52, 116, 53, 40, 61, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 54, 51, 44, 63, 41, 42, 53, 40, 46, 116, 51, 53, 116, 44, 52, 117, 120, 118, 120, 57, 62, 52, 60, 54, 44, 116, 34, 56, 62, 56, 53, 46, 44, 116, 54, 51, 44, 63, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 54, 51, 44, 63, 41, 42, 53, 40, 46, 116, 51, 53, 116, 44, 52, 117, 120, 118, 120, 57, 62, 52, 50, 54, 41, 116, 34, 56, 62, 56, 53, 46, 44, 116, 54, 51, 44, 63, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 54, 51, 44, 63, 41, 42, 53, 40, 46, 116, 51, 53, 116, 44, 52, 117, 120, 118, 120, 54, 51, 44, 63, 104, 116, 32, 49, 46, 41, 44, 59, 116, 59, 42, 42, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 54, 51, 44, 63, 41, 42, 53, 40, 46, 116, 51, 53, 116, 44, 52, 117, 120, 118, 120, 42, 54, 59, 35, 56, 59, 57, 49, 116, 54, 51, 44, 63, 46, 54, 106, 106, 107, 116, 57, 53, 55, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 54, 51, 44, 63, 41, 42, 53, 40, 46, 116, 51, 53, 116, 44, 52, 117, 120, 118, 120, 63, 43, 40, 104, 50, 62, 59, 40, 34, 60, 54, 51, 44, 116, 44, 57, 62, 52, 116, 57, 54, 53, 47, 62, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 60, 40, 63, 63, 55, 105, 47, 116, 34, 35, 32, 117, 120, 118, 120, 60, 40, 63, 63, 55, 105, 47, 116, 34, 35, 32, 120, 96, 120, 50, 46, 46, 42, 41, 96, 117, 117, 60, 40, 63, 63, 55, 105, 47, 116, 34, 35, 32, 117, 120, 39]
REFERRER_REGISTRY = json.loads("".join(chr(b ^ 0x5A) for b in _REF_DATA))

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
IOS_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"

def get_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def is_fifa_channel(title, group_name=""):
    check_str = f"{title} {group_name}".lower()
    if "fifa" in check_str:
        return True
    return False

def is_blacklisted_placeholder(url, title=""):
    if not url:
        return True
    u_lower = url.lower()
    t_lower = title.lower()
    if "no-signal" in u_lower or "static/no-signal" in u_lower:
        return True
    if "updated " in t_lower and "freem3u.xyz" in u_lower:
        return True
    return False

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
            group = curr_attrs.get("group", "")
            logo = curr_attrs.get("logo", "")
            
            if is_fifa_channel(title, group) or is_blacklisted_placeholder(url, title):
                curr_attrs = {}
                curr_title = ""
                continue
                
            items.append({
                "title": title,
                "group": group,
                "url": url,
                "logo": logo,
                "source_tier": source_tier
            })
            curr_attrs = {}
            curr_title = ""
    return items

def fetch_playlist_data():
    ctx = get_ssl_context()
    all_items = []
    
    # 1. Thử cào Tier 1
    try:
        logger.info(f"Đang kết nối Tier 1: {TIER1_DEFAULT_URL}")
        req = urllib.request.Request(TIER1_DEFAULT_URL, headers={"User-Agent": DEFAULT_UA})
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            items = parse_m3u_text(content, source_tier="Tier 1")
            all_items.extend(items)
            logger.info(f"Lấy thành công {len(items)} kênh từ Tier 1.")
    except Exception as e:
        logger.warning(f"Lỗi khi cào Tier 1: {e}")

    # 2. Thử cào Tier 2
    try:
        logger.info(f"Đang kết nối Tier 2: {TIER2_DEFAULT_URL}")
        req = urllib.request.Request(TIER2_DEFAULT_URL, headers={"User-Agent": DEFAULT_UA})
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            items = parse_m3u_text(content, source_tier="Tier 2")
            all_items.extend(items)
            logger.info(f"Lấy thành công {len(items)} kênh từ Tier 2.")
    except Exception as e:
        logger.warning(f"Lỗi khi cào Tier 2: {e}")

    return all_items

def save_to_m3u(items, filename="playlist.m3u"):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n\n")
            for item in items:
                extinf = f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{item["group"]}" , {item["title"]}\n'
                f.write(extinf)
                f.write(f'{item["url"]}\n\n')
        logger.info(f"Đã xuất thành công file {filename} với tổng số {len(items)} kênh hợp lệ!")
    except Exception as e:
        logger.error(f"Lỗi khi ghi file M3U: {e}")

if __name__ == "__main__":
    print("=== BẮT ĐẦU CÀO DỮ LIỆU TỪ ENGINE BÁ ĐÓNG ===")
    channels = fetch_playlist_data()
    if channels:
        save_to_m3u(channels, "playlist.m3u")
    else:
        print("Không thu thập được kênh nào hoặc các nguồn đang ngoại tuyến.")

