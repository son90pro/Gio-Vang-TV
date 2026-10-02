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


def get_sport_emoji(sport_type="", league="", match_name=""):
  s = f"{sport_type} {league} {match_name}".lower()
  if any(k in s for k in ["basketball", "bóng rổ", "nba", "aces", "fever"]):
    return "🏀"
  if any(k in s for k in ["volleyball", "bóng chuyền"]):
    return "🏐"
  if any(k in s for k in ["baseball", "bóng chày", "braves", "phillies"]):
    return "⚾"
  if any(
      k in s for k in ["tennis", "quần vợt", "softball", "wta", "atp", "open"]
  ):
    return "🥎"
  if any(k in s for k in ["esport", "esports", "lol", "dota", "valorant"]):
    return "🎮"
  if any(k in s for k in ["billiards", "bida", "pool"]):
    return "🎱"
  if any(k in s for k in ["f1", "formula1", "grand prix", "formula 1"]):
    return "🏎️"
  if any(k in s for k in ["american football", "nfl", "steelers", "browns"]):
    return "🏈"
  return "⚽"


def clean_blv_name(blv_raw):
  if not blv_raw:
    return ""
  if isinstance(blv_raw, list):
    blv_raw = blv_raw[0] if blv_raw else ""
  if isinstance(blv_raw, dict):
    blv_raw = (
        blv_raw.get("name")
        or blv_raw.get("nickname")
        or blv_raw.get("title")
        or blv_raw.get("blv_name")
        or ""
    )

  name = str(blv_raw).strip().strip("()")
  if not name or name.lower() in ["none", "null", "undefined"]:
    return ""

  cleaned = re.sub(
      r"^(blv|commentator)[-_\s]*", "", name, flags=re.IGNORECASE
  ).strip()
  if cleaned:
    # Giữ nguyên chữ BLV nếu có sẵn từ API mẫu của anh
    if not name.lower().startswith("blv"):
      cleaned = f"BLV {cleaned}"
  return f" ({cleaned})" if cleaned else ""


def fetch_url(url, timeout=10):
  sep = "&" if "?" in url else "?"
  full_url = f"{url}{sep}t={int(time.time())}"
  req = urllib.request.Request(full_url, headers=HEADERS)
  try:
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
      if resp.status == 200:
        text = resp.read().decode("utf-8", errors="ignore")
        return text.replace("\\/", "/")
  except Exception:
    pass
  return None


def extract_room_id(match_obj):
  """Bóc tách chính xác room_id chuẩn 10 chữ số dạng 179xxxxxxx"""
  match_str = json.dumps(match_obj)

  # 1. Quét regex trực tiếp chuỗi room_id 10 chữ số trong toàn bộ JSON của trận
  ids = re.findall(r"\b(179\d{7})\b", match_str)
  if ids:
    return ids[0]

  # 2. Quét các dạng 10 chữ số bất kỳ bắt đầu bằng 17/18
  ids_gen = re.findall(r"\b(1[789]\d{7,8})\b", match_str)
  if ids_gen:
    return ids_gen[0]

  # 3. Quét thuộc tính room_id hoặc fi
  for key in ["room_id", "fi", "live_id", "id"]:
    val = match_obj.get(key)
    if val and str(val).isdigit() and len(str(val)) in [9, 10]:
      return str(val)

  return None


def main():
  now_vn = datetime.datetime.now(TZ_VN)

  # Các API chính chứa danh sách trận đấu
  api_sources = [
      "https://live-api.keonhacaitp.one/storage/livestream/live.json",
      "https://api.giovang.co/storage/livestream/live.json",
      "https://live-api.keonhacaitp.one/storage/livestream/home.json",
      "https://live-api.keonhacaitp.one/storage/livestream/match.json",
  ]

  today_str = now_vn.strftime("%d-%m-%Y")
  api_sources.append(
      f"https://live-api.keonhacaitp.one/storage/livestream/date/{today_str}.json"
  )

  raw_matches = []
  with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(fetch_url, url) for url in api_sources]
    for future in as_completed(futures):
      text = future.result()
      if text:
        try:
          data = json.loads(text)
          items = (
              data.get("response")
              or data.get("data")
              or (data if isinstance(data, list) else [])
          )
          if isinstance(items, list):
            for item in items:
              if isinstance(item, dict):
                raw_matches.append(item)
        except Exception:
          pass

  playlist_dict = {}

  for match in raw_matches:
    room_id = extract_room_id(match)

    # Chỉ xử lý các trận lấy được room_id (bỏ qua hoàn toàn no-signal)
    if not room_id:
      continue

    # Tái tạo link VCDN chuẩn xác theo file M3U mẫu
    stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{room_id}_hd/{room_id}_hd@720p.m3u8"

    # Xử lý Tên trận đấu
    teams = match.get("teams") if isinstance(match.get("teams"), dict) else {}
    home_obj = (
        teams.get("home") or match.get("home") or match.get("home_team") or {}
    )
    away_obj = (
        teams.get("away") or match.get("away") or match.get("away_team") or {}
    )

    home_name = (
        home_obj.get("name") if isinstance(home_obj, dict) else str(home_obj)
    ) or match.get("home_name", "")
    away_name = (
        away_obj.get("name") if isinstance(away_obj, dict) else str(away_obj)
    ) or match.get("away_name", "")

    if home_name and away_name and home_name != "None" and away_name != "None":
      match_name = f"{home_name.strip()} vs {away_name.strip()}"
    else:
      match_name = str(
          match.get("title") or match.get("name") or "Trận đấu"
      ).strip()

    # Xử lý Logo
    logo = (
        (home_obj.get("logo") if isinstance(home_obj, dict) else "")
        or match.get("home_logo")
        or match.get("logo")
        or ""
    )

    # Xử lý Thời gian
    ts = (
        match.get("time_start")
        or match.get("timestamp")
        or match.get("match_time")
    )
    time_str = ""
    if ts:
      try:
        ts_int = int(ts)
        if ts_int > 1e11:
          ts_int //= 1000
        dt = datetime.datetime.fromtimestamp(ts_int, tz=TZ_VN)
        time_str = dt.strftime("%H:%M %d/%m")
      except Exception:
        pass

    if not time_str:
      time_str = now_vn.strftime("%H:%M %d/%m")

    # BLV & Icon môn thể thao
    blv_raw = match.get("blv") or match.get("commentator") or ""
    blv_str = clean_blv_name(blv_raw)

    sport_type = (
        match.get("type")
        or match.get("sport_type")
        or match.get("category")
        or ""
    )
    league_obj = match.get("league") or match.get("tournament") or {}
    league_title = (
        league_obj.get("title") or league_obj.get("name") or ""
        if isinstance(league_obj, dict)
        else str(league_obj)
    )
    emoji = get_sport_emoji(str(sport_type), str(league_title), match_name)

    key = f"{room_id}"
    playlist_dict[key] = {
        "title": f"🟢 {time_str} {emoji} {match_name}{blv_str} [hls]",
        "logo": logo,
        "url": stream_url,
    }

  # Xuất file M3U
  m3u_lines = ["#EXTM3U\n"]
  for item in playlist_dict.values():
    m3u_lines.append(
        f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="Giờ Vàng TV" ,'
        f" {item['title']}"
    )
    m3u_lines.append(item["url"])
    m3u_lines.append("")

  with open("playlist.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(m3u_lines))

  print("Đã tạo file playlist.m3u chuẩn vcdn.cloud!")


if __name__ == "__main__":
  main()
    
