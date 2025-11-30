import requests
import math
import time
from sgp4.api import Satrec, jday
from datetime import datetime, timezone

# -------------------------------------
# Celestrak Groups
# -------------------------------------
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
}

# -------------------------------------
# Satellite Engine
# -------------------------------------

class LiveSatelliteEngine:

    def __init__(self):
        self.sats = {}
        self.load_all_groups()

    def fetch_group(self, group, retries=5):
        """Fetch JSON with retry (fixes Cloudflare blocks)."""

        url = BASE_URL.format(group)

        for attempt in range(retries):
            try:
                r = requests.get(url, headers=HEADERS, timeout=25)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list) and len(data) > 0:
                        return data

                print(f"⚠️ Retry {attempt+1}/{retries} for {group}")
                time.sleep(2)

            except Exception as e:
                print(f"⚠️ Error fetching {group}: {e}")
                time.sleep(2)

        print(f"❌ FAILED TO DOWNLOAD: {group}")
        return []

    def load_all_groups(self):
        """Load all GP JSON groups and build satrec objects."""

        for group in CELESTRAK_GROUPS.values():
            data = self.fetch_group(group)

            print(f"📡 Group {group}: fetched {len(data)} satellites")

            if len(data) == 0:
                continue

            for entry in data:
                norad = entry["NORAD_CAT_ID"]

                try:
                    incl = math.radians(entry["INCLINATION"])
                    raan = math.radians(entry["RA_OF_ASC_NODE"])
                    argp = math.radians(entry["ARG_OF_PERICENTER"])
                    mean_anom = math.radians(entry["MEAN_ANOMALY"])
                except:
                    print(f"⚠️ Bad angle data for {norad}")
                    continue

                # SGP4 Init (your version of sgp4 ONLY accepts positional arguments)
                try:
                    satrec = Satrec()
                    satrec.sgp4init(
                        72,                        # WGS72 gravity model
                        'i',                       # opsmode
                        norad,                     # satellite number
                        entry["EPOCH"],            # epoch (JD)
                        entry["BSTAR"],            # drag
                        entry["MEAN_MOTION_DOT"],  # ndot
                        entry["MEAN_MOTION_DDOT"], # nddot
                        entry["ECCENTRICITY"],     # eccentricity
                        argp,                      # argument of perigee (rad)
                        incl,                      # inclination (rad)
                        mean_anom,                 # mean anomaly (rad)
                        entry["MEAN_MOTION"],      # mean motion (rev/day)
                        raan                       # RAAN (rad)
                    )
                except Exception as e:
                    print(f"❌ SGP4 INIT FAIL {norad}: {e}")
                    continue

                # Save into memory
                self.sats[norad] = {
                    "name": entry["OBJECT_NAME"],
                    "group": group,
                    "satrec": satrec,
                    "meta": entry,
                }

            print(f"✔ Total satellites loaded so far: {len(self.sats)}\n")

    def compute_position(self, norad, t=None):
        if norad not in self.sats:
            return None

        if t is None:
            t = datetime.now(timezone.utc)

        satrec = self.sats[norad]["satrec"]

        jd, fr = jday(
            t.year,
            t.month,
            t.day,
            t.hour,
            t.minute,
            t.second + t.microsecond / 1e6,
        )

        e, r, v = satrec.sgp4(jd, fr)
        if e != 0:
            return None

        x, y, z = r

        lon = math.degrees(math.atan2(y, x))
        hyp = math.sqrt(x*x + y*y)
        lat = math.degrees(math.atan2(z, hyp))
        alt_km = math.sqrt(x*x + y*y + z*z) - 6378.137

        return {
            "norad_id": norad,
            "name": self.sats[norad]["name"],
            "group": self.sats[norad]["group"],
            "lon": lon,
            "lat": lat,
            "alt_km": alt_km,
            "timestamp": t.isoformat(),
            "meta": self.sats[norad]["meta"],
        }


