import datetime
import json
import re
import ssl
import time
import urllib.request
import zoneinfo
from concurrent.futures import ThreadPoolExecutor, as_completed

TZ_VN = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")

# Header chuẩn vượt tường rào CDN vcdn.cloud
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like"
    " Gecko) Chrome/128.0.0.0 Safari/537.36"
)
REFERER = "https://giovang.co/"

HEADERS = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Referer": REFERER,
    "Origin": "https://giovang.co/",
}

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def get_sport_emoji(sport_type="", league="", match_name=""):
  """Nhận diện icon cho từng môn thể thao"""
  s = f"{sport_type} {league} {match_name}".lower()
  if any(k in s for k in ["basketball", "bóng rổ", "nba"]):
    return "🏀"
  if any(k in s for k in ["volleyball", "bóng chuyền"]):
    return "🏐"
  if any(
      k in s for k in ["tennis", "quần vợt", "softball", "wta", "atp", "open"]
  ):
    return "🥎"
  if any(
      k in s
      for k in ["esport", "esports", "lol", "dota", "valorant", "liên minh"]
  ):
    return "🎮"
  if any(k in s for k in ["billiards", "bida", "bi a", "pool", "9-ball"]):
    return "🎱"
  if any(
      k in s for k in ["f1", "formula1", "formula 1", "grand prix", "racing"]
  ):
    return "🏎️"
  if any(k in s for k in ["mma", "one friday", "boxing", "ufc", "võ"]):
    return "🥊"
  if any(k in s for k in ["american football", "nfl", "steelers", "browns"]):
    return "⚽"  # Hoặc 🏈
  return "⚽"


def clean_blv_name(blv_raw):
  """Làm sạch tên Bình luận viên đúng định dạng m3u mẫu"""
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

  name = str(blv_raw).strip()
  if not name or name.lower() in ["none", "null", "undefined"]:
    return ""

  if name.startswith("(") and name.endswith(")"):
    return f" {name}"

  cleaned = re.sub(
      r"^(blv|commentator)[-_\s]*", "", name, flags=re.IGNORECASE
  ).strip()
  if cleaned:
    if name.lower().startswith("blv"):
      return f" (blv-{cleaned.lower()})"
    return f" ({cleaned})"
  return ""


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
  """Bắt ID phòng live của Giờ Vàng (Dạng 10 chữ số)"""
  match_str = json.dumps(match_obj)
  ids = re.findall(r"\b(179\d{7})\b", match_str)
  if ids:
    return ids[0]

  ids_gen = re.findall(r"\b(1[789]\d{7,8})\b", match_str)
  if ids_gen:
    return ids_gen[0]

  for key in ["room_id", "fi", "live_id", "id"]:
    val = match_obj.get(key)
    if val and str(val).isdigit() and len(str(val)) in [9, 10]:
      return str(val)

  return None


def main():
  now_vn = datetime.datetime.now(TZ_VN)

  # Các API endpoint cào dữ liệu Giờ Vàng
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
    if not room_id:
      continue

    # Tên đội / Trận đấu
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

    if (
        home_name
        and away_name
        and str(home_name).lower() != "none"
        and str(away_name).lower() != "none"
    ):
      match_name = f"{home_name.strip()} vs {away_name.strip()}"
    else:
      match_name = str(
          match.get("title") or match.get("name") or "Trận đấu"
      ).strip()

    # Logo
    logo = (
        (home_obj.get("logo") if isinstance(home_obj, dict) else "")
        or match.get("home_logo")
        or match.get("logo")
        or "https://giovang.co/favicon.ico"
    )

    # Thời gian thi đấu & Trạng thái LIVE
    ts = (
        match.get("time_start")
        or match.get("timestamp")
        or match.get("match_time")
    )
    time_str = ""
    is_live = False

    if ts:
      try:
        ts_int = int(ts)
        if ts_int > 1e11:
          ts_int //= 1000
        dt = datetime.datetime.fromtimestamp(ts_int, tz=TZ_VN)
        time_str = dt.strftime("%H:%M %d/%m")

        # Nếu đã đến giờ đá hoặc đang diễn ra
        if dt <= now_vn + datetime.timedelta(minutes=10):
          is_live = True
      except Exception:
        pass

    if not time_str:
      time_str = now_vn.strftime("%H:%M %d/%m")
      is_live = True

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

    # Tạo đường dẫn Stream chuẩn kèm Header bypass CDN
    if is_live:
      status_icon = "🟢 "
      base_stream = f"https://ftlh5sc02iliv.vcdn.cloud/{room_id}_hd/{room_id}_hd@720p.m3u8"
    else:
      status_icon = ""
      base_stream = "https://freem3u.xyz/static/no-signal/low.m3u8"

    # Gắn Header trực tiếp vào URL cho TiviMate / Smart TV
    final_stream = f"{base_stream}|User-Agent={UA}&Referer={REFERER}"

    title = f"{status_icon}{time_str} {emoji} {match_name}{blv_str} [hls]"

    playlist_dict[room_id] = {
        "title": title,
        "logo": logo,
        "url": final_stream,
    }

  # Ghép dữ liệu thành file M3U chuẩn
  m3u_lines = ["#EXTM3U\n"]
  for item in playlist_dict.values():
    m3u_lines.append(f"#EXTVLCOPT:http-user-agent={UA}")
    m3u_lines.append(f"#EXTVLCOPT:http-referrer={REFERER}")
    m3u_lines.append(
        f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="Giờ Vàng TV" ,'
        f" {item['title']}"
    )
    m3u_lines.append(item["url"])
    m3u_lines.append("")

  with open("playlist.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(m3u_lines))

  print(f"Đã cập nhật {len(playlist_dict)} trận đấu vào file playlist.m3u")


if __name__ == "__main__":
  main()
    
