import os
import json
import urllib.parse
import http.server
import socketserver
import webbrowser
import threading
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

PORT = 8000
CONFIG_FILE = "config.json"

default_config = {
    "maptiler_key": "YOUR_MAPTILER_API_KEY",
    "photos_dir": "./photos"
}

if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(default_config, f, indent=2, ensure_ascii=False)
    print(f"[!] Konfigurační soubor '{CONFIG_FILE}' nebyl nalezen. Byl vytvořen vzorový.")
    print(f"[!] Doplňte prosím svůj MapTiler API klíč a cestu ke složce s médii do '{CONFIG_FILE}'.")
    exit(0)

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

ROOT_DIR = config.get("photos_dir", default_config["photos_dir"])
MAPTILER_KEY = config.get("maptiler_key", "")

if not os.path.exists(ROOT_DIR):
    print(f"CHYBA: Složka s fotkami '{ROOT_DIR}' neexistuje! Zkontrolujte nastavení v {CONFIG_FILE}.")
    exit(1)

def get_exif_data(img):
    exif = img._getexif()
    if not exif:
        return None, None
    date_str = None
    geotagging = {}
    for (idx, tag) in TAGS.items():
        if tag == 'DateTimeOriginal' and idx in exif:
            date_str = str(exif[idx])
        elif tag == 'GPSInfo' and idx in exif:
            for (key, val) in GPSTAGS.items():
                if key in exif[idx]:
                    geotagging[val] = exif[idx][key]
    return geotagging, date_str

def get_decimal_coordinates(info):
    if not info:
        return None
    for key in ['GPSLatitude', 'GPSLatitudeRef', 'GPSLongitude', 'GPSLongitudeRef']:
        if key not in info:
            return None

    def _convert_to_degrees(value):
        d = float(value[0])
        m = float(value[1])
        s = float(value[2])
        return d + (m / 60.0) + (s / 3600.0)

    lat = _convert_to_degrees(info['GPSLatitude'])
    lat_ref = info['GPSLatitudeRef']
    if isinstance(lat_ref, bytes):
        lat_ref = lat_ref.decode(errors='ignore')
    if str(lat_ref).strip().upper() != 'N':
        lat = -lat

    lon = _convert_to_degrees(info['GPSLongitude'])
    lon_ref = info['GPSLongitudeRef']
    if isinstance(lon_ref, bytes):
        lon_ref = lon_ref.decode(errors='ignore')
    if str(lon_ref).strip().upper() != 'E':
        lon = -lon

    return lat, lon

def format_date(raw_date):
    if not raw_date:
        return None
    try:
        parts = raw_date.split(" ")[0].split(":")
        return f"{int(parts[2])}. {int(parts[1])}. {parts[0]}"
    except Exception:
        return raw_date

IMG_EXTS = ('.jpg', '.jpeg', '.png', '.webp')
VID_EXTS = ('.mp4', '.mov', '.webm', '.m4v')
ALL_EXTS = IMG_EXTS + VID_EXTS

albums = {}
print(f"Skenuji složky v: {ROOT_DIR}")

for item in sorted(os.listdir(ROOT_DIR)):
    subfolder_path = os.path.join(ROOT_DIR, item)
    if os.path.isdir(subfolder_path):
        slides = []
        files = sorted(os.listdir(subfolder_path))
        first_img_cover = None

        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in ALL_EXTS:
                fpath = os.path.join(subfolder_path, fname)
                is_video = ext in VID_EXTS
                coords = None
                taken_date = None

                if not is_video:
                    try:
                        with Image.open(fpath) as img:
                            geo, date_raw = get_exif_data(img)
                            coords = get_decimal_coordinates(geo)
                            taken_date = format_date(date_raw)
                    except Exception:
                        pass
                else:
                    try:
                        mtime = os.path.getmtime(fpath)
                        dt = datetime.fromtimestamp(mtime)
                        taken_date = f"{dt.day}. {dt.month}. {dt.year}"
                    except Exception:
                        pass

                url_path = f"{urllib.parse.quote(item)}/{urllib.parse.quote(fname)}"
                if not is_video and not first_img_cover:
                    first_img_cover = url_path

                slides.append({
                    "name": fname,
                    "file": url_path,
                    "type": "video" if is_video else "image",
                    "date": taken_date,
                    "lat": coords[0] if coords else None,
                    "lon": coords[1] if coords else None
                })
        
        if slides:
            albums[item] = {
                "title": item,
                "cover": first_img_cover or slides[0]["file"],
                "count": len(slides),
                "slides": slides
            }
            print(f"  ✓ {item}: {len(slides)} položek")

