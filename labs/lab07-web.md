# Lab 7 — The web surface

Fill in during Chapter 7 §7.6.

## Hit every endpoint

| Endpoint | Query | Key field in the response |
|----------|-------|---------------------------|
| `/route` | A→B | `paths[0].instructions` count = |
| `/isochrone` | 600s from A | polygon vertices = |
| `/spt` or `/matrix` (if enabled) | A→[B,C] | times = |
| `/nearest` | one point | snapped `distance` = |
| `/mvt/{z}/{x}/{y}.mvt` | a tile over A | HTTP status = |

## The response model

| Field on `ResponsePath` | Present? |
|-------------------------|----------|
| `distance` / `time` | |
| `instructions` (turn-by-turn) | |
| `points` (geometry) | |
| a `PathDetail` (e.g. `road_class`) | |

## Notes
_Which instruction `sign` codes did you see, and what do they mean? How would VinBus turn this into an on-screen ETA?_
