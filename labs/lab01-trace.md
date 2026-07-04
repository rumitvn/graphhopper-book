# Lab 1 — Trace one request end-to-end

Fill in during Chapter 1 §1.6.

## The hops of a `/route` request

Fill each hop with the `file:line` you land on (verify against the clone).

| # | Hop | Symbol | file:line |
|---|-----|--------|-----------|
| 1 | HTTP endpoint receives the query | `RouteResource.doGet` | |
| 2 | builds the request object | `GHRequest` | |
| 3 | engine entry point | `GraphHopper.route(GHRequest)` | |
| 4 | picks the algorithm (CH / LM / flexible) | `Router` | |
| 5 | runs the search | `RoutingAlgorithm.calcPath` | |
| 6 | wraps the answer | `ResponsePath` / `GHResponse` | |

## Confirm from the outside

| Field (from `query_route/query.py A B`) | Value |
|-----------------------------------------|-------|
| HTTP status | _expected 200_ |
| `paths[0].distance` present? | |
| `info.took` (ms) | |

## Notes
_In one sentence each: import vs store vs query vs shape. Which hop is the "algorithm"?_
