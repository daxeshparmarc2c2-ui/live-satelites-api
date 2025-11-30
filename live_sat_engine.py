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
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def gp_json_to_tle(entry):
    satnum = int(entry["NORAD_CAT_ID"])
    classif = "U"

    intldes = entry.get("OBJECT_ID", "00000A").replace("-", "")

    epoch = entry["EPOCH"].replace("Z", "")
    dt = datetime.fromisoformat(epoch)

    epoch_year = dt.year % 100
    epoch_day = (
        dt.timetuple().tm_yday +
        (dt.hour / 24) +
        (dt.minute / 1440) +
        (dt.second / 86400)
    )

    line1 = (
        f"1 {satnum:05d}{classif} {intldes:8s} "
        f"{epoch_year:02d}{epoch_day:012.8f} "
        f"{float(entry['MEAN_MOTION_DOT']): .8f} "
        f"{float(entry['MEAN_MOTION_DDOT']): .8f} "
        f"{float(entry['BSTAR']): .8f} 0 9999"
    )

    ecc_scaled = int(float(entry["ECCENTRICITY"]) * 1e7)

    line2 = (
        f"2 {satnum:05d} "
        f"{float(entry['INCLINATION']):8.4f} "
        f"{float(entry['RA_OF_ASC_NODE']):8.4f} "
        f"{ecc_scaled:07d} "
        f"{float(entry['ARG_OF_PERICENTER']):8.4f} "
        f"{float(entry['MEAN_ANOMALY']):8.4f} "
        f"{float(entry['MEAN_MOTION']):11.8f} 0"
    )

    return line1, line2


class LiveSatelliteEngine:

    CELESTRAK_GROUPS = CELESTRAK_GROUPS

    def __init__(self):
        self.sats = {}
        self.load_all_groups()

    def fetch_group(self, group):
        url = BASE_URL.format(group)
        for _ in range(3):
            try:
                r = requests.get(url, headers=HEADERS, timeout=20)
                if r.status_code == 200:
                    return r.json()
            except:
                time.sleep(1)
        return []

    def load_all_groups(self):
        for group in CELESTRAK_GROUPS.values():
            data = self.fetch_group(group)
            print(f"📡 Loaded {len(data)} from {group}")

            for entry in data:
                try:
                    line1, line2 = gp_json_to_tle(entry)
                    satrec = Satrec.twoline2rv(line1, line2)
                except Exception as e:
                    print(f"❌ TLE error {entry['NORAD_CAT_ID']}: {e}")
                    continue

                norad = entry["NORAD_CAT_ID"]

                self.sats[norad] = {
                    "name": entry.get("OBJECT_NAME"),
                    "group": group,
                    "meta": entry,
                    "satrec": satrec,
                }

    def compute_position(self, norad):
        if norad not in self.sats:
            return None

        sat = self.sats[norad]["satrec"]
        t = datetime.now(timezone.utc)

        jd, fr = jday(
            t.year, t.month, t.day,
            t.hour, t.minute, t.second + t.microsecond / 1e6
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
            "lon": lon,
            "lat": lat,
            "alt_km": alt,
            "timestamp": t.isoformat(),
            "meta": self.sats[norad]["meta"],
            "name": self.sats[norad]["name"],
            "group": self.sats[norad]["group"],
        }
