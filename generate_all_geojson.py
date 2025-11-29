import json, os, math
from datetime import datetime, timezone
from live_sat_engine import LiveSatelliteEngine

# Load group definitions
with open("groups.json") as f:
    GROUP_MAP = json.load(f)

OUTPUT_DIR = "output"

def safe_num(x):
    """Return float or None if invalid, used for JSON safety."""
    try:
        if x is None: return None
        x = float(x)
        if math.isnan(x) or math.isinf(x): return None
        return x
    except:
        return None

def compute_velocity_km_s(mean_motion_rev_per_day):
    if not mean_motion_rev_per_day:
        return None
    # Mean motion rev/day → km/s
    # 1 rev = 2*pi*Earth radius approx? No, use orbital period:
    period_sec = 86400 / mean_motion_rev_per_day
    mu = 398600.4418  # Earth gravitational parameter km^3/s^2
    a = (mu * (period_sec / (2 * math.pi))**2)**(1/3)
    v = math.sqrt(mu / a)
    return v

def classify_orbit(alt_km):
    if alt_km is None:
        return "Unknown"
    if alt_km < 2000:
        return "LEO"
    elif alt_km < 20000:
        return "MEO"
    elif alt_km < 40000:
        return "GEO"
    else:
        return "HEO"

def write_geojson(path, features):
    data = {
        "type": "FeatureCollection",
        "features": features
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def generate_group_files():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    eng = LiveSatelliteEngine()
    t = datetime.now(timezone.utc)

    # Prepare empty containers for all groups
    group_data = {g: [] for g in GROUP_MAP}

    for norad, sat in eng.sats.items():
        pos = eng.compute_position(norad, t=t)
        if not pos:
            continue

        lon = safe_num(pos["lon"])
        lat = safe_num(pos["lat"])
        alt = safe_num(pos["alt_km"])
        if None in (lon, lat, alt):
            continue

        raw = sat["satrec"]  # raw SGP4 satrec object
        meta = sat.get("meta", {})  # metadata container if available

        # Determine group from name
        name_l = sat["name"].lower()

        for group_name, match_string in GROUP_MAP.items():
            if match_string.lower() in name_l:

                mm = safe_num(meta.get("MEAN_MOTION"))
                velocity = safe_num(compute_velocity_km_s(mm))

                feature = {
                    "type": "Feature",
                    "properties": {
                        # Identifiers
                        "norad_id": norad,
                        "name": sat["name"],
                        "object_id": meta.get("OBJECT_ID"),
                        "object_type": meta.get("OBJECT_TYPE"),
                        "classification_type": meta.get("CLASSIFICATION_TYPE"),

                        # Country / Launch
                        "country": meta.get("COUNTRY"),
                        "launch_date": meta.get("LAUNCH_DATE"),
                        "site_code": meta.get("SITE_CODE"),
                        "decay_date": meta.get("DECAY_DATE"),

                        # Physical / RCS
                        "rcs": safe_num(meta.get("RCS")),

                        # Orbital Parameters
                        "inclination_deg": safe_num(meta.get("INCLINATION")),
                        "eccentricity": safe_num(meta.get("ECCENTRICITY")),
                        "mean_motion_rev_per_day": mm,
                        "mean_motion_dot": safe_num(meta.get("MEAN_MOTION_DOT")),
                        "mean_motion_ddot": safe_num(meta.get("MEAN_MOTION_DDOT")),
                        "raan_deg": safe_num(meta.get("RA_OF_ASC_NODE")),
                        "argp_deg": safe_num(meta.get("ARG_OF_PERICENTER")),
                        "mean_anomaly_deg": safe_num(meta.get("MEAN_ANOMALY")),
                        "period_minutes": safe_num(meta.get("PERIOD")),
                        "perigee_km": safe_num(meta.get("PERIGEE")),
                        "apogee_km": safe_num(meta.get("APOGEE")),
                        "bstar": safe_num(meta.get("BSTAR")),

                        # Computed values
                        "longitude_deg": lon,
                        "latitude_deg": lat,
                        "alt_km": alt,
                        "velocity_km_s": velocity,
                        "orbit_class": classify_orbit(alt),
                        "tle_epoch": meta.get("EPOCH"),
                        "timestamp": pos["time"]
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    }
                }

                group_data[group_name].append(feature)

    # Write all group files
    for group_name, feats in group_data.items():
        path = f"{OUTPUT_DIR}/{group_name}.geojson"
        write_geojson(path, feats)
        print(f"✓ {group_name}.geojson — {len(feats)} features")

    print("\n🎉 ALL GROUPS GENERATED SUCCESSFULLY WITH FULL METADATA")

if __name__ == "__main__":
    generate_group_files()
