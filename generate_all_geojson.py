import json
from datetime import datetime, timezone
from live_sat_engine import LiveSatelliteEngine

OUTPUT_DIR = "output/"

def classify_orbit(alt):
    if alt < 2000:
        return "LEO"
    if alt < 35786:
        return "MEO"
    if 35700 <= alt <= 36000:
        return "GEO"
    return "HEO"


def generate_all():
    engine = LiveSatelliteEngine()
    grouped = {g: [] for g in engine.CELESTRAK_GROUPS.values()}

    for norad, sat in engine.sats.items():
        pos = engine.compute_position(norad)
        if pos is None:
            continue

        meta = pos["meta"]

        feature = {
            "type": "Feature",
            "properties": {
                **meta,  # include ALL metadata automatically
                "norad_id": norad,
                "name": sat["name"],
                "group": sat["group"],
                "longitude_deg": pos["lon"],
                "latitude_deg": pos["lat"],
                "alt_km": pos["alt_km"],
                "orbit_class": classify_orbit(pos["alt_km"]),
                "timestamp": pos["timestamp"],
            },
            "geometry": {
                "type": "Point",
                "coordinates": [pos["lon"], pos["lat"]],
            },
        }

        grouped[sat["group"]].append(feature)

    for group, features in grouped.items():
        geojson = {"type": "FeatureCollection", "features": features}
        with open(f"{OUTPUT_DIR}{group}.geojson", "w") as f:
            json.dump(geojson, f, indent=2)

        print(f"✔ {group}.geojson → {len(features)} satellites")


if __name__ == "__main__":
    generate_all()

