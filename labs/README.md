# Labs

Hands-on counterparts to each chapter. Run them beside the pinned clone (`../graphhopper`).

## What's here

- **`lab00-build.md` … `lab08-pr.md`** — one note template per chapter lab. Fill them in as you go;
  they're **your** proof you ran the thing and saw the expected result, and they make Chapter 8's re-sync
  and capstone far easier.
- **`query_route/`** — a minimal, self-contained "ask the engine and print the answer" client with **no
  build and no dependencies** (stdlib `urllib` only). It hits a running GraphHopper server's `/route` and
  `/isochrone` endpoints and is reused by Labs 1, 3, 5, 7, and the capstone.
  `python3 query_route/query.py 52.517,13.389 52.508,13.421`.

## How labs work

Each chapter ends with a 🧪 lab pointing here. Labs split into two kinds:

- **Read-only labs (Chapters 1, 2, 3, 4, 6):** `grep` and short reads against the clone, plus a couple of
  `java -jar … import`/measurement runs — they confirm the structure you just read in source. No app needed.
- **Server labs (Chapters 0, 5, 7, 8):** start a local GraphHopper server on a small `.osm.pbf` (Chapter 0
  §0.3) and query it with `query_route/query.py` or `curl`. Chapter 5 additionally imports a small GTFS feed.

> 💡 **Small extracts only.** Import a *city*-sized `.osm.pbf` from Geofabrik, not a whole country. The
> import is what takes memory and time; the queries are instant. Everything in these labs runs on a laptop.

> 📌 **Nothing heavy in git.** The labs never commit OSM extracts, GTFS feeds, or the `graph-cache/`
> import directory — they're large and reproducible. `.gitignore` keeps them out.

## Lab index

| Lab | Chapter | Kind | Goal |
|-----|---------|------|------|
| `lab00-build.md` | 00 | server | Pinned clone; build the modules; run the server; first route |
| `lab01-trace.md` | 01 | read-only | Trace one `/route` request from resource → `route()` → `ResponsePath` |
| `lab02-graph.md` | 02 | read-only | Count nodes/edges; sweep one node's edges with `EdgeExplorer` |
| `lab03-algorithms.md` | 03 | read-only | Compare Dijkstra vs A* vs CH: nodes visited & shortcut count |
| `lab04-profiles.md` | 04 | read-only | Write a `custom_model`; watch a route change; read encoded values |
| `lab05-transit.md` | 05 | server | Import a GTFS feed; run a `pt` query; read the legs & transfers |
| `lab06-matching.md` | 06 | read-only | Match a synthetic GPS trace; read the emission/transition split |
| `lab07-web.md` | 07 | server | Hit `/route`, `/matrix`, `/isochrone`, `/mvt` and read the envelopes |
| `lab08-pr.md` | 08 | server | Re-pin, re-verify citations, read a merged PR unaided |
