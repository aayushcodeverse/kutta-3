import os
import time
import requests
from flask import Flask, render_template, jsonify, request, send_from_directory
# Environment variables are handled directly by Replit

NASA_API_KEY = os.getenv("NASA_API_KEY")  # set this in environment
if not NASA_API_KEY:
    print("WARNING: NASA_API_KEY not set. Some endpoints will fail until you set it.")

app = Flask(__name__, static_folder="static", template_folder="templates")

# Simple in-memory cache: { key: (timestamp, ttl_seconds, data) }
_cache = {}

def cache_get(key):
    item = _cache.get(key)
    if not item:
        return None
    ts, ttl, data = item
    if time.time() - ts > ttl:
        del _cache[key]
        return None
    return data

def cache_set(key, data, ttl=300):
    _cache[key] = (time.time(), ttl, data)

@app.route("/")
def index():
    return render_template("index.html")

# Proxy APOD (Astronomy Picture of the Day)
@app.route("/api/apod")
def api_apod():
    key = "apod"
    data = cache_get(key)
    if data:
        return jsonify(data)
    url = "https://api.nasa.gov/planetary/apod"
    params = {"api_key": NASA_API_KEY or "DEMO_KEY"}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    cache_set(key, data, ttl=60*30)  # 30 minutes
    return jsonify(data)

# Search NASA images (uses images-api.nasa.gov, doesn't require API key)
@app.route("/api/search_images")
def api_search_images():
    q = request.args.get("q", "mars")
    page = request.args.get("page", "1")
    key = f"search_images:{q}:{page}"
    data = cache_get(key)
    if data:
        return jsonify(data)
    url = "https://images-api.nasa.gov/search"
    params = {"q": q, "media_type": "image", "page": page}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    js = r.json()
    # pick top results and return useful fields
    items = []
    for it in js.get("collection", {}).get("items", [])[:12]:
        link = None
        links = it.get("links")
        if links and isinstance(links, list):
            link = links[0].get("href")
        data_item = {
            "title": (it.get("data") or [{}])[0].get("title"),
            "nasa_id": (it.get("data") or [{}])[0].get("nasa_id"),
            "date_created": (it.get("data") or [{}])[0].get("date_created"),
            "href": link
        }
        items.append(data_item)
    data = {"q": q, "results": items}
    cache_set(key, data, ttl=60*15)  # 15 min
    return jsonify(data)

# Example: Near-Earth Objects feed (today)
@app.route("/api/neo/today")
def api_neo_today():
    # Use today's date range
    from datetime import date
    today = date.today().isoformat()
    key = f"neo:{today}"
    data = cache_get(key)
    if data:
        return jsonify(data)
    url = "https://api.nasa.gov/neo/rest/v1/feed"
    params = {"start_date": today, "end_date": today, "api_key": NASA_API_KEY or "DEMO_KEY"}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    js = r.json()
    # keep compact
    simplified = {"element_count": js.get("element_count", 0), "near_earth_objects": {}}
    neos = js.get("near_earth_objects", {}).get(today, [])
    simplified["near_earth_objects"][today] = [
        {
            "id": n.get("id"),
            "name": n.get("name"),
            "is_potentially_hazardous": n.get("is_potentially_hazardous_asteroid"),
            "estimated_diameter_m_min": n.get("estimated_diameter", {}).get("meters", {}).get("estimated_diameter_min"),
            "estimated_diameter_m_max": n.get("estimated_diameter", {}).get("meters", {}).get("estimated_diameter_max"),
            "close_approach_data": n.get("close_approach_data", [])[:1]  # first approach
        } for n in neos
    ]
    cache_set(key, simplified, ttl=60*30)
    return jsonify(simplified)

# Asteroids endpoint for the 3D viewer
@app.route("/asteroids")
def asteroids():
    """
    Simple proxy to NASA NeoWs 'browse' endpoint.
    Returns a simplified list of neos with their orbital_data.
    """
    try:
        url = f"https://api.nasa.gov/neo/rest/v1/neo/browse?api_key={NASA_API_KEY or 'DEMO_KEY'}&size=50"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        raw_neos = data.get("near_earth_objects", [])
        # build a simplified list
        neos = []
        for neo in raw_neos:
            od = neo.get("orbital_data", {})
            neos.append({
                "id": neo.get("id"),
                "name": neo.get("name"),
                "diameter": neo.get("estimated_diameter", {}).get("meters", {}).get("estimated_diameter_max", 100),
                "is_hazardous": neo.get("is_potentially_hazardous_asteroid"),
                "orbit": {
                    "semi_major_axis": float(od.get("semi_major_axis", "1.5")),
                    "eccentricity": float(od.get("eccentricity", "0.1")),
                    "inclination": float(od.get("inclination", "0.0"))
                }
            })
        return jsonify(neos)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

# Static file fallback (if needed)
@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

if __name__ == "__main__":
    # development server
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
