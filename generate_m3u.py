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
  """Format tên Bình luận viên chuẩn (Súp), (Cận), (blv-mason)"""
  if not blv_raw:
    return ""
  if isinstance(blv_raw, list):
    blv_raw = blv_raw[0] if blv_raw else ""
  if isinstance(blv_raw, dict):
    blv_raw = (
        blv_raw.get("name")
        or blv_raw.get("nickname")
        or blv_raw.get("title")
        or ""
    )

  name = str(blv_raw).strip().strip("()")
  if not name or name.lower() in ["none", "null", "undefined"]:
    return ""

  if not name.lower().startswith("blv-") and not name.lower().startswith(
      "blv_"
  ):
    name = re.sub(r"^blv\s+", "", name, flags=re.IGNORECASE).strip()
    if name:
      name = name[0].upper() + name[1:] if len(name) > 1 else name.upper()

  return f" ({name})" if name else ""


def is_valid_room_id(val):
  """Kiểm tra ID luồng live có đúng định dạng vcdn (thường 10 chữ số bắt đầu bằng 17/18)"""
  if not val:
    return False
  s = str(val).strip()
  return (
      s.isdigit()
      and len(s) in [9, 10, 11]
      and not s.startswith("16")
      and not s.startswith("15")
  )


def get_vcdn_url(room_id):
  """Tạo URL luồng vcdn.cloud phát trực tiếp mượt mà"""
  return f"https://ftlh5sc02iliv.vcdn.cloud/{room_id}_hd/{room_id}_hd@720p.m3u8"


def fetch_url(url, timeout=12):
  """Tải dữ liệu URL kèm bypass SSL"""
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


def extract_room_id_from_dict(obj):
  """Bổ sung ưu tiên kiểm tra khóa 'id' và các khóa phòng livestream"""
  if not isinstance(obj, dict):
    return None

  # 1. Kiểm tra trực tiếp các trường ID phòng
  for key in [
      "room_id",
      "id",
      "live_id",
      "stream_id",
      "channel_id",
      "fi",
      "room",
  ]:
    val = obj.get(key)
    if isinstance(val, dict):
      val = (
          val.get("id")
          or val.get("room_id")
          or val.get("stream_id")
          or val.get("live_id")
      )
    if is_valid_room_id(val):
      return str(val).strip()

  # 2. Nếu không thấy, tìm bằng Regex tất cả số 10 chữ số dạng 17xxxxxxxx
  obj_str = json.dumps(obj)
  found = re.findall(r"\b(179\d{7}|178\d{7}|180\d{7})\b", obj_str)
  if found:
    return found[0]

  return None


def extract_rooms_from_match(match):
  """Tách danh sách phòng phát / BLV của từng trận đấu"""
  rooms_data = []

  # Lấy danh sách phòng con (relate_rooms / rooms / blv)
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
        # Lấy room_id từ phòng con r, nếu không có mới lấy từ trận đấu chính
        r_id = extract_room_id_from_dict(r) or extract_room_id_from_dict(match)
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
        if not url:
          url = "https://freem3u.xyz/static/no-signal/low.m3u8"

        rooms_data.append(
            {"room_id": r_id, "blv": blv_name, "stream_url": url}
        )

  # Nếu không có danh sách phòng con, lấy trực tiếp trận đấu làm 1 luồng
  if not rooms_data:
    r_id = extract_room_id_from_dict(match)
    blv_name = match.get("blv") or match.get("commentator") or ""
    url = get_vcdn_url(r_id) if r_id else None
    if not url:
      url = "https://freem3u.xyz/static/no-signal/low.m3u8"

    rooms_data.append({"room_id": r_id, "blv": blv_name, "stream_url": url})

  return rooms_data


def extract_match_info(match):
  """Rút trích tên trận đấu, logo, thời gian"""
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
              k in obj for k in ["home", "away", "teams", "room_id", "title"]
          ) and ("pageProps" not in obj):
            matches.append(obj)
          for v in obj.values():
            traverse(v)
        elif isinstance(obj, list):
          for item in obj:
            traverse(item)

      traverse(data.get("props", {}))
    except Exception:
      pass
  return matches


def main():
  now_vn = datetime.datetime.now(TZ_VN)

  api_sources = [
      "https://live-api.keonhacaitp.one/storage/livestream/live.json",
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
  ]

  raw_matches = []

  # Tải dữ liệu từ API
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

  # Tải dữ liệu từ Web
  with ThreadPoolExecutor(max_workers=5) as executor:
    future_to_url = {
        executor.submit(fetch_url, url): url for url in web_sources
    }
    for future in as_completed(future_to_url):
      html_text = future.result()
      if html_text:
        extracted = extract_matches_from_html(html_text)
        raw_matches.extend(extracted)

  # Tạo nội dung M3U
  m3u_lines = ["#EXTM3U\n"]
  seen_keys = set()

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

      unique_key = (
          stream_url
          if "vcdn.cloud" in stream_url
          else f"{info['match_name']}_{info['time_str']}_{blv_str}"
      )
      if unique_key in seen_keys:
        continue
      seen_keys.add(unique_key)

      # Định dạng biểu tượng trạng thái phát chuẩn
      is_vcdn = "vcdn.cloud" in stream_url
      status_icon = "🟢 " if is_vcdn else "🟡 "

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
    
