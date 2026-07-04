# GraphHopper Internals Handbook

> A **RumitX** from-the-source study guide for [`graphhopper/graphhopper`](https://github.com/graphhopper/graphhopper),
> pinned to **`11.0`** (short SHA `69e50f6`). Read it with the source open beside you.

GraphHopper is one of the most readable production routing engines in the open-source world: give it an
OpenStreetMap extract and it will find the fastest route across a continent in a millisecond, plan a
public-transit journey from a GTFS feed, snap a noisy GPS trace back onto the roads a driver actually
took, and serve all of it over a clean HTTP API. Every line of it is on GitHub, in Java. This book takes
that gift seriously: we trace a *single `/route` request* from the HTTP endpoint down to the shortest-path
algorithm and back out as turn-by-turn instructions, citing the exact `file:line` where each thing happens.

This is **not** a "how to deploy GraphHopper" tutorial and **not** an API-reference paraphrase. It is an
engineer's tour of *how the software is built* — the kind of understanding you'd need to add a custom
vehicle profile, debug why a route is slower than expected, plug in a GTFS feed, or read a merged PR and
actually know what changed.

---

## Who this is for

You can read Java and you've built things that move people around a map. You've heard "Dijkstra", "A*",
"Contraction Hierarchies", and "RAPTOR" and want to see what those words mean in code that ships. You may
have:

- built a **public-transit app** — stops, schedules, journey planning (this book bridges hard to that:
  GraphHopper's `reader-gtfs` is a real RAPTOR-style transit router you can read end to end), or
- built a **ride-hailing / navigation** feature — ETA, dispatch, matching a driver's GPS to the road
  network — which maps cleanly onto the shortest-path family and the map-matching chapter.

If neither fits, you'll still be fine; Chapter 0 refreshes the idioms and the build.

> 🔌 **The "Connect to your past" thread.** Each chapter ends with a sidebar tying the concept to the
> author's real work: **transit apps — BusMap and VinBus** (stops, GTFS, live ETA), the lead bridge for
> the transit chapter, and **ride-hailing routing** (Uber/Lyft-style dispatch, ETA and GPS map-matching),
> the bridge for the shortest-path and map-matching chapters. Read "publishes a `ResponsePath`" as "answers
> the route request your app just made."

---

## Pedagogy

Every chapter has the same shape, on purpose:

1. **Goal** — one blockquote, with the pinned ref, telling you what you'll be able to do after.
2. **Why it matters** — the problem this layer solves before any code.
3. **Mental model + ASCII diagram** — a picture to hold in your head.
4. **Guided source read** — exact `file:line` citations into the local clone. We read the real code.
5. **Lab** — concrete commands you run against your own local server, with an **expected** observation,
   recorded into `labs/`.
6. **Checkpoint** — 4–6 questions; if one is shaky, it tells you which section to re-read.
7. **🔌 Connect to your past** — bridge to your real work, then a bold **Next:** link.

We **verify every citation** by reading the line. Line numbers are pinned to `11.0`; if you re-pin
(Chapter 8 shows how), expect drift and re-verify.

---

## The 9-chapter arc

Depth is weighted toward **Chapter 3** — the shortest-path algorithm family — because that is where a
routing engine earns its name, and where the road-routing/ETA bridge is strongest.

| # | Chapter | What you get |
|---|---------|--------------|
| 00 | **Environment & Java Refresher** | A readable tree pinned to `11.0`; a Maven build; the server running on a city extract; the idioms GraphHopper leans on: the fluent `GraphHopper`/`GHRequest` API, encoded values, and `DataAccess` storage. |
| 01 | **Mental Model & the Repo Map** | The import → store → query → shape model; the module map; one full trace: `/route?point=A&point=B` from `RouteResource` to `ResponsePath`. |
| 02 | **The Graph — map → routable network** | How `OSMReader` turns an `.osm.pbf` into a `BaseGraph`; `EdgeIterator`/`EdgeExplorer`; `DataAccess` (RAM vs MMAP); geometry and turn restrictions. |
| 03 | ★ **The Shortest-Path Algorithm Family** | **Flagship.** Four case studies: `Dijkstra` + the pluggable `Weighting`; `A*`/bidirectional and the meeting condition; **Contraction Hierarchies** and why it's ~1000× faster; **Landmarks/ALT** for flexible weighting. |
| 04 | **Profiles, Weighting & Custom Models** | `Profile`, the `CustomModel` DSL and `CustomWeighting`, and the `EncodedValue`/`EncodingManager` system that packs per-edge attributes the weighting reads. |
| 05 | **Public Transit — GTFS & RAPTOR** | `GtfsReader` → the time-expanded `PtGraph`; `MultiCriteriaLabelSetting` (RAPTOR-style multi-criteria); GTFS-realtime. The BusMap/VinBus chapter. |
| 06 | **Map-Matching — snapping GPS to roads** | The Newson–Krumm Hidden Markov Model: candidate snaps (emission), routing between candidates (transition), and the Viterbi pass. The ride-hailing chapter. |
| 07 | **Navigation, Isochrones & the Web/Tiles Surface** | Edge sequence → turn-by-turn `Instruction`s; the `/route`, `/matrix`, `/isochrone`, `/nearest`, `/mvt` endpoints; the `ResponsePath` + `PathDetail` response model. |
| 08 | **Capstone & Staying Current** | Add a custom profile, build an isochrone, run a transit query on a real city, read a merged PR unaided, and re-sync this book to a newer tag. |

---

## How the repo is laid out

```text
graphhopper-book/
├── README.md                      # you are here
├── 00..08-*.md                    # the nine chapters
├── labs/                          # one note template per chapter lab + a runnable artifact
│   ├── lab00-build.md ... lab08-pr.md
│   └── query_route/               # a tiny standalone "call the routing API & print" client
├── reference/glossary.md          # term tables by area + a "Key files" source index
├── diagrams/                      # (placeholder)
├── site_src/build_site.py         # the static-site generator
└── site/                          # built HTML (index, 9 chapters, glossary, handbook.html) + assets
```

The upstream clone lives next to this book at `../graphhopper/` (pinned to `11.0`, SHA `69e50f6`). It is a
Maven multi-module project — the modules this book reads are `core` (the graph + algorithms), `reader-gtfs`
(transit), `map-matching`, `navigation`, `web-api` (the request/response value objects), `web-bundle`
(the HTTP resources), and `web` (the server). The clone is **read-only, for citations**; the labs are small
and run on your machine against a city-sized extract.

---

## Build the site

```bash
python3 site_src/build_site.py        # → 11 pages + handbook.html, into site/
```

Needs `markdown` + `pygments`. `site/assets/code.css` is generated; `styles.css` + `app.js` are the
hand-authored RumitX kit.

---

## Progress checklist

- [ ] **00** — Cloned & pinned, `mvn install` green, server answering `/route` on a city extract
- [ ] **01** — Can name every hop from `RouteResource` to `ResponsePath` and back
- [ ] **02** — Understand `OSMReader.addEdge`, `BaseGraph.edge`, `EdgeExplorer`, RAM vs MMAP `DataAccess`
- [ ] **03** — ★ Can explain Dijkstra → A* → CH → Landmarks and where `Weighting.calcEdgeWeight` is called
- [ ] **04** — Can write a `CustomModel` and name the `EncodedValue`s it reads
- [ ] **05** — Understand the time-expanded `PtGraph` and what a `Label` dominates on in `MultiCriteriaLabelSetting`
- [ ] **06** — Understand emission vs transition probability and the Viterbi pass in `MapMatching`
- [ ] **07** — Can read `InstructionsFromEdges` and hit `/route` `/isochrone` `/matrix` `/mvt`
- [ ] **08** — Re-pinned, re-verified citations, read one merged PR unaided

> 💡 **You never build the whole world.** Import a *city*-sized `.osm.pbf` (Geofabrik) or use the bundled
> `core/files/andorra.osm.pbf`. The import is the only heavy step; every query in the labs is instant.

*A RumitX publication · [rumitx.com](https://rumitx.com) · maps, routing & human-centric mobility.*
