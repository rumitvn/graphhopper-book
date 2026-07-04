# Chapter 07 — Navigation, Isochrones & the Web/Tiles Surface

> **Goal:** See how the engine reaches the app. After this chapter you can explain how
> `InstructionsFromEdges` turns a raw edge sequence into turn-by-turn `Instruction`s (with sign codes), how
> the `ResponsePath` + `PathDetail` value objects carry a route to a client, and what the family of HTTP
> endpoints — `/route`, `/isochrone`, `/nearest`, `/mvt` — each does. Pinned to **`11.0`** (`69e50f6`).

## 7.1 Why it matters

Chapters 3–6 produced *paths* — sequences of edges with a total distance and time. But a driver doesn't
want an edge list; they want "In 200 m, turn left onto Hauptstraße." A dispatch system doesn't want a
polyline; it wants a JSON envelope with a distance, a duration, and maybe the road classes along the way. A
map UI wants vector tiles it can render. This chapter is the **shape** layer from Chapter 1 — the last
transformation from "the algorithm's answer" to "what the product consumes."

For you this is the surface your apps already talk to. Everything here is the other side of the HTTP calls
BusMap, VinBus, and a ride-hailing backend make every day.

## 7.2 Mental model: from edges to a rendered answer

```text
   Path (edge ids + geometry)                    HTTP endpoints (web-bundle)
        │                                         ┌──────────────────────────────┐
        ▼  InstructionsFromEdges (core)           │ /route      → ResponsePath    │
   InstructionList: [ "Continue on X" (sign 0),   │ /isochrone  → reachable polygon│
                      "Turn left"     (sign -2),  │ /nearest    → snapped point    │
                      "Finish"        (sign 4) ]  │ /mvt/z/x/y  → vector tile      │
        │                                         │ /spt        → shortest-path tree│
        ▼  packed into                            └──────────────────────────────┘
   ResponsePath { distance, time, points,                       │ JSON / protobuf
                  instructions, pathDetails } ──────────────────┘
        │
        ▼  GHResponse.getBest() → serialized to JSON → your app
```

Two objects do most of the work: `InstructionList` (the turn-by-turn steps) and `ResponsePath` (the whole
answer). The endpoints are thin wrappers that call the engine and serialize one of these.

## 7.3 Turn instructions from edges

Turning a path into instructions means walking its edges and, at each junction, deciding "did the road bend
enough, or the name change, to warrant telling the driver something?" That's `InstructionsFromEdges`, an
edge visitor:

```java
public class InstructionsFromEdges implements Path.EdgeVisitor {              // :36
    public static InstructionList calcInstructions(Path path, Graph graph, Weighting weighting,
                                                   EncodedValueLookup evLookup, Translation tr) {  // :111
        final InstructionList ways = new InstructionList(tr);
        // ...
        ways.add(new FinishInstruction(graph.getNodeAccess(), path.getEndNode()));   // :115
```
📌 `core/src/main/java/com/graphhopper/routing/InstructionsFromEdges.java:36`,`:111`–`:118`. The first step
is always a `CONTINUE_ON_STREET`; each subsequent junction gets a **sign** computed from the geometry:

```java
int sign = Instruction.CONTINUE_ON_STREET;                                    // :160  (first instruction)
// ...at each junction:
int sign = getTurn(edge, baseNode, prevNode, adjNode, name, ...);             // :257
// getTurn → InstructionsHelper.calculateSign(prevLat, prevLon, lat, lon, prevOrientation)  // :362
```
📌 `InstructionsFromEdges.java:158`–`:161`,`:256`–`:257`,`:355`–`:362`. The sign is an integer code the
client renders as an arrow:

```java
public static final int TURN_LEFT        = -2;   // :32
public static final int CONTINUE_ON_STREET = 0;  // :34
public static final int TURN_RIGHT       = 2;    // :36
public static final int FINISH           = 4;    // :38
public static final int USE_ROUNDABOUT   = 6;    // :40
public static final int PT_START_TRIP    = 101;  // :47  (transit instructions, Chapter 5)
```
📌 `web-api/src/main/java/com/graphhopper/util/Instruction.java:28`–`:47`. Sharper angles get bigger
magnitudes (`SHARP_LEFT`/`SHARP_RIGHT`), and the sign's *sign* is its handedness — negative left, positive
right. Note the `PT_*` codes: transit journeys (Chapter 5) reuse this same instruction machinery.

## 7.4 The response model

A route leaves the engine as a `ResponsePath`:

