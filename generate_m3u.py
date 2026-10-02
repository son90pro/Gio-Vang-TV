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
  """Nhận diện chính xác emoji môn thể thao"""
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
    return "[formula1]"
  if any(
      k in s for k in ["mma", "one friday", "boxing", "ufc", "võ", "fights"]
  ):
    return "🥊"
  return "⚽"


def clean_blv_name(blv_raw):
  """Định dạng tên BLV chuẩn mẫu"""
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

  return f" ({name})"


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


def get_real_room_id(match_obj):
  """Lấy chính xác Room ID phát sóng từ JSON dữ liệu gốc"""
  # Ưu tiên các trường chứa ID phòng live thực tế
  for key in ["room_id", "fi", "live_id", "stream_id"]:
    val = match_obj.get(key)
    if val and str(val).isdigit() and len(str(val)) in [9, 10]:
      return str(val)

  # Quét từ mảng links hoặc servers nếu có
  servers = match_obj.get("servers") or match_obj.get("links") or []
  if isinstance(servers, list):
    for srv in servers:
      if isinstance(srv, dict):
        sid = srv.get("room_id") or srv.get("id") or srv.get("stream_id")
        if sid and str(sid).isdigit() and len(str(sid)) in [9, 10]:
          return str(sid)

  # Tìm ID dạng 10 chữ số bắt đầu bằng 179... trong toàn bộ JSON object
  match_str = json.dumps(match_obj)
  ids = re.findall(r'"(?:room_id|fi|id|live_id)"\s*:\s*"?(\d{9,10})"?', match_str)
  if ids:
    return ids[0]

  return None


def main():
  now_vn = datetime.datetime.now(TZ_VN)

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

  playlist_entries = []
  seen_keys = set()

  for match in raw_matches:
    room_id = get_real_room_id(match)

    # Lấy tên 2 đội
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

    # Khóa chống trùng lặp trận
    unique_key = f"{match_name}_{match.get('time_start', '')}"
    if unique_key in seen_keys:
      continue
    seen_keys.add(unique_key)

    # Logo
    logo = (
        (home_obj.get("logo") if isinstance(home_obj, dict) else "")
        or match.get("home_logo")
        or match.get("logo")
        or "https://giovang.co/favicon.ico"
    )

    # Thời gian thi đấu & Kiểm tra trạng thái Đang đá (LIVE)
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

        # Trận đã diễn ra hoặc đang trong khung giờ thi đấu
        if dt <= now_vn + datetime.timedelta(minutes=15):
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

    # Xử lý đường dẫn stream
    if is_live and room_id:
      status_icon = "🟢 "
      stream_url = f"https://ftlh5sc02iliv.vcdn.cloud/{room_id}_hd/{room_id}_hd@720p.m3u8"
    else:
      status_icon = ""
      stream_url = "https://freem3u.xyz/static/no-signal/low.m3u8"

    title = f"{status_icon}{time_str} {emoji} {match_name}{blv_str} [hls]"

    playlist_entries.append({
        "title": title,
        "logo": logo,
        "url": stream_url,
    })

  # Xuất file M3U chuẩn khớp 100% với file mẫu
  m3u_lines = ["#EXTM3U\n"]
  for entry in playlist_entries:
    m3u_lines.append(
        f'#EXTINF:-1 tvg-logo="{entry["logo"]}" group-title="Giờ Vàng TV" ,'
        f" {entry['title']}"
    )
    m3u_lines.append(entry["url"])
    m3u_lines.append("")

  with open("playlist.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(m3u_lines))

  print(
      f"Hoàn thành xuất {len(playlist_entries)} trận đấu vào file playlist.m3u!"
  )


if __name__ == "__main__":
  main()
