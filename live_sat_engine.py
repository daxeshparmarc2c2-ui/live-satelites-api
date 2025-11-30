import requests
import math
import time
from sgp4.api import Satrec, jday
from datetime import datetime, timezone

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
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}


# ----------------------------------------------------------
# Convert GP JSON epoch string → Julian date
# ----------------------------------------------------------
def parse_epoch(epoch_str):
    dt = datetime.fromisoformat(epoch_str.replace("Z", ""))
    jd, fr = jday(
        dt.year,
        dt.month,
        dt.day,
        dt.hour,
        dt.minute,
        dt.second + dt.microsecond / 1e6,
    )
    return jd + fr


# ----------------------------------------------------------
# Satellite Engine
# ----------------------------------------------------------
class LiveSatelliteEngine:

    def __init__(self):
        self.sats = {}
        self.load_all_groups()

    def fetch_group(self, group, retries=5):
        url = BASE_URL.format(group)

        for attempt in range(retries):
            try:
                r = requests.get(url, headers=HEADERS, timeout=20)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list) and len(data) > 0:
                        return data
                print(f"⚠️ Retry {attempt+1}/{retries} for {group}")
                time.sleep(1)
            except:
                time.sleep(1)

        print(f"❌ FAILED TO FETCH {group}")
        return []

    def load_all_groups(self):

        for group in CELESTRAK_GROUPS.values():
            data = self.fetch_group(group)
            print(f"📡 Group {group}: fetched {len(data)} satellites")

            for entry in data:

                try:
                    norad = int(entry["NORAD_CAT_ID"])

                    # Convert EVERYTHING to float
                    incl = math.radians(float(entry["INCLINATION"]))
                    raan = math.radians(float(entry["RA_OF_ASC_NODE"]))
                    argp = math.radians(float(entry["ARG_OF_PERICENTER"]))
                    mean_anom = math.radians(float(entry["MEAN_ANOMALY"]))
                    ecc = float(entry["ECCENTRICITY"])
                    mm = float(entry["MEAN_MOTION"])
                    ndot = float(entry["MEAN_MOTION_DOT"])
                    nddot = float(entry["MEAN_MOTION_DDOT"])
                    bstar = float(entry["BSTAR"])

                    epoch = parse_epoch(entry["EPOCH"])

                except Exception as e:
                    print(f"⚠️ Bad numeric data for {entry['NORAD_CAT_ID']}: {e}")
                    continue

                # Build Satrec (positional arguments ONLY)
                try:
                    sat = Satrec()
                    sat.sgp4init(
                        72,         # WGS72
                        'i',        # opsmode
                        norad,
                        epoch,      # epoch as JD
                        bstar,
                        ndot,
                        nddot,
                        ecc,
                        argp,
                        incl,
                        mean_anom,
                        mm,
                        raan
                    )
                except Exception as e:
                    print(f"❌ SGP4 INIT FAIL {norad}: {e}")
                    continue

                self.sats[norad] = {
                    "name": entry["OBJECT_NAME"],
                    "group": group,
                    "satrec": sat,
                    "meta": entry,
                }

            print(f"✔ Total satellites loaded so far: {len(self.sats)}\n")

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
            "lon": lon,
            "lat": lat,
            "alt_km": alt,
            "timestamp": t.isoformat(),
            "meta": self.sats[norad]["meta"],
        }
