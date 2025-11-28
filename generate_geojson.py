import json
from datetime import datetime, timezone
from live_sat_engine import LiveSatelliteEngine  # your uploaded file

OUTPUT = "live_satellites.geojson"

def build_geojson():
    eng = LiveSatelliteEngine()
    features = []

    # compute for all satellites in your engine
    t = datetime.now(timezone.utc)

    for norad, obj in eng.sats.items():
        pos = eng.compute_position(norad, t=t)
        if not pos:
            continue
        
        feat = {
            "type": "Feature",
            "properties": {
                "norad_id": pos["NORAD"],
                "name": pos["name"],
                "alt_km": pos["alt_km"],
                "timestamp": pos["time"]
            },
            "geometry": {
                "type": "Point",
                "coordinates": [pos["lon"], pos["lat"]]
            }
        }
        features.append(feat)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    with open(OUTPUT, "w") as f:
        json.dump(geojson, f, indent=2)

    print(f"✅ Saved {len(features)} satellite positions → {OUTPUT}")

if __name__ == "__main__":
    build_geojson()