```java
public class ResponsePath {                                   // :34
    private InstructionList instructions;                     // :43
    private Map<String, List<PathDetail>> pathDetails;        // :50
    public PointList getPoints() { ... }                      // :99   geometry
    public double getDistance() { ... }                       // :148  metres
    public long getTime() { ... }                             // :197  milliseconds
    public InstructionList getInstructions() { ... }          // :246
```
📌 `web-api/src/main/java/com/graphhopper/ResponsePath.java:34`–`:246`. Beyond distance/time/geometry/turns
it carries **path details** — interval-tagged values along the route ("edges 0–5 are `road_class=primary`,
6–9 are `residential`"):

```java
public class PathDetail {                 // :25
    private final Object value;           // :26   e.g. "primary", or a speed
    // first / last point index the value spans
    public Object getValue() { ... }      // :37
```
📌 `web-api/src/main/java/com/graphhopper/util/details/PathDetail.java:25`–`:37`. The whole thing is wrapped
in a `GHResponse` (best path + alternatives + errors), whose `getBest()` (`GHResponse.java:48`, seen back in
§1.4) the resource serializes.

## 7.5 The endpoint family

Each capability is a JAX-RS resource in `web-bundle`. `/route` you already traced (§1.4):

```java
@Path("route")   public class RouteResource { ... GHResponse ghResponse = graphHopper.route(request); // :154 }
```

**`/isochrone`** — "everywhere reachable within N seconds/metres" — grows a shortest-path *tree* (not a
single path) and contours it into a polygon:

```java
@Path("isochrone")
// ...
ShortestPathTree shortestPathTree = new ShortestPathTree(queryGraph, ..., reverseFlow, traversalMode);  // :105
// ...bucket the reachable area by time/distance, then triangulate + contour:
Triangulator.Result result = triangulator.triangulate(snap, queryGraph, shortestPathTree, fz, ...);     // :127
```
📌 `web-bundle/src/main/java/com/graphhopper/resources/IsochroneResource.java:46`–`:128` (the
weight/distance/time limit dispatch is at `:109`–`:122`).

**`/nearest`** — snap a coordinate to the graph — is a single location-index lookup:

```java
@Path("nearest")
Snap snap = index.findClosest(point.lat, point.lon, EdgeFilter.ALL_EDGES);   // :70
```
📌 `NearestResource.java:42`–`:70`. **`/mvt/{z}/{x}/{y}.mvt`** serves Mapbox **vector tiles** so a client can
draw the routable network:

```java
@Path("mvt")
@GET @Path("{z}/{x}/{y}.mvt")
public Response doGetXyz(@PathParam("z") int zInfo, @PathParam("x") int xInfo, @PathParam("y") int yInfo, ...)
// ...uses a VectorTileEncoder                                                // :93
```
📌 `MVTResource.java:34`–`:93`. (There's also an `/spt` shortest-path-tree endpoint and PT-specific
resources for transit isochrones and tiles.)

> 🧠 **Mental model:** the endpoints are all the *same* engine viewed through different lenses. `/route` is
> one path; `/isochrone` is the whole reachable set (a tree, not a path); `/nearest` is just the snap step;
> `/mvt` is the graph itself, drawn. Once you see them as projections of the graph + the shortest-path
> machinery, there are no new concepts here — only new outputs.

## 7.6 Lab 7 — hit the surface

> 🧪 **Lab 7.** Server lab. Goal: exercise the endpoint family and read the response model. Record in
> [`labs/lab07-web.md`](labs/lab07-web.md).

```bash
cd ~/Documents/learning/graphhopper
# confirm the sign codes and the isochrone tree resolve:
sed -n '28,47p' web-api/src/main/java/com/graphhopper/util/Instruction.java
sed -n '105p;127p' web-bundle/src/main/java/com/graphhopper/resources/IsochroneResource.java

# with the Chapter 0 server running:
python3 ~/Documents/learning/graphhopper-book/labs/query_route/query.py 52.517,13.389 52.508,13.421
python3 ~/Documents/learning/graphhopper-book/labs/query_route/query.py 52.517,13.389 --isochrone 600
curl -s "http://localhost:8989/nearest?point=52.517,13.389" | head -c 200
```

**Expected:** `Instruction.java:34` is `CONTINUE_ON_STREET = 0`, `:32` is `TURN_LEFT = -2`;
`IsochroneResource.java:105` builds a `ShortestPathTree`; `query.py` prints the route with a handful of
instruction lines and their sign codes, then an isochrone polygon vertex count; `/nearest` returns a snapped
coordinate and its distance. Record which sign codes appeared on your route.

## 7.7 Checkpoint

1. A path is an edge list; a driver needs instructions. What decides that a junction deserves an
   instruction, and what integer encodes "turn left" vs "turn right"?
2. What does `ResponsePath` carry beyond distance and time, and what is a `PathDetail`?
3. `/isochrone` and `/route` use the same engine but return different shapes. What's the structural
   difference (path vs …)?
4. Transit journeys (Chapter 5) reuse the instruction system. What in `Instruction` proves it?
5. Trace one sentence: from `GHResponse.getBest()` to the JSON your app parses — who does the serializing?

> If #1 is shaky, re-read §7.3. If #3 is shaky, re-read §7.5.

## 🔌 Connect to your past (the on-screen map and the ETA)

This chapter is everything your UI touches. The turn arrows and "300 m, then left" banner in a navigation
screen are `InstructionList` + sign codes rendered. The ETA VinBus shows is `ResponsePath.getTime()`. The
"which roads am I on" a trip-detail screen colors is `PathDetail`. The reachable-area overlay a
service-coverage or "cars near you" feature draws is `/isochrone`. The base map itself can come from `/mvt`.
Everything the algorithms computed in Chapters 3–6 only becomes a *product* here — and now you can read the
exact object your app deserializes and the exact endpoint it called to get it.

**Next:** you've read the whole engine. The last chapter makes you self-sufficient — a capstone, reading a
real PR unaided, and re-syncing this book when you re-pin.
→ **[Chapter 08 — Capstone & Staying Current](08-capstone-and-staying-current.md)**
