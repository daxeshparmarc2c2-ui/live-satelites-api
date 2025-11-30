import requests
import math
import time
from sgp4.api import Satrec, jday
from datetime import datetime, timezone

# ----------------------------------------------------------
# Celestrak Groups
# ----------------------------------------------------------
CELESTRAK_GROUPS = {
    "last-30-days": "last-30-days",
    "stations": "stations",
    "active": "active",
    "weather": "weather",
    "resource": "resource",
    "dmc": "dmc",
    "intelsat": "intelsat",
    "eutelsat": "eutelsat",
    "starlink": "starlink",
    "gnss": "gnss",
    "gps-ops": "gps-ops",
    "glo-ops": "glo-ops",
    "galileo": "galileo",
    "beidou": "beidou",
    "nnss": "nnss",
    "musson": "musson",
    "cosmos-1408-debris": "cosmos-1408-debris",
    "fengyun-1c-debris": "fengyun-1c-debris",
    "iridium-33-debris": "iridium-33-debris",
    "cosmos-2251-debris": "cosmos-2251-debris",
}

BASE_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP={}&FORMAT=json"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

# ----------------------------------------------------------
# Convert Celestrak GP JSON → TLE LINES
# ----------------------------------------------------------
def gp_json_to_tle(entry):
    """Convert GP JSON entry → TLE line1, line2."""

    satnum = int(entry["NORAD_CAT_ID"])
    classification = "U"

    intldes = entry["OBJECT_ID"] if "OBJECT_ID" in entry else "00000A"
    intldes = intldes.replace("-", "")

    epoch_str = entry["EPOCH"]
    dt = datetime.fromisoformat(epoch_str.replace("Z", ""))

    epoch_year = dt.year % 100
    epoch_day = dt.timetuple().tm_yday + (
        dt.hour / 24 + dt.minute / (24 * 60) + dt.second / 86400
    )

    ndot = float(entry["MEAN_MOTION_DOT"])
    nddot = float(entry["MEAN_MOTION_DDOT"])
    bstar = float(entry["BSTAR"])

    line1 = (
        f"1 {satnum:05d}{classification} {intldes:8s} "
        f"{epoch_year:02d}{epoch_day:012.8f} "
        f"{ndot: .8f} {nddot: .8f} {bstar: .8f} 0 9999"
    )

    inc = float(entry["INCLINATION"])
    raan = float(entry["RA_OF_ASC_NODE"])
    ecc = float(entry["ECCENTRICITY"]) * 1e7
    argp = float(entry["ARG_OF_PERICENTER"])
    mean_anom = float(entry["MEAN_ANOMALY"])
    mm = float(entry["MEAN_MOTION"])

    line2 = (
        f"2 {satnum:05d} {inc:8.4f} {raan:8.4f} "
        f"{int(ecc):07d} {argp:8.4f} {mean_anom:8.4f} {mm:11.8f} 0"
    )

    return line1, line2


# ----------------------------------------------------------
# Satellite Engine
# ----------------------------------------------------------
class LiveSatelliteEngine:

    def __init__(self):
        self.sats = {}
        self.load_all_groups()

    def fetch_group(self, group):
        url = BASE_URL.format(group)
        for attempt in range(5):
            try:
                r = requests.get(url, headers=HEADERS, timeout=20)
                if r.status_code == 200:
                    data = r.json()
                    if len(data) > 0:
                        return data
            except:
                pass
            time.sleep(1)
        return []

    def load_all_groups(self):
        for group in CELESTRAK_GROUPS.values():
            data = self.fetch_group(group)
            print(f"📡 Group {group}: fetched {len(data)} satellites")

            for entry in data:
                try:
                    line1, line2 = gp_json_to_tle(entry)
                    satrec = Satrec.twoline2rv(line1, line2)
                except Exception as e:
                    print(f"❌ TLE build failed for {entry['NORAD_CAT_ID']}: {e}")
                    continue

                norad = entry["NORAD_CAT_ID"]
                self.sats[norad] = {
                    "name": entry["OBJECT_NAME"],
                    "group": group,
                    "satrec": satrec,
                    "meta": entry,
                }

            print(f"✔ Total loaded so far: {len(self.sats)}\n")

    def compute_position(self, norad, t=None):
        if norad not in self.sats:
            return None

        if t is None:
            t = datetime.now(timezone.utc)

        sat = self.sats[norad]["satrec"]

        jd, fr = jday(
            t.year,
            t.month,
            t.day,
            t.hour,
            t.minute,
            t.second + t.microsecond / 1e6,
        )

        e, r, v = sat.sgp4(jd, fr)

        if e != 0:
            return None

        x, y, z = r

        lon = math.degrees(math.atan2(y, x))
        hyp = math.sqrt(x*x + y*y)
        lat = math.degrees(math.atan2(z, hyp))
        alt = math.sqrt(x*x + y*y + z*z) - 6378.137

        return {
            "norad_id": norad,
            "name": self.sats[norad]["name"],
            "group": self.sats[norad]["group"],
            "lon": lon,
            "lat": lat,
            "alt_km": alt,
            "timestamp": t.isoformat(),
            "meta": self.sats[norad]["meta"],
        }