HTML = f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="utf-8"/>
<title>Travel Presenter</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #08090b; color: #eee; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; overflow: hidden; height: 100vh; width: 100vw; }}
  
  #home-view {{ width: 100%; height: 100%; overflow-y: auto; padding: 40px 60px; }}
  .header-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }}
  h1 {{ font-weight: 400; font-size: 28px; letter-spacing: 0.5px; color: #fff; }}
  .btn-exit {{ background: #dc2626; color: #fff; border: none; padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: 500; cursor: pointer; transition: background 0.2s; }}
  .btn-exit:hover {{ background: #b91c1c; }}

  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 24px; padding-bottom: 50px; }}
  .card {{ background: #161922; border-radius: 12px; overflow: hidden; cursor: pointer; transition: transform 0.2s, border-color 0.2s; border: 1px solid #232733; }}
  .card:hover {{ transform: translateY(-4px); border-color: #3b82f6; }}
  .card-img {{ width: 100%; height: 160px; object-fit: cover; background: #1f232e; }}
  .card-body {{ padding: 14px 16px; }}
  .card-title {{ font-size: 16px; font-weight: 600; margin-bottom: 4px; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .card-sub {{ font-size: 13px; color: #8892b0; }}

  #pres-view {{ display: none; width: 100%; height: 100%; flex-direction: row; position: relative; }}
  #media-box {{ flex: 1.35; display: flex; align-items: center; justify-content: center; position: relative; padding: 20px; background: #000; overflow: hidden; transition: flex 0.2s ease; }}
  #slide-img {{ max-width: 100%; max-height: 96vh; object-fit: contain; border-radius: 4px; display: none; }}
  #slide-video {{ max-width: 100%; max-height: 96vh; border-radius: 4px; display: none; outline: none; }}
  #map-container {{ flex: 1; height: 100%; border-left: 2px solid #1c202a; background: #111; position: relative; }}
  #map-box {{ width: 100%; height: 100%; }}

  body.map-hidden #map-container {{ display: none; }}
  body.map-hidden #media-box {{ flex: 1; width: 100vw; }}

  .top-bar {{ position: absolute; top: 16px; left: 20px; display: flex; gap: 10px; z-index: 10; }}
  .btn-ui {{ background: rgba(15, 17, 21, 0.75); color: #eee; border: 1px solid rgba(255,255,255,0.15); padding: 7px 14px; border-radius: 8px; cursor: pointer; backdrop-filter: blur(8px); font-size: 13px; transition: background 0.2s; }}
  .btn-ui:hover {{ background: rgba(255,255,255,0.2); }}

  #meta-box {{
    position: absolute; bottom: 24px; left: 24px; z-index: 1000;
    background: rgba(15, 17, 21, 0.88); border: 1px solid rgba(255, 255, 255, 0.15);
    backdrop-filter: blur(10px); border-radius: 10px; padding: 12px 18px; max-width: 320px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.6); pointer-events: none;
  }}
  .meta-place {{ font-size: 15px; font-weight: 600; color: #fff; margin-bottom: 4px; display: flex; align-items: center; gap: 6px; }}
  .meta-date {{ font-size: 13px; color: #9ca3af; display: flex; align-items: center; gap: 6px; }}

  #mini-map-box {{
    position: absolute; bottom: 24px; right: 24px; z-index: 1000;
    width: 200px; height: 230px;
    background: #111; border: 2px solid rgba(255, 255, 255, 0.25);
    border-radius: 10px; overflow: hidden;
    box-shadow: 0 8px 30px rgba(0,0,0,0.8);
    pointer-events: none;
  }}

  #blackout {{ position: fixed; inset: 0; background: #000; z-index: 9999; display: none; }}
</style>
</head>
<body>

  <div id="blackout"></div>

  <div id="home-view">
    <div class="header-row">
      <h1>Kategorie prezentace</h1>
      <button class="btn-exit" onclick="shutdownApp()">✕ Ukončit aplikaci</button>
    </div>
    <div class="grid" id="album-grid"></div>
  </div>

  <div id="pres-view">
    <div id="media-box">
      <div class="top-bar">
        <button class="btn-ui" onclick="goHome()">← Zpět (Esc)</button>
        <button class="btn-ui" id="btn-toggle-map" onclick="toggleMap()">🗺️ Skrýt mapu (M)</button>
        <div class="btn-ui" id="slide-info"></div>
      </div>
      
      <img id="slide-img" src="" alt="foto"/>
      <video id="slide-video" controls playsinline></video>
    </div>

    <div id="map-container">
      <div id="map-box"></div>
      <div id="meta-box" style="display: none;">
        <div class="meta-place" id="meta-place">📍 Hledám místo...</div>
        <div class="meta-date" id="meta-date">📅 -</div>
      </div>
      <div id="mini-map-box"></div>
    </div>
  </div>

<script>
  const albums = {json.dumps(albums)};
  let currentAlbumKey = null;
  let currentIdx = 0;
  let lastCoords = null;
  let lastMiniCoords = null;
  
  let map = null;
  let currentMarker = null;
  let miniMap = null;
  let miniMarker = null;

  let isMapVisible = true;
  let geocodeController = null;
  const locationCache = {{}};

  const preloader = new Image();

  const grid = document.getElementById('album-grid');
  for (const [key, data] of Object.entries(albums)) {{
    const card = document.createElement('div');
    card.className = 'card';
    card.onclick = () => openAlbum(key);
    card.innerHTML = `
      <img class="card-img" src="${{data.cover}}" loading="lazy" alt=""/>
      <div class="card-body">
        <div class="card-title">${{data.title}}</div>
        <div class="card-sub">${{data.count}} položek</div>
      </div>
    `;
    grid.appendChild(card);
  }}

  const MAPTILER_KEY = "{MAPTILER_KEY}";

  function initMaps() {{
    if (map) return;
    map = L.map('map-box', {{ zoomControl: false, attributionControl: false }}).setView([20, 0], 2);
    L.tileLayer(`https://api.maptiler.com/maps/streets-v2/{{z}}/{{x}}/{{y}}.png?key=${{MAPTILER_KEY}}&language=en`, {{
      tileSize: 512, zoomOffset: -1, minZoom: 1, maxZoom: 19, crossOrigin: true
    }}).addTo(map);
    L.control.zoom({{ position: 'topright' }}).addTo(map);

    miniMap = L.map('mini-map-box', {{
      zoomControl: false, attributionControl: false, dragging: false,
      scrollWheelZoom: false, doubleClickZoom: false, boxZoom: false, keyboard: false
    }}).setView([20, 0], 2);

    L.tileLayer(`https://api.maptiler.com/maps/streets-v2/{{z}}/{{x}}/{{y}}.png?key=${{MAPTILER_KEY}}&language=en`, {{
      tileSize: 512, zoomOffset: -1, minZoom: 1, maxZoom: 10, crossOrigin: true
    }}).addTo(miniMap);
  }}

  function refreshMapLayout() {{
    requestAnimationFrame(() => {{
      requestAnimationFrame(() => {{
        if (map) map.invalidateSize();
        if (miniMap) miniMap.invalidateSize();
      }});
    }});
  }}

  function toggleMap() {{
    isMapVisible = !isMapVisible;
    document.body.classList.toggle('map-hidden', !isMapVisible);
    document.getElementById('btn-toggle-map').innerText = isMapVisible ? '🗺️ Skrýt mapu (M)' : '🗺️ Zobrazit mapu (M)';
    
    if (isMapVisible && map) {{
      refreshMapLayout();
      const item = albums[currentAlbumKey].slides[currentIdx];
      if (item.lat !== null && item.lon !== null) {{
        map.setView([item.lat, item.lon], 14);
        miniMap.setView([item.lat, item.lon], 6);
      }}
    }}
  }}

  function openAlbum(key) {{
    currentAlbumKey = key;
    currentIdx = 0;
    lastCoords = null;
    lastMiniCoords = null;
    document.getElementById('home-view').style.display = 'none';
    document.getElementById('pres-view').style.display = 'flex';
    initMaps();
    refreshMapLayout();
    showSlide(0);
  }}

  function clearVideoPlayer() {{
    const video = document.getElementById('slide-video');
    video.pause();
    video.removeAttribute('src');
    video.load();
  }}

  function goHome() {{
    clearVideoPlayer();
    if (geocodeController) {{
      geocodeController.abort();
      geocodeController = null;
    }}
    document.getElementById('pres-view').style.display = 'none';
    document.getElementById('home-view').style.display = 'block';
    currentAlbumKey = null;
    lastCoords = null;
    lastMiniCoords = null;
  }}

  async function fetchPlaceNameAsync(lat, lon) {{
    const key = `${{lat.toFixed(3)}},${{lon.toFixed(3)}}`;
    const metaPlace = document.getElementById('meta-place');

    if (locationCache[key]) {{
      metaPlace.innerHTML = `📍 ${{locationCache[key]}}`;
      return;
    }}

    if (geocodeController) {{
      geocodeController.abort();
    }}
    geocodeController = new AbortController();

    try {{
      const url = `https://api.maptiler.com/geocoding/${{lon}},${{lat}}.json?key=${{MAPTILER_KEY}}&language=en`;
      const resp = await fetch(url, {{ signal: geocodeController.signal }});
      if (!resp.ok) throw new Error();
      const data = await resp.json();
      
      if (data.features && data.features.length > 0) {{
        const feat = data.features[0];
        const place = feat.text;
        const countryObj = (feat.context || []).find(c => c.id.startsWith('country'));
        const country = countryObj ? countryObj.text : '';
        const result = country && !place.includes(country) ? `${{place}}, ${{country}}` : place;
        locationCache[key] = result;
        metaPlace.innerHTML = `📍 ${{result}}`;
        return;
      }}
      metaPlace.innerHTML = `📍 ${{lat.toFixed(4)}}° N, ${{lon.toFixed(4)}}° E`;
    }} catch (e) {{
      if (e.name !== 'AbortError') {{
        metaPlace.innerHTML = `📍 ${{lat.toFixed(4)}}° N, ${{lon.toFixed(4)}}° E`;
      }}
    }}
  }}

  function moveMapAdaptively(lat, lon) {{
    const target = [lat, lon];
    map.stop();

    if (!lastCoords) {{
      map.setView(target, 14);
    }} else {{
      const dist = map.distance(lastCoords, target);
      if (dist < 50) {{
      }} else if (dist < 5000) {{
        map.panTo(target, {{ animate: true, duration: 0.7 }});
      }} else {{
        map.flyTo(target, 14, {{ duration: 1.1, easeLinearity: 0.2 }});
      }}
    }}
    lastCoords = target;

    if (!lastMiniCoords || map.distance(lastMiniCoords, target) >= 50) {{
      miniMap.setView(target, 6);
      lastMiniCoords = target;
    }}
  }}

  function showSlide(idx) {{
    const album = albums[currentAlbumKey];
    if (!album || idx < 0 || idx >= album.slides.length) return;
    currentIdx = idx;
    const item = album.slides[idx];

    const img = document.getElementById('slide-img');
    const video = document.getElementById('slide-video');
    
    clearVideoPlayer();

    if (item.type === 'video') {{
      img.style.display = 'none';
      img.removeAttribute('src');
      video.style.display = 'block';
      video.src = item.file;
      video.load();
    }} else {{
      video.style.display = 'none';
      img.style.display = 'block';
      img.src = item.file;

      if (idx + 1 < album.slides.length && album.slides[idx + 1].type === 'image') {{
        preloader.src = album.slides[idx + 1].file;
      }}
    }}

    document.getElementById('slide-info').innerText = `${{album.title}} | ${{idx + 1}} / ${{album.slides.length}}`;

    const metaBox = document.getElementById('meta-box');
    const metaPlace = document.getElementById('meta-place');
    const metaDate = document.getElementById('meta-date');

    if (item.date || item.lat !== null) {{
      metaBox.style.display = 'block';
      metaDate.innerHTML = item.date ? `📅 ${{item.date}}` : '';
      metaDate.style.display = item.date ? 'flex' : 'none';
    }} else {{
      metaBox.style.display = 'none';
    }}

    if (item.lat !== null && item.lon !== null) {{
      if (currentMarker) map.removeLayer(currentMarker);
      currentMarker = L.marker([item.lat, item.lon]).addTo(map);

      if (miniMarker) miniMap.removeLayer(miniMarker);
      miniMarker = L.circleMarker([item.lat, item.lon], {{
        radius: 7, fillColor: '#ef4444', color: '#ffffff', weight: 2, opacity: 1, fillOpacity: 0.95
      }}).addTo(miniMap);
      
      if (isMapVisible) {{
        moveMapAdaptively(item.lat, item.lon);
      }}

      metaPlace.innerHTML = '📍 Zjišťuji místo...';
      fetchPlaceNameAsync(item.lat, item.lon);
    }} else {{
      metaPlace.innerHTML = '📍 Poloha není v souboru';
    }}
  }}

  window.addEventListener('keydown', (e) => {{
    if (e.key === 'b' || e.key === 'B') {{
      const b = document.getElementById('blackout');
      b.style.display = b.style.display === 'block' ? 'none' : 'block';
      e.preventDefault();
      return;
    }}
    if (!currentAlbumKey) return;
    
    if (e.key === 'm' || e.key === 'M') {{
      toggleMap();
      e.preventDefault();
      return;
    }}
    
    const video = document.getElementById('slide-video');
    if (e.key === ' ' && video.style.display === 'block') {{
      if (video.paused) video.play(); else video.pause();
      e.preventDefault();
      e.stopPropagation();
      return;
    }}
    
    if (e.key === 'ArrowRight' || e.key === 'PageDown') {{
      showSlide(currentIdx + 1);
      e.preventDefault();
    }} else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {{
      showSlide(currentIdx - 1);
      e.preventDefault();
    }} else if (e.key === 'Escape') {{
      goHome();
      e.preventDefault();
    }}
  }}, true);

  function shutdownApp() {{
    if (confirm("Opravdu chcete prezentaci ukončit a vypnout server?")) {{
      fetch('/shutdown', {{ method: 'POST' }}).then(() => {{
        window.close();
        document.body.innerHTML = '<h2 style="padding:40px;color:#aaa;">Aplikace byla úspěšně ukončena. Můžete zavřít toto okno.</h2>';
      }}).catch(() => {{ window.close(); }});
    }}
  }}
</script>
</body>
</html>
"""

html_path = os.path.join(ROOT_DIR, "index.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(HTML)

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT_DIR, **kwargs)

    def do_POST(self):
        if self.path == '/shutdown':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            print("\nPřijat požadavek na vypnutí. Ukončuji Python server...")
            threading.Thread(target=httpd.shutdown, daemon=True).start()
        else:
            self.send_error(404)

socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("", PORT), CustomHandler)

print(f"Spouštím rozcestník na http://localhost:{PORT}")
webbrowser.open(f"http://localhost:{PORT}/index.html")

try:
    httpd.serve_forever()
finally:
    httpd.server_close()
    print("Server ukončen. Hezký den!")