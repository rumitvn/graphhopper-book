# Chapter 01 — Mental Model & the Repo Map

> **Goal:** Hold the whole engine in your head at once. After this chapter you can name GraphHopper's four
> layers — **import → store → query → shape** — point at the module each lives in, and trace a single
> `/route?point=A&point=B` request hop by hop from the HTTP resource to the `ResponsePath` it returns and
> back out as JSON. Pinned to **`11.0`** (`69e50f6`).

## 1.1 Why it matters

A routing engine sounds like one thing — "find the shortest path" — but it is really **four** things, and
they run at different times. If you don't separate them, the code looks like a maze; once you do, every
file has an obvious home:

1. **Import** — turn a map file (`.osm.pbf`) into an internal graph. Runs once.
2. **Store** — keep that graph in compact, memory-mappable form on disk (`graph-cache/`). Persists.
3. **Query** — given two points, run an algorithm over the stored graph. Runs per request, in ~1 ms.
4. **Shape** — turn the raw edge sequence into what a client wants: turn instructions, geometry, an ETA.

The whole rest of this book is a tour of those four layers. This chapter draws the map so the later
chapters are "go deeper on a box you've already placed," not "where does this even live?"

## 1.2 Mental model: import → store → query → shape

```text
   OSM .pbf                                          graph-cache/ (on disk)
      │                                                    ▲   │
      ▼                                                    │   ▼
┌───────────┐   BaseGraph    ┌──────────────┐  CH/LM prep  │  ┌──────────────────────────────┐
│  IMPORT   │ ─────────────▶ │    STORE     │ ────────────▶│  │           QUERY              │
│ OSMReader │  nodes+edges   │ DataAccess   │  shortcuts   │  │ Router → RoutingAlgorithm    │
│  (core)   │                │ (flat arrays)│  landmarks   │  │  Dijkstra / A* / CH / LM     │
└───────────┘                └──────────────┘              │  └──────────────┬───────────────┘
   Chapter 2                     Chapter 2                     Chapter 3      │ ResponsePath
                                                                             ▼
   ┌─────────────────────────────────────────────────────────────┐  ┌───────────────┐
   │  SHAPE: InstructionsFromEdges → InstructionList, PathDetail   │  │  web layer     │
   │         (Chapter 7)                                           │◀─│ RouteResource  │──▶ JSON
   └─────────────────────────────────────────────────────────────┘  └───────────────┘
                                                                        Chapter 1 (this trace)
```

Two things to hold. First, **import + store happen before any request** — that's the `importOrLoad()`
phase from §0.5. By the time a `/route` arrives, the graph, the Contraction-Hierarchies shortcuts, and the
landmarks are already built and memory-mapped; a query only *reads*. Second, the **web layer is thin** —
it parses a request, calls one method, and serializes the answer. Everything interesting is below it.

## 1.3 The module map

Map the four layers onto the Maven modules from §0.3:

| Layer | Lives in | Star symbols |
|-------|----------|--------------|
| Import | `core` | `OSMReader`, `WaySegmentParser` |
| Store | `core` | `BaseGraph`, `DataAccess`, `EdgeIterator`, `TurnCostStorage` |
| Query | `core` | `Router`, `RoutingAlgorithm`, `Dijkstra`, `AStar`, CH (`ch/`), Landmarks (`lm/`) |
| Shape | `core` + `web-api` | `InstructionsFromEdges` (core), `Instruction`/`ResponsePath` (web-api) |
| Transit | `reader-gtfs` | `GtfsReader`, `PtGraph`, `MultiCriteriaLabelSetting` |
| Map-matching | `map-matching` | `MapMatching`, `HmmProbabilities` |
| HTTP surface | `web-bundle` + `web` | `RouteResource`, `IsochroneResource`, `GraphHopperApplication` |
| Request/response objects | `web-api` | `GHRequest`, `GHResponse`, `ResponsePath` |

> 🧠 **Mental model:** `core` is the engine; `web-api` is the *vocabulary* the engine and the outside world
> share (`GHRequest`/`GHResponse`); `web-bundle` + `web` are the HTTP skin. The transit and map-matching
> modules are peers of `core` that reuse its graph and algorithms.

## 1.4 One request, end to end

Let's follow `GET /route?point=52.52,13.39&point=52.50,13.42&profile=car` through every hop. Open each
file as we go.

**Hop 1 — the HTTP resource.** The endpoint is a JAX-RS resource:

```java
@Path("route")
public class RouteResource {
```
📌 `web-bundle/src/main/java/com/graphhopper/resources/RouteResource.java:57`–`:58`. The `GET` handler
(`:82`–`:108`) declares the query parameters, including the repeated `point` and the `profile`:

```java
@QueryParam("point") @NotNull List<GHPointParam> pointParams,   // :89
@QueryParam("profile") String profileName,                      // :96
```

**Hop 2 — params become a `GHRequest`.** The resource assembles the same domain object you built by hand
in §0.4:

```java
GHRequest request = new GHRequest();                 // :116
// ...
request.setPoints(points).setProfile(profileName)
       .setAlgorithm(algoStr).setLocale(localeStr);  // :122–:133
```
📌 `RouteResource.java:116`–`:133`. A little profile resolution runs first (`:145`–`:152`), then the one
line that crosses from the web layer into the engine:

```java
GHResponse ghResponse = graphHopper.route(request);
```
📌 `RouteResource.java:154`. Everything above this line is HTTP; everything below is the engine. If the
response has errors, the resource maps them to HTTP 400 (`:159`–`:165`).

**Hop 3 — the façade builds a fresh `Router`.** `GraphHopper.route` is tiny — and revealing:

