#!/usr/bin/env python3
"""query.py — the smallest possible GraphHopper client.

Hit a *running* GraphHopper server's HTTP API and print the answer: the fastest
route between two points, plus (optionally) a matrix cell and an isochrone size.
This is the "ask the engine, read the response" spine used by several labs — it
touches the same endpoints Chapters 1 and 7 dissect from the inside.

No compile, no dependencies: standard-library ``urllib`` only.

Prereqs — start a GraphHopper server first (Chapter 0 §0.3):
    java -Ddw.graphhopper.datareader.file=some-city.osm.pbf \\
         -jar web/target/graphhopper-web-*.jar server config-example.yml
    # server now listening on http://localhost:8989

Usage:
    python3 query.py 52.517,13.389 52.508,13.421              # route (profile=car)
    python3 query.py 52.517,13.389 52.508,13.421 --profile bike
    python3 query.py 52.517,13.389 52.508,13.421 --isochrone 600
    python3 query.py --host http://localhost:8989 A B

Each ``point`` is ``lat,lon``. With no publisher/server running you'll get a clear
connection error — which is itself the lesson that the engine is a separate service
your app talks to over HTTP (Chapter 1).
"""
import sys
import json
import urllib.request
import urllib.parse
import urllib.error

DEFAULT_HOST = "http://localhost:8989"


def _get(url: str) -> dict:
    """GET a URL and parse JSON, surfacing GraphHopper's error envelope clearly."""
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:  # GraphHopper returns JSON errors with a body
        body = e.read().decode("utf-8", "replace")
        try:
            msg = json.loads(body).get("message", body)
        except json.JSONDecodeError:
            msg = body
        sys.stderr.write(f"HTTP {e.code} from {url}\n  {msg}\n")
        sys.exit(1)
    except urllib.error.URLError as e:
        sys.stderr.write(
            f"Could not reach GraphHopper at {url}\n  {e.reason}\n"
            "Start the server first (see this file's docstring / Chapter 0 §0.3).\n"
        )
        sys.exit(1)


def route(host: str, a: str, b: str, profile: str) -> None:
    q = urllib.parse.urlencode(
        [("point", a), ("point", b), ("profile", profile),
         ("points_encoded", "false"), ("instructions", "true")]
    )
    data = _get(f"{host}/route?{q}")
    path = data["paths"][0]
    km = path["distance"] / 1000.0
    mins = path["time"] / 60000.0
    pts = len(path["points"]["coordinates"])
    turns = len(path.get("instructions", []))
    print(f"route  profile={profile:5s}  {km:7.3f} km  {mins:6.1f} min  "
          f"{pts:5d} geometry pts  {turns:3d} instructions")
    for ins in path.get("instructions", [])[:6]:
        d = ins["distance"]
        print(f"    · {ins['text']:40s} {d:7.1f} m  (sign {ins['sign']:+d})")
    if turns > 6:
        print(f"    … {turns - 6} more")


def isochrone(host: str, center: str, seconds: int, profile: str) -> None:
    q = urllib.parse.urlencode(
        [("point", center), ("profile", profile),
         ("time_limit", str(seconds)), ("buckets", "1")]
    )
    data = _get(f"{host}/isochrone?{q}")
    poly = data["polygons"][0]["geometry"]["coordinates"][0]
    print(f"isochrone  {seconds}s from {center}  →  reachable polygon with {len(poly)} vertices")


def main(argv):
    host = DEFAULT_HOST
    profile = "car"
    iso = None
    pts = []
    it = iter(argv)
    for tok in it:
        if tok == "--host":
            host = next(it)
        elif tok == "--profile":
            profile = next(it)
        elif tok == "--isochrone":
            iso = int(next(it))
        else:
            pts.append(tok)
    if iso is not None and pts:
        isochrone(host, pts[0], iso, profile)
        return
    if len(pts) < 2:
        print(__doc__)
        return
    route(host, pts[0], pts[1], profile)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        sys.exit(0)
