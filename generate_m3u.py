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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://giovang.rent/",
}

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def get_sport_emoji(sport_type="", league="", team=""):
  """Phân loại biểu tượng môn thể thao"""
  s = f"{sport_type} {league} {team}".lower()
  if any(k in s for k in ["basketball", "bóng rổ", "nba", "aces", "fever"]):
    return "🏀"
  if any(k in s for k in ["volleyball", "bóng chuyền"]):
    return "🏐"
  if any(k in s for k in ["baseball", "bóng chày", "braves", "phillies"]):
    return "⚾"
  if any(k in s for k in ["tennis", "quần vợt", "softball", "wta", "atp"]):
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
  """Format tên Bình luận viên chuẩn (Súp), (Cận), (Riko)"""
  if not blv_raw:
    return ""
  if isinstance(blv_raw, list):
    blv_raw = blv_raw[0] if blv_raw else ""

  name = str(blv_raw).strip()
  name = re.sub(r"^blv[-_\s]*", "", name, flags=re.IGNORECASE)

  if name:
    name = name.capitalize()
  return f" ({name})" if name else ""


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


def extract_stream_url(match):
  """Trích xuất Stream URL chuẩn vcdn.cloud từ thông tin trận đấu"""
  match_str = json.dumps(match)

  # 1. Tìm trực tiếp URL m3u8 vcdn.cloud trong dữ liệu
  m3u8_matches = re.findall(
      r"https?://ftlh5sc02iliv\.vcdn\.cloud/\d+_hd/\d+_hd@720p\.m3u8", match_str
  )
  if m3u8_matches:
    return m3u8_matches[0]

  # 2. Ưu tiên lấy từ trường room_id, live_id, stream_id, fi, room
  for key in ["room_id", "live_id", "stream_id", "fi", "room", "channel_id"]:
    val = match.get(key)
    if isinstance(val, dict):
      val = (
          val.get("id")
          or val.get("room_id")
          or val.get("stream_id")
          or val.get("fi")
      )
    if val and str(val).isdigit():
      s_val = str(val).strip()
      if len(s_val) in [9, 10, 11]:
        return f"https://ftlh5sc02iliv.vcdn.cloud/{s_val}_hd/{s_val}_hd@720p.m3u8"

  # 3. Lấy theo trường id của trận đấu
  m_id = str(match.get("id", "")).strip()
  if m_id.isdigit() and len(m_id) in [9, 10, 11]:
    return f"https://ftlh5sc02iliv.vcdn.cloud/{m_id}_hd/{m_id}_hd@720p.m3u8"

  # 4. Tìm kiếm ID 9-11 chữ số bất kỳ trong chuỗi JSON
  ids = re.findall(r"\b(179\d{7}|178\d{7}|\d{10})\b", match_str)
  if ids:
    s_id = ids[0]
    return f"https://ftlh5sc02iliv.vcdn.cloud/{s_id}_hd/{s_id}_hd@720p.m3u8"

  return "https://freem3u.xyz/static/no-signal/low.m3u8"


def extract_matches_from_html(html_content):
  """Rút trích dữ liệu từ __NEXT_DATA__"""
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
          ):
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

  # Nguồn API (ưu tiên các nguồn livestream trực tiếp)
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

  web_sources = ["https://giovang.rent/", "https://giovang.city/"]

  all_matches_dict = {}

  # 1. Cào các nguồn API
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
                m_id = (
                    item.get("room_id")
                    or item.get("id")
                    or item.get("fi")
                    or item.get("title")
                )
                if m_id and str(m_id) not in all_matches_dict:
                  all_matches_dict[str(m_id)] = item
        except Exception:
          pass

  # 2. Cào các trang Web
  with ThreadPoolExecutor(max_workers=5) as executor:
    future_to_url = {
        executor.submit(fetch_url, url): url for url in web_sources
    }
    for future in as_completed(future_to_url):
      html_text = future.result()
      if html_text:
        for item in extract_matches_from_html(html_text):
          m_id = (
              item.get("room_id")
              or item.get("id")
              or item.get("fi")
              or item.get("title")
          )
          if m_id and str(m_id) not in all_matches_dict:
            all_matches_dict[str(m_id)] = item

  # 3. Tạo file M3U chuẩn 100% theo mẫu tttt.m3u
  m3u_lines = ["#EXTM3U\n"]

  for match in all_matches_dict.values():
    status_code = str(match.get("status_code", "")).upper()
    if status_code in ["FINISHED", "FT", "ENDED", "CANCELLED"]:
      continue

    stream_url = extract_stream_url(match)

    teams = match.get("teams") if isinstance(match.get("teams"), dict) else {}
    home_name = (
        teams.get("home", {}).get("name", "").strip()
        if isinstance(teams.get("home"), dict)
        else ""
    )
    away_name = (
        teams.get("away", {}).get("name", "").strip()
        if isinstance(teams.get("away"), dict)
        else ""
    )

    match_name = (
        f"{home_name} vs {away_name}"
        if home_name and away_name
        else (match.get("title") or "Trận đấu")
    )

    logo = ""
    if isinstance(teams.get("home"), dict) and teams.get("home", {}).get(
        "logo"
    ):
      logo = teams["home"]["logo"]

    ts = match.get("time_start")
    if ts:
      try:
        dt = datetime.datetime.fromtimestamp(int(ts), tz=TZ_VN)
        time_str = dt.strftime("%H:%M %d/%m")
      except Exception:
        time_str = now_vn.strftime("%H:%M %d/%m")
    else:
      time_str = now_vn.strftime("%H:%M %d/%m")

    blv_str = clean_blv_name(match.get("blv") or match.get("commentator"))
    sport_type = match.get("type") or match.get("sport_type") or ""
    league_title = (
        match.get("league", {}).get("title", "")
        if isinstance(match.get("league"), dict)
        else ""
    )
    emoji = get_sport_emoji(str(sport_type), str(league_title), str(match_name))

    is_live = "vcdn.cloud" in stream_url
    status_icon = "🟢 " if is_live else "🟡 "
    title = f"{status_icon}{time_str} {emoji} {match_name}{blv_str} [hls]"

    m3u_lines.append(
        f'#EXTINF:-1 tvg-logo="{logo}" group-title="Giờ Vàng TV" , {title}'
    )
    m3u_lines.append(stream_url)
    m3u_lines.append("")

  with open("playlist.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(m3u_lines))

  print("Cập nhật thành công playlist.m3u!")


if __name__ == "__main__":
  main()
    