```java
public GHResponse route(GHRequest request) {
    return createRouter().route(request);
}
```
📌 `core/src/main/java/com/graphhopper/GraphHopper.java:1333`–`:1335`. `createRouter()` (`:1337`–`:1347`)
checks the engine is fully loaded, then `doCreateRouter()` (`:1349`–`:1355`) constructs `new Router(...)`,
handing it the `baseGraph`, the `encodingManager`, the `locationIndex`, the profiles, and — crucially —
the prepared **CH graphs** and **landmarks**.

> 🧠 **Mental model:** a `Router` is created **per request**, but it's cheap — it just wires references to
> the already-built, shared, read-only structures. The heavy stuff (the graph, the shortcuts) was built at
> import time and is never rebuilt. This is the import/query split made concrete.

**Hop 4 — the `Router` validates and dispatches.** The class is `Router.java:58`; its `route` method is
the real orchestration:

```java
public GHResponse route(GHRequest request) {
    try {
        checkNoLegacyParameters(request);
        checkAtLeastOnePoint(request);
        checkIfPointsAreInBoundsAndNotNull(request.getPoints());
        // ...
        Solver solver = createSolver(request);
        solver.checkRequest();
        solver.init();
        // ...
        return routeVia(request, solver);
```
📌 `Router.java:97`–`:120`. The one decision that determines everything about *how fast* the query runs is
which solver it creates:

```java
if (chEnabled && !disableCH)      // Contraction Hierarchies — fastest, fixed weighting
    return createCHSolver(...);
else if (lmEnabled && !disableLM) // Landmarks/ALT — fast, flexible weighting
    return createLMSolver(...);
else                              // plain bidirectional Dijkstra/A* — slowest, fully flexible
    return createFlexSolver(...);
```
📌 `Router.java:190`–`:198` (`chEnabled`/`lmEnabled` were set at `:88`–`:89` from whether CH graphs /
landmarks exist). That three-way choice **is** Chapter 3.

**Hop 5 — the answer comes back.** The solver runs an algorithm (Chapter 3), builds a `ResponsePath` with
geometry, distance, time and instructions (Chapter 7), and the resource pulls the best one:

```java
public ResponsePath getBest() { return responsePaths.get(0); }
```
📌 `web-api/src/main/java/com/graphhopper/GHResponse.java:48`. `RouteResource` serializes it to JSON and
writes HTTP 200. Request complete.

## 1.5 The one insight to keep

Every `/route` call funnels through **one method** (`GraphHopper.route`, `:1333`) into **one dispatcher**
(`Router.route`, `:97`) that makes **one choice** (CH vs LM vs flexible, `:190`). If you remember only
that spine, you can find your way into any routing behaviour in the codebase from the outside in.

## 1.6 Lab 1 — trace the request yourself

> 🧪 **Lab 1.** No build needed beyond Chapter 0's server. Goal: confirm the trace by reading the six hops
> and by watching the request from the outside. Record in [`labs/lab01-trace.md`](labs/lab01-trace.md).

```bash
cd ~/Documents/learning/graphhopper
# read each hop and confirm the line resolves to the symbol:
sed -n '57,58p;89p;96p;154p' web-bundle/src/main/java/com/graphhopper/resources/RouteResource.java
sed -n '1333,1335p' core/src/main/java/com/graphhopper/GraphHopper.java
sed -n '58p;97,120p;190,198p' core/src/main/java/com/graphhopper/routing/Router.java

# now the outside view — with the Chapter 0 server running:
python3 ~/Documents/learning/graphhopper-book/labs/query_route/query.py 52.517,13.389 52.508,13.421
curl -s "http://localhost:8989/route?point=52.517,13.389&point=52.508,13.421&profile=car" | head -c 400
```

**Expected:** `RouteResource.java:154` reads `GHResponse ghResponse = graphHopper.route(request);`;
`GraphHopper.java:1333` reads `public GHResponse route(GHRequest request)`; `Router.java:190`–`:198` shows
the CH/LM/flex branch. `query.py` prints a distance/time line; the `curl` shows a JSON body with a
`paths` array and an `info.took` in milliseconds. Note that `took` — that's the whole query, and it's tiny.

## 1.7 Checkpoint

1. Name GraphHopper's four layers and say which run *before* a request arrives vs *per* request.
2. A `/route` request enters the engine at exactly one line. Which file:line, and what is above vs below it?
3. Why does `GraphHopper.route` build a **new `Router` every request**, and why is that not expensive?
4. `Router.route` makes one three-way decision that sets the query's speed. What are the three options and
   what does each trade off?
5. Which module holds `GHRequest`/`GHResponse`, and why does it sit *between* `core` and the web layer?

> If #2 is shaky, re-read §1.4 Hop 2–3. If #4 is shaky, re-read §1.4 Hop 4 and hold it for Chapter 3.

## 🔌 Connect to your past (your app already calls this boundary)

Whatever routing your app does today, it crosses exactly the boundary you just traced — usually as an HTTP
call to a routing service. BusMap asking "how do I get from stop A to stop B", a ride-hailing backend
asking "what's the ETA from the driver to the rider" — both send the equivalent of a `GHRequest` and read
back the equivalent of a `ResponsePath`. What this chapter gives you is the *other side* of that call: the
`RouteResource` → `GraphHopper.route` → `Router` → `ResponsePath` spine your requests have been hitting all
along. From here on, when your app makes a routing call, you'll know what the server does with it in the
millisecond before it answers.

**Next:** the query layer needs something to walk. Let's build it — how an OSM file becomes the
`BaseGraph` every algorithm sweeps. → **[Chapter 02 — The Graph](02-the-graph-map-to-network.md)**
