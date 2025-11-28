import json, os
from datetime import datetime, timezone
from live_sat_engine import LiveSatelliteEngine

# Load groups from groups.json
with open("groups.json") as f:
    GROUP_MAP = json.load(f)

OUTPUT_DIR = "output"

def safe_coord(x):
    """Ensures coordinates are GIS safe"""
    if x is None: return None
    if isinstance(x, float) and (x != x): return None # NaN
    return x

def generate_group_files():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    eng = LiveSatelliteEngine()
    t = datetime.now(timezone.utc)

    # Prepare empty containers
    group_data = {g: [] for g in GROUP_MAP}

    # Loop through satellites
    for norad, sat in eng.sats.items():

        pos = eng.compute_position(norad, t=t)
        if not pos:
            continue

        # Check group
        name = sat["name"].lower()

        for out_name, word in GROUP_MAP.items():
            if word in name:
                # Validate coordinates
                lon = safe_coord(pos["lon"])
                lat = safe_coord(pos["lat"])
                alt_km = safe_coord(pos["alt_km"])

                if None in (lon, lat, alt_km):
                    continue

                feature = {
                    "type": "Feature",
                    "properties": {
                        "norad_id": pos["NORAD"],
                        "name": pos["name"],
                        "alt_km": pos["alt_km"],
                        "timestamp": pos["time"]
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    }
                }

                group_data[out_name].append(feature)

    # Write each group to separate GeoJSON file
    for out_name, feats in group_data.items():
        out_path = f"{OUTPUT_DIR}/{out_name}.geojson"

        geo = {
            "type": "FeatureCollection",
            "features": feats
        }

        with open(out_path, "w") as f:
            json.dump(geo, f, indent=2)

        print(f"✓ Saved → {out_path} ({len(feats)} features)")

    print("\n🎉 All group GeoJSON files generated successfully!")

if __name__ == "__main__":
    generate_group_files()
