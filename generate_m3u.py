import datetime
import json
import re
import ssl
import time
import urllib.request
import zoneinfo
from concurrent.futures import ThreadPoolExecutor, as_completed

# Múi giờ Việt Nam (GMT+7)
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
  """Phân loại biểu tượng môn thể thao"""
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
  """Format tên BLV chuẩn: blv-can -> Cận, blv-vit -> Vịt, blv-mason -> Mason"""
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


def is_valid_room_id(val, match_time_start=None):
  """Kiểm tra ID phòng live thật (tránh nhầm với time_start thi đấu)"""
  if not val:
    return False
  s = str(val).strip()
  if not (s.isdigit() and len(s) in [9, 10, 11]):
    return False

  v = int(s)
  # Nếu trùng khớp hoàn toàn với time_start thi đấu -> Loại bỏ (đó là mốc thời gian, không phải room_id)
  if match_time_start and v == int(match_time_start):
    return False

  # Thời gian bắt đầu trận đấu luôn là số tròn chia hết cho 300 (5 phút). Room ID thật thì không.
  if (
      v % 300 == 0
      and match_time_start
      and abs(v - int(match_time_start)) < 7200
  ):
    return False

  return True


def get_vcdn_url(room_id):
  return f"https://ftlh5sc02iliv.vcdn.cloud/{room_id}_hd/{room_id}_hd@720p.m3u8"


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


def extract_rooms_from_match(match):
  """Trích xuất danh sách phòng phát / BLV chính xác nhất"""
  time_start = (
      match.get("time_start")
      or match.get("timestamp")
      or match.get("match_time")
  )

  match_str = json.dumps(match)

  # 1. Tìm các link .m3u8 trực tiếp nếu có
  m3u8_links = re.findall(r"https?://[^\s\"']+\.m3u8", match_str)

  # 2. Tìm tất cả số ID 10 chữ số hợp lệ dạng vcdn
  vcdn_ids = re.findall(r"\b(17[89]\d{7}|180\d{7})\b", match_str)
  valid_vcdn_ids = [s for s in vcdn_ids if is_valid_room_id(s, time_start)]

  rooms_data = []

  # Lấy danh sách các phòng live con (relate_rooms / rooms / blv)
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

  if not candidates:
    blv_val = match.get("blv") or match.get("commentator")
    if (
        isinstance(blv_val, list)
        and len(blv_val) > 0
        and isinstance(blv_val[0], dict)
    ):
      candidates = blv_val

  if candidates:
    for r in candidates:
      if isinstance(r, dict):
        r_id = None
        for key in [
            "room_id",
            "id",
            "live_id",
            "stream_id",
            "channel_id",
            "fi",
            "room",
        ]:
          val = r.get(key)
          if val and is_valid_room_id(val, time_start):
            r_id = str(val).strip()
            break

        if not r_id and valid_vcdn_ids:
          r_id = valid_vcdn_ids[0]

        blv_name = (
            r.get("name")
            or r.get("blv_name")
            or r.get("nickname")
            or r.get("commentator")
            or r.get("title")
            or match.get("blv")
            or ""
        )

        url = get_vcdn_url(r_id) if r_id else None
        if not url and m3u8_links:
          url = m3u8_links[0]
        if not url:
          url = "https://freem3u.xyz/static/no-signal/low.m3u8"

        rooms_data.append(
            {"room_id": r_id, "blv": blv_name, "stream_url": url}
        )
      elif isinstance(r, str):
        r_id = valid_vcdn_ids[0] if valid_vcdn_ids else None
        url = (
            get_vcdn_url(r_id)
            if r_id
            else "https://freem3u.xyz/static/no-signal/low.m3u8"
        )
        rooms_data.append({"room_id": r_id, "blv": r, "stream_url": url})

  # Nếu không có danh sách phòng con, lấy trực tiếp trận đấu
  if not rooms_data:
    r_id = None
    for key in ["room_id", "live_id", "stream_id", "channel_id", "fi", "room"]:
      val = match.get(key)
      if val and is_valid_room_id(val, time_start):
        r_id = str(val).strip()
        break

    if not r_id and valid_vcdn_ids:
      r_id = valid_vcdn_ids[0]

    blv_name = match.get("blv") or match.get("commentator") or ""
    url = get_vcdn_url(r_id) if r_id else None
    if not url and m3u8_links:
      url = m3u8_links[0]
    if not url:
      url = "https://freem3u.xyz/static/no-signal/low.m3u8"

    rooms_data.append({"room_id": r_id, "blv": blv_name, "stream_url": url})

  return rooms_data


def extract_match_info(match):
  teams = match.get("teams") if isinstance(match.get("teams"), dict) else {}
  home_obj = teams.get("home") or match.get("home") or match.get("home_team") or {}
  away_obj = teams.get("away") or match.get("away") or match.get("away_team") or {}

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
      match.get("type") or match.get("sport_type") or match.get("category") or ""
  )
  league_obj = match.get("league") or match.get("tournament") or {}
  league_title = (
      league_obj.get("title") or league_obj.get("name") or ""
      if isinstance(league_obj, dict)
      else str(league_obj)
  )

  emoji = get_sport_emoji(str(sport_type), str(league_title), match_name)
  status_code = str(
      match.get("status_code") or match.get("status") or ""
  ).upper()

  return {
      "match_name": match_name,
      "logo": logo,
      "time_str": time_str,
      "emoji": emoji,
      "status_code": status_code,
  }


