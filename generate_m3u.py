import datetime
import json
import re
import ssl
import time
import urllib.request
import zoneinfo
from concurrent.futures import ThreadPoolExecutor, as_completed

TZ_VN = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Referer": "https://giovang.co/",
    "Origin": "https://giovang.co/",
}

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def fetch_json(url):
  sep = "&" if "?" in url else "?"
  full_url = f"{url}{sep}t={int(time.time())}"
  req = urllib.request.Request(full_url, headers=HEADERS)
  try:
    with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
      if resp.status == 200:
        text = resp.read().decode("utf-8", errors="ignore")
        return json.loads(text.replace("\\/", "/"))
  except Exception:
    pass
  return None


def find_room_id(match):
  """Quét tất cả ngóc ngách để lấy ID 10 chữ số dạng 179xxxxxxx chuẩn CDN"""
  # 1. Thử các key thông dụng
  for k in ["room_id", "fi", "live_id", "stream_id", "id"]:
    val = match.get(k)
    if val and str(val).isdigit() and len(str(val)) in [9, 10]:
      return str(val)

  # 2. Tìm trong mảng server / links
  servers = match.get("servers") or match.get("links") or []
  if isinstance(servers, list):
    for s in servers:
      if isinstance(s, dict):
        sid = s.get("room_id") or s.get("id") or s.get("stream_id")
        if sid and str(sid).isdigit() and len(str(sid)) in [9, 10]:
          return str(sid)

  # 3. Quét Regex thô tìm chuỗi ID bắt đầu bằng 179
  raw_str = json.dumps(match)
  match_ids = re.findall(r"\b(179\d{7})\b", raw_str)
  if match_ids:
    return match_ids[0]

  return None


def get_emoji(sport, league, title):
  text = f"{sport} {league} {title}".lower()
  if any(k in text for k in ["basketball", "bóng rổ"]):
    return "🏀"
  if any(k in text for k in ["volleyball", "bóng chuyền"]):
    return "🏐"
  if any(k in text for k in ["tennis", "quần vợt", "open"]):
    return "🥎"
  if any(k in text for k in ["esport", "lol", "dota", "valorant"]):
    return "🎮"
  if any(k in text for k in ["billiards", "bida", "bi a", "pool"]):
    return "🎱"
  if any(k in text for k in ["f1", "formula"]):
    return "[formula1]"
  if any(k in text for k in ["mma", "boxing", "one friday", "ufc"]):
    return "🥊"
  return "⚽"


def main():
  now_vn = datetime.datetime.now(TZ_VN)
  today_str = now_vn.strftime("%d-%m-%Y")

  sources = [
      "https://live-api.keonhacaitp.one/storage/livestream/live.json",
      "https://api.giovang.co/storage/livestream/live.json",
      "https://live-api.keonhacaitp.one/storage/livestream/home.json",
      "https://live-api.keonhacaitp.one/storage/livestream/match.json",
      f"https://live-api.keonhacaitp.one/storage/livestream/date/{today_str}.json",
  ]

  raw_matches = []
  with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(fetch_json, u) for u in sources]
    for f in as_completed(futures):
      res = f.result()
      if res:
        items = (
            res.get("response")
            or res.get("data")
            or (res if isinstance(res, list) else [])
        )
        if isinstance(items, list):
          raw_matches.extend([i for i in items if isinstance(i, dict)])

  entries = []
  seen = set()

  print("=== CHECK TRỰC TIẾP KẾT QUẢ CÀO ===")
  for match in raw_matches:
    room_id = find_room_id(match)

    # Lấy tên trận
    teams = match.get("teams") if isinstance(match.get("teams"), dict) else {}
    h = (
        (teams.get("home") or match.get("home") or {}).get("name")
        if isinstance(teams.get("home") or match.get("home"), dict)
        else (match.get("home_name") or "")
    )
    a = (
        (teams.get("away") or match.get("away") or {}).get("name")
        if isinstance(teams.get("away") or match.get("away"), dict)
        else (match.get("away_name") or "")
    )

    match_name = (
        f"{h.strip()} vs {a.strip()}"
        if h and a
        else str(match.get("title") or match.get("name") or "Trận đấu").strip()
    )

    key = f"{match_name}_{match.get('time_start','')}"
    if key in seen:
      continue
    seen.add(key)

    # Tên BLV
    blv = match.get("blv") or match.get("commentator") or ""
    if isinstance(blv, list) and blv:
      blv = blv[0]
    if isinstance(blv, dict):
      blv = blv.get("name") or blv.get("nickname") or ""
    blv_str = (
        f" ({str(blv).strip()})"
        if blv and str(blv).strip().lower() not in ["none", "null"]
        else ""
    )

    # Thời gian & Trạng thái LIVE
    ts = match.get("time_start") or match.get("timestamp")
    time_str = now_vn.strftime("%H:%M %d/%m")
    is_live = False

    if ts:
      try:
        ts_int = int(ts) // 1000 if int(ts) > 1e11 else int(ts)
        dt = datetime.datetime.fromtimestamp(ts_int, tz=TZ_VN)
        time_str = dt.strftime("%H:%M %d/%m")
        if dt <= now_vn + datetime.timedelta(minutes=30):
          is_live = True
      except Exception:
        pass
    else:
      is_live = True

    emoji = get_emoji(
        str(match.get("type", "")), str(match.get("league", "")), match_name
    )
    logo = (
        match.get("logo")
        or match.get("home_logo")
        or "https://giovang.co/favicon.ico"
    )

    if room_id and is_live:
      status = "🟢 "
      url = f"https://ftlh5sc02iliv.vcdn.cloud/{room_id}_hd/{room_id}_hd@720p.m3u8"
      print(f"✅ BẮT ĐƯỢC LIVE: {match_name} -> ID: {room_id}")
    else:
      status = ""
      url = "https://freem3u.xyz/static/no-signal/low.m3u8"
      print(f"⚪ CHƯA LIVE/KHÔNG ID: {match_name}")

    title = f"{status}{time_str} {emoji} {match_name}{blv_str} [hls]"
    entries.append((title, logo, url))

  # Ghi file M3U chuẩn 100%
  with open("playlist.m3u", "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n\n")
    for t, l, u in entries:
      f.write(
          f'#EXTINF:-1 tvg-logo="{l}" group-title="Giờ Vàng TV" ,'
          f" {t}\n{u}\n\n"
      )

  print(f"\n=== TỔNG CỘNG XUẤT {len(entries)} TRẬN VÀO FILE playlist.m3u ===")


if __name__ == "__main__":
  main()
    
