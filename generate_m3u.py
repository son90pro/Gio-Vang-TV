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


def extract_stream_from_text(text):
  if not text:
    return None

  # 1. Tìm trực tiếp URL m3u8
  m3u8s = re.findall(
      r"https?://[^\s\"']+\.m3u8[^\s\"']*", text, re.IGNORECASE
  )
  for m in m3u8s:
    if "no-signal" not in m:
      return m

  # 2. Tìm Room ID dạng 178xxxxxxx, 179xxxxxxx, 180xxxxxxx...
  ids = re.findall(r"\b(1[789]\d{7,9})\b", text)
  if ids:
    return f"https://ftlh5sc02iliv.vcdn.cloud/{ids[0]}_hd/{ids[0]}_hd@720p.m3u8"

  # 3. Quét bất kỳ chuỗi số nào trong field room_id
  room_matches = re.findall(r'"room_id"\s*:\s*"?(\d+)"?', text)
  for r_id in room_matches:
    if len(r_id) >= 6:
      return f"https://ftlh5sc02iliv.vcdn.cloud/{r_id}_hd/{r_id}_hd@720p.m3u8"

  return None


def process_single_match(match):
  m_id = match.get("id") or match.get("match_id")
  match_str = json.dumps(match)

  stream_url = extract_stream_from_text(match_str)

  # Nếu không có link trong JSON tổng, gọi API chi tiết của trận đó
  if not stream_url and m_id:
    detail_url = f"https://live-api.keonhacaitp.one/storage/livestream/match/{m_id}.json"
    detail_text = fetch_url(detail_url)
    if detail_text:
      stream_url = extract_stream_from_text(detail_text)

  # Fallback cuối cùng nếu thực sự chưa phát live
  is_live = True
  if not stream_url:
    stream_url = "https://freem3u.xyz/static/no-signal/low.m3u8"
    is_live = False

  # Xử lý thông tin trận đấu
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

  logo = (
      (home_obj.get("logo") if isinstance(home_obj, dict) else "")
      or match.get("home_logo")
      or match.get("logo")
      or ""
  )

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
    time_str = datetime.datetime.now(TZ_VN).strftime("%H:%M %d/%m")

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

  return {
      "key": f"{match_name.lower().strip()}_{time_str}_{blv_str.lower().strip()}",
      "match_name": match_name,
      "logo": logo,
      "time_str": time_str,
      "blv_str": blv_str,
      "emoji": emoji,
      "stream_url": stream_url,
      "is_live": is_live,
  }


def main():
  now_vn = datetime.datetime.now(TZ_VN)

  # Lấy danh sách trận đấu từ các nguồn
  api_sources = [
      "https://live-api.keonhacaitp.one/storage/livestream/live.json",
      "https://api.giovang.co/storage/livestream/live.json",
      "https://live-api.keonhacaitp.one/storage/livestream/home.json",
  ]

  for i in range(-1, 2):
    day = now_vn + datetime.timedelta(days=i)
    api_sources.append(
        f"https://live-api.keonhacaitp.one/storage/livestream/date/{day.strftime('%d-%m-%Y')}.json"
    )

  unique_matches = {}
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
                m_id = item.get("id") or item.get("match_id")
                if m_id:
                  unique_matches[m_id] = item
        except Exception:
          pass

  # Chạy đa luồng bóc tách link từng trận
  playlist_dict = {}
  with ThreadPoolExecutor(max_workers=15) as executor:
    futures = [
        executor.submit(process_single_match, m)
        for m in unique_matches.values()
    ]
    for future in as_completed(futures):
      res = future.result()
      k = res["key"]
      if k not in playlist_dict or (
          not playlist_dict[k]["is_live"] and res["is_live"]
      ):
        playlist_dict[k] = res

  m3u_lines = ["#EXTM3U\n"]
  m3u_lines.append(
      f"# Updated at {datetime.datetime.now(TZ_VN).strftime('%Y-%m-%d %H:%M:%S')}"
  )

  for item in playlist_dict.values():
    status_icon = "🟢 " if item["is_live"] else "🟡 "
    title = f"{status_icon}{item['time_str']} {item['emoji']} {item['match_name']}{item['blv_str']} [hls]"
    m3u_lines.append(
        f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="Giờ Vàng TV" ,'
        f" {title}"
    )
    m3u_lines.append(item["stream_url"])
    m3u_lines.append("")

  with open("playlist.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(m3u_lines))

  print("Đã cập nhật playlist thành công!")


if __name__ == "__main__":
  main()
    