def extract_matches_from_html(html_content):
  """Lấy dữ liệu JSON từ HTML trang web"""
  matches = []
  if not html_content:
    return matches

  json_matches = re.findall(
      r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
      html_content,
      re.DOTALL,
  )
  if json_matches:
    try:
      data = json.loads(json_matches[0])

      def traverse(obj):
        if isinstance(obj, dict):
          if any(
              k in obj
              for k in [
                  "relate_rooms",
                  "room_id",
                  "home_team",
                  "away_team",
                  "home",
                  "away",
              ]
          ):
            matches.append(obj)
          for v in obj.values():
            if isinstance(v, (dict, list)):
              traverse(v)
        elif isinstance(obj, list):
          for item in obj:
            if isinstance(item, (dict, list)):
              traverse(item)

      traverse(data.get("props", {}))
    except Exception:
      pass
  return matches


def main():
  now_vn = datetime.datetime.now(TZ_VN)

  # Các nguồn API phát live (đưa nguồn live lên đầu)
  api_sources = [
      "https://live-api.keonhacaitp.one/storage/livestream/live.json",
      "https://api.giovang.co/storage/livestream/live.json",
      "https://api.giovang.co/api/v1/matches/live",
      "https://live-api.keonhacaitp.one/storage/livestream/home.json",
      "https://live-api.keonhacaitp.one/storage/livestream/match.json",
      "https://live-api.keonhacaitp.one/storage/livestream/schedule.json",
  ]

  for i in range(-1, 3):
    day = now_vn + datetime.timedelta(days=i)
    d1 = day.strftime("%d-%m-%Y")
    d2 = day.strftime("%Y-%m-%d")
    api_sources.append(
        f"https://live-api.keonhacaitp.one/storage/livestream/date/{d1}.json"
    )
    api_sources.append(
        f"https://live-api.keonhacaitp.one/storage/livestream/date/{d2}.json"
    )

  web_sources = [
      "https://giovang.co/",
      "https://giovang.rent/",
      "https://giovang.city/",
      "https://giovang.live/",
  ]

  raw_matches = []

  # 1. Tải dữ liệu từ API
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

  # 2. Tải dữ liệu từ Web
  with ThreadPoolExecutor(max_workers=5) as executor:
    future_to_url = {
        executor.submit(fetch_url, url): url for url in web_sources
    }
    for future in as_completed(future_to_url):
      html_text = future.result()
      if html_text:
        extracted = extract_matches_from_html(html_text)
        raw_matches.extend(extracted)

  # 3. Tổng hợp và ưu tiên ghi đè link Live thật (🟢 vcdn.cloud)
  playlist_dict = {}

  for match in raw_matches:
    info = extract_match_info(match)

    if info["status_code"] in [
        "FINISHED",
        "FT",
        "ENDED",
        "CANCELLED",
        "POSTPONED",
    ]:
      continue

    rooms = extract_rooms_from_match(match)

    for room in rooms:
      stream_url = room["stream_url"]
      blv_str = clean_blv_name(room["blv"])

      match_key = f"{info['match_name'].lower().strip()}_{info['time_str']}_{blv_str.lower().strip()}"
      is_live = "vcdn.cloud" in stream_url

      # Logic ghi đè: Nếu trận đấu đã có trong danh sách nhưng trước đó dính link no-signal,
      # nếu gặp link vcdn.cloud thật -> Lập tức ghi đè link live!
      if match_key in playlist_dict:
        existing = playlist_dict[match_key]
        if not existing["is_live"] and is_live:
          playlist_dict[match_key] = {
              "info": info,
              "stream_url": stream_url,
              "blv_str": blv_str,
              "is_live": is_live,
          }
      else:
        playlist_dict[match_key] = {
            "info": info,
            "stream_url": stream_url,
            "blv_str": blv_str,
            "is_live": is_live,
        }

  # 4. Xuất file M3U chuẩn
  m3u_lines = ["#EXTM3U\n"]

  for item in playlist_dict.values():
    info = item["info"]
    stream_url = item["stream_url"]
    blv_str = item["blv_str"]
    is_live = item["is_live"]

    status_icon = "🟢 " if is_live else "🟡 "
    title = f"{status_icon}{info['time_str']} {info['emoji']} {info['match_name']}{blv_str} [hls]"

    m3u_lines.append(
        f'#EXTINF:-1 tvg-logo="{info["logo"]}" group-title="Giờ Vàng TV" ,'
        f" {title}"
    )
    m3u_lines.append(stream_url)
    m3u_lines.append("")

  with open("playlist.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(m3u_lines))

  print("Đã cập nhật thành công playlist.m3u chuẩn vcdn.cloud!")


if __name__ == "__main__":
  main()
    
