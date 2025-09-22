from flask import Flask, render_template, jsonify
import os, requests

app = Flask(__name__)

NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")  # set your key in Replit Secrets

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/asteroids")
def asteroids():
    """
    Simple proxy to NASA NeoWs 'browse' endpoint.
    Returns a simplified list of neos with their orbital_data.
    """
    try:
        url = f"https://api.nasa.gov/neo/rest/v1/neo/browse?api_key={NASA_API_KEY}&size=50"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        raw_neos = data.get("near_earth_objects") or data.get("near_earth_objects", []) or data.get("near_earth_objects", [])
        # sometimes browse returns 'near_earth_objects' as key; make a defensive fallback
        # build a simplified list
        neos = []
        for neo in raw_neos:
            od = neo.get("orbital_data", {})
            neos.append({
                "id": neo.get("id"),
                "name": neo.get("name"),
                "is_hazardous": neo.get("is_potentially_hazardous_asteroid"),
                "orbital_data": {
                    "a": od.get("semi_major_axis"),
                    "e": od.get("eccentricity"),
                    "i": od.get("inclination"),
                    "omega": od.get("perihelion_argument"),           # argument of perihelion
                    "Omega": od.get("ascending_node_longitude"),      # longitude of ascending node
                    "M": od.get("mean_anomaly"),
                    "epoch": od.get("epoch_osculation")
                }
            })
        return jsonify({"neos": neos})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
