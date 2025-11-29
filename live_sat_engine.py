import requests
import math
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
    "cosmos-2251-debris": "cosmos-2251-debris"
}

BASE_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP={}&FORMAT=json"


class LiveSatelliteEngine:

    def __init__(self):
        self.sats = {}
        self.load_all_groups()

    def fetch_group(self, group):
        url = BASE_URL.format(group)
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        return r.json()

    def load_all_groups(self):
        for group in CELESTRAK_GROUPS.values():
            try:
                print(f"Loading {group}...")
                data = self.fetch_group(group)

                for entry in data:

                    norad = entry["NORAD_CAT_ID"]
                    name = entry["OBJECT_NAME"]

                    # Convert degrees to radians
                    incl = math.radians(entry["INCLINATION"])
                    raan = math.radians(entry["RA_OF_ASC_NODE"])
                    argp = math.radians(entry["ARG_OF_PERICENTER"])
                    mean_anom = math.radians(entry["MEAN_ANOMALY"])

                    # Create satrec correctly using GP JSON
                    satrec = Satrec()
                    satrec.sgp4init(
                        WGS84=False,
                        opsmode='i',
                        satnum=norad,
                        epoch=entry["EPOCH"],             # already in JD
                        bstar=entry["BSTAR"],
                        ndot=entry["MEAN_MOTION_DOT"],
                        nddot=entry["MEAN_MOTION_DDOT"],
                        ecco=entry["ECCENTRICITY"],
                        argpo=argp,
                        inclo=incl,
                        mo=mean_anom,
                        no_kozai=entry["MEAN_MOTION"],
                        nodeo=raan
                    )

                    self.sats[norad] = {
                        "name": name,
                        "group": group,
                        "satrec": satrec,
                        "meta": entry
                    }

            except Exception as e:
                print(f"Error loading {group}: {e}")

    def compute_position(self, norad, t=None):
        if norad not in self.sats:
            return None

        if t is None:
            t = datetime.now(timezone.utc)

        satrec = self.sats[norad]["satrec"]
        jd, fr = jday(t.year, t.month, t.day, t.hour, t.minute, t.second + t.microsecond/1e6)

        e, r, v = satrec.sgp4(jd, fr)
        if e != 0:
            return None  # SGP4 error

        x, y, z = r

        lon = math.degrees(math.atan2(y, x))
        hyp = math.sqrt(x*x + y*y)
        lat = math.degrees(math.atan2(z, hyp))
        alt_km = math.sqrt(x*x + y*y + z*z) - 6378.137

        return {
            "NORAD": norad,
            "name": self.sats[norad]["name"],
            "group": self.sats[norad]["group"],
            "lon": lon,
            "lat": lat,
            "alt_km": alt_km,
            "time": t.isoformat()
        }


