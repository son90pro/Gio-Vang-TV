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

  cleaned = re.sub(r"^blv[-_\s]*", "", name, flags=re.IGNORECASE).strip()
  if cleaned:
    name = cleaned.capitalize()

  return f" ({name})" if name else ""


def fetch_url(url, timeout=12):
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


def find_stream_url(obj):
  """Tìm link .m3u8 hoặc room_id từ dict/object bất kỳ"""
  if not obj:
    return None

  obj_str = json.dumps(obj)

  # 1. Quét trực tiếp link .m3u8 trong JSON
  m3u8_matches = re.findall(
      r"https?://[^\s\"']+\.m3u8[^\s\"']*", obj_str, re.IGNORECASE
  )
  for link in m3u8_matches:
    if "no-signal" not in link:
      return link

  # 2. Tìm ID phòng live (dạng 9-11 chữ số)
  room_ids = re.findall(r"\b(1[789]\d{7,9})\b", obj_str)
  if room_ids:
    return f"https://ftlh5sc02iliv.vcdn.cloud/{room_ids[0]}_hd/{room_ids[0]}_hd@720p.m3u8"

  return None


def extract_rooms_from_match(match):
  rooms_data = []

  # Lấy danh sách BLV/Phòng live nếu có
  candidates = []
  for k in [
      "relate_rooms",
      "rooms",
      "blv_list",
      "blvs",
      "commentators",
      "channels",
  ]:
    val = match.get(k)
    if isinstance(val, list) and len(val) > 0:
      candidates = val
      break

  if candidates:
    for r in candidates:
      if isinstance(r, dict):
        blv_name = (
            r.get("name")
            or r.get("blv_name")
            or r.get("nickname")
            or r.get("commentator")
            or r.get("title")
            or ""
        )
        url = find_stream_url(r) or find_stream_url(match)
        if url:
          rooms_data.append(
              {"blv": blv_name, "stream_url": url, "is_valid": True}
          )
      elif isinstance(r, str):
        url = find_stream_url(match)
        if url:
          rooms_data.append({"blv": r, "stream_url": url, "is_valid": True})

  if not rooms_data:
    blv_name = match.get("blv") or match.get("commentator") or ""
    url = find_stream_url(match)
    if url:
      rooms_data.append({"blv": blv_name, "stream_url": url, "is_valid": True})
    else:
      # Nếu trận chưa/không có link live thì mới dùng link fallback
      rooms_data.append({
          "blv": blv_name,
          "stream_url": "https://freem3u.xyz/static/no-signal/low.m3u8",
          "is_valid": False,
      })

  return rooms_data


def extract_match_info(match):
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

  logo = ""
  if isinstance(home_obj, dict) and home_obj.get("logo"):
    logo = home_obj["logo"]
  elif isinstance(away_obj, dict) and away_obj.get("logo"):
    logo = away_obj["logo"]

  if not logo:
    logo = (
        match.get("home_logo")
        or match.get("away_logo")
        or match.get("logo")
        or ""
    )

  ts = (
      match.get("time_start")
      or match.get("timestamp")
      or match.get("match_time")
      or match.get("time")
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
    time_str = datetime.datetime.now(TZ_VN).strftime("%H:%M %d/%m")

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

  return {
      "match_name": match_name,
      "logo": logo,
      "time_str": time_str,
      "emoji": emoji,
  }


def main():
  now_vn = datetime.datetime.now(TZ_VN)

  api_sources = [
      "https://live-api.keonhacaitp.one/storage/livestream/live.json",
      "https://api.giovang.co/storage/livestream/live.json",
      "https://api.giovang.co/api/v1/matches/live",
      "https://live-api.keonhacaitp.one/storage/livestream/home.json",
      "https://live-api.keonhacaitp.one/storage/livestream/match.json",
      "https://live-api.keonhacaitp.one/storage/livestream/schedule.json",
  ]

  for i in range(-1, 2):
    day = now_vn + datetime.timedelta(days=i)
    d1 = day.strftime("%d-%m-%Y")
    d2 = day.strftime("%Y-%m-%d")
    api_sources.append(
        f"https://live-api.keonhacaitp.one/storage/livestream/date/{d1}.json"
    )
    api_sources.append(
        f"https://live-api.keonhacaitp.one/storage/livestream/date/{d2}.json"
    )

  raw_matches = []

  with ThreadPoolExecutor(max_workers=10) as executor:
    future_to_url = {
        executor.submit(fetch_url, url): url for url in api_sources
    }
    for future in as_completed(future_to_url):
      raw_text = future.result()
      if raw_text:
        try:
          data = json.loads(raw_text)
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
    info = extract_match_info(match)
    rooms = extract_rooms_from_match(match)

    for room in rooms:
      stream_url = room["stream_url"]
      blv_str = clean_blv_name(room["blv"])
      is_valid = room["is_valid"]

      match_key = f"{info['match_name'].lower().strip()}_{info['time_str']}_{blv_str.lower().strip()}"

      # Nếu đã có trong danh sách nhưng chưa có link thật mà lượt này tìm thấy link thật -> Ghi đè
      if match_key in playlist_dict:
        if not playlist_dict[match_key]["is_valid"] and is_valid:
          playlist_dict[match_key] = {
              "info": info,
              "stream_url": stream_url,
              "blv_str": blv_str,
              "is_valid": is_valid,
          }
      else:
        playlist_dict[match_key] = {
            "info": info,
            "stream_url": stream_url,
            "blv_str": blv_str,
            "is_valid": is_valid,
        }

  m3u_lines = ["#EXTM3U\n"]
  m3u_lines.append(
      f"# Updated at {datetime.datetime.now(TZ_VN).strftime('%Y-%m-%d %H:%M:%S')}"
  )

  for item in playlist_dict.values():
    info = item["info"]
    stream_url = item["stream_url"]
    blv_str = item["blv_str"]
    is_valid = item["is_valid"]

    status_icon = "🟢 " if is_valid else "🟡 "
    title = f"{status_icon}{info['time_str']} {info['emoji']} {info['match_name']}{blv_str} [hls]"

    m3u_lines.append(
        f'#EXTINF:-1 tvg-logo="{info["logo"]}" group-title="Giờ Vàng TV" ,'
        f" {title}"
    )
    m3u_lines.append(stream_url)
    m3u_lines.append("")

  with open("playlist.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(m3u_lines))

  print("Đã cập nhật playlist.m3u!")


if __name__ == "__main__":
  main()
      
