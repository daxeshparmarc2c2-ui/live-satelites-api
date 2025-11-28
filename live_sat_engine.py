import requests
from datetime import datetime, timezone
from math import atan2, asin, sqrt, degrees, radians, pi
from sgp4.api import Satrec

GROUPS = [
    "last-30-days",
    "stations",
    "active",
    "weather",
    "resource",
    "dmc",
    "intelsat",
    "eutelsat",
    "starlink",
    "gnss",
    "gps-ops",
    "glo-ops",
    "galileo",
    "beidou",
    "nnss",
    "musson",
    "cosmos-1408-debris",
    "fengyun-1c-debris",
    "iridium-33-debris",
    "cosmos-2251-debris",
]


def safe_float(x, key, default=0.0):
    try:
        return float(x.get(key, default))
    except:
        return default


def epoch_to_sgp4(rec):
    # Use EPOCHJD if available
    if "EPOCHJD" in rec:
        return float(rec["EPOCHJD"]) - 2433281.5

    # Otherwise parse ISO8601 timestamp
    t = rec.get("EPOCH")
    if not t:
        raise KeyError("No EPOCH or EPOCHJD")

    t = t.replace("Z", "")
    dt = datetime.fromisoformat(t)

    # Convert datetime → Julian Date
    day_fraction = (
        dt.hour*3600 + dt.minute*60 + dt.second + dt.microsecond/1e6
    ) / 86400

    jd = dt.toordinal() + 1721424.5 + day_fraction
    return jd - 2433281.5


class LiveSatelliteEngine:
    def __init__(self):
        self.sats = {}
        self.load()

    def load(self):
        print("🔄 Downloading satellites...")
        all_records = []

        for g in GROUPS:
            url = f"https://celestrak.org/NORAD/elements/gp.php?GROUP={g}&FORMAT=json"
            print("🌐", url)
            try:
                r = requests.get(url, timeout=20)
                r.raise_for_status()
                rec = r.json()
                if isinstance(rec, list):
                    all_records.extend(rec)
            except Exception as e:
                print("⚠️", e)

        print(f"📦 Retrieved {len(all_records)} records")
        self.build_sgp4(all_records)

    def build_sgp4(self, records):
        for r in records:
            try:
                norad = int(r["NORAD_CAT_ID"])

                # ---- Epoch ----
                epoch = epoch_to_sgp4(r)

                # ---- Convert units ----
                inc = radians(safe_float(r, "INCLINATION"))
                raan = radians(safe_float(r, "RA_OF_ASC_NODE"))
                argp = radians(safe_float(r, "ARG_OF_PERICENTER"))
                manom = radians(safe_float(r, "MEAN_ANOMALY"))

                # Mean motion: rev/day → rad/min
                mm_rev_day = safe_float(r, "MEAN_MOTION")
                mm = mm_rev_day * 2*pi / 1440.0

                # n-dot, n-ddot conversions
                ndot = safe_float(r, "MEAN_MOTION_DOT") * (2*pi / 1440**2)
                nddot = safe_float(r, "MEAN_MOTION_DDOT") * (2*pi / 1440**3)

                ecc = safe_float(r, "ECCENTRICITY")
                bstar = safe_float(r, "BSTAR")

                sat = Satrec()
                sat.sgp4init(
                    0, 'i', norad,
                    epoch, bstar,
                    ndot, nddot,
                    ecc, argp,
                    inc, manom,
                    mm, raan,
                )

                self.sats[norad] = {
                    "name": r.get("OBJECT_NAME", "").strip(),
                    "satrec": sat
                }

            except Exception as e:
                print(f"⚠️ Failed SGP4 for {r.get('NORAD_CAT_ID')}: {e}")

        print(f"✅ Built {len(self.sats)} SGP4 satellites")

    def compute_position(self, norad, t=None):
        item = self.sats.get(norad)
        if not item:
            return None

        sat = item["satrec"]
        t = t or datetime.now(timezone.utc)

        # Julian Date
        jd = t.toordinal() + 1721424.5
        fr = (t.hour*3600 + t.minute*60 + t.second + t.microsecond/1e6)/86400

        code, r, v = sat.sgp4(jd, fr)
        if code != 0:
            return None

        x, y, z = r
        rho = sqrt(x*x + y*y + z*z)

        lat = degrees(asin(z / rho))
        lon = degrees(atan2(y, x))
        alt = rho - 6378.137  # km

        return {
            "NORAD": norad,
            "name": item["name"],
            "lat": lat,
            "lon": lon,
            "alt_km": alt,
            "time": t.isoformat()
        }


if __name__ == "__main__":
    eng = LiveSatelliteEngine()

    print("\n🛰 Testing ISS (25544):")
    print(eng.compute_position(25544))

    print("\n📡 Testing 5:")
    i = 0
    for sid in eng.sats:
        print(eng.compute_position(sid))
        i += 1
        if i == 5:
            break
