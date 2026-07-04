# query_route — the minimal GraphHopper client

`query.py` is a ~120-line, **dependency-free** (stdlib `urllib` only) client for a
*running* GraphHopper server. It is the "ask the engine, read the response" spine
reused by Labs 1, 3, 5, 7, and the capstone.

## What it shows you

The routing engine is a **service your app talks to over HTTP** — the same shape as
BusMap or a ride-hailing backend calling a routing microservice. `query.py` hits the
exact endpoints Chapter 1 traces from the outside and Chapter 7 dissects from the inside:

- `/route` — the fastest path A→B: distance, time, geometry, turn-by-turn instructions.
- `/isochrone` — everywhere reachable within N seconds (the "coverage" query).

## Run it

First start a server (Chapter 0 §0.3) on a small extract, then:

```bash
python3 query.py 52.517,13.389 52.508,13.421              # route (profile=car)
python3 query.py 52.517,13.389 52.508,13.421 --profile bike
python3 query.py 52.517,13.389 52.508,13.421 --isochrone 600
python3 query.py --host http://localhost:8989 A B
```

Each point is `lat,lon`. With **no server running** you get a clear connection error —
which is itself the Chapter 1 lesson: the engine is a separate process reached over HTTP,
not a library linked into your app.

> ⚠️ Use points that fall **inside** the extent of the `.osm.pbf` you imported, or
> GraphHopper returns a "point not found / out of bounds" error. The defaults above are
> in central Berlin; swap them for coordinates in your own extract.
