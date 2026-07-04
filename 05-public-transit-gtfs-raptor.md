# Chapter 05 — Public Transit: GTFS & RAPTOR

> **Goal:** Understand how GraphHopper plans a bus/train journey. After this chapter you can explain how
> `GtfsReader` turns a GTFS feed into a **time-expanded** `PtGraph` (one node per stop-time, edges for
> boarding, riding, dwelling, transferring), how `MultiCriteriaLabelSetting` does a **RAPTOR-style**
> multi-criteria search over it (arrival time vs transfers vs walking), and how GTFS-realtime folds live
> delays back in. Pinned to **`11.0`** (`69e50f6`). This is the BusMap / VinBus chapter.

## 5.1 Why it matters

Road routing has one cost and no clock: an edge is always there and always the same length. Transit is the
opposite — you can only board a bus *when it departs*, a "faster" route with three transfers may be worse
than a slower direct one, and "shortest" is genuinely multi-dimensional. RAPTOR (Round-bAsed Public Transit
Optimized Router) and its label-setting cousins exist precisely because Dijkstra-over-distance can't express
"leave later, arrive earlier, but only if you don't mind two changes."

This is the chapter that maps straight onto your day job. BusMap's journey planner and VinBus's "when's the
next bus and when will I arrive" are exactly this computation. By the end you'll recognize your own product
in `MultiCriteriaLabelSetting`.

## 5.2 Mental model: fold time into the graph

```text
  GTFS feed (stops.txt, trips.txt, stop_times.txt, transfers.txt)
        │  GtfsReader.buildPtNetwork()
        ▼
   time-expanded PtGraph — one node per (stop, time) event, not per stop:

     stop A          stop B          stop C
   depart 09:00 ──HOP──▶ arrive 09:10 ──DWELL──▶ depart 09:12 ──HOP──▶ arrive 09:25
      ▲                     │                        ▲                     │
     BOARD                ALIGHT                    BOARD                 ALIGHT
      │                     ▼                        │                     ▼
   [ departure timeline at A ]   ──WAIT──▶ [ next departure ]   ...  street/walk edges
      ▲ ENTER_PT                                                        connect timelines
   street node (walk here from the road network — Chapters 2–3)
```

The trick is **time expansion**: instead of one node per stop, there's one node per *event* (this trip
departs A at 09:00; this trip arrives B at 09:10). Riding a vehicle is a `HOP` edge whose weight is the
scheduled minutes; boarding and alighting are `BOARD`/`ALIGHT` edges connecting a stop's departure timeline
to the trip; waiting at a stop is a `WAIT` edge along the timeline. Because arrival time is baked into the
node, a plain graph search over this structure respects the schedule automatically.

## 5.3 GTFS → `PtGraph`

The build is three steps:

```java
void buildPtNetwork() {
    createTrips();
    wireUpStops();
    insertGtfsTransfers();
}
```
📌 `reader-gtfs/src/main/java/com/graphhopper/gtfs/GtfsReader.java:118`–`:122`. `createTrips` walks each
trip's stop-times and lays down the per-trip edges — this is the literal construction of the diagram above:

```java
// riding between consecutive stops of a trip:
out.createEdge(departureNode, arrivalNode,
    new PtEdgeAttributes(GtfsStorage.EdgeType.HOP, stopTime.arrival_time - prev.departure_time, ...));  // :272
// connecting the trip to the stop's timeline:
out.createEdge(departureTimelineNode, departureNode,
    new PtEdgeAttributes(GtfsStorage.EdgeType.BOARD, 0, validOn, ...));                                  // :290
out.createEdge(arrivalNode, arrivalTimelineNode,
    new PtEdgeAttributes(GtfsStorage.EdgeType.ALIGHT, 0, validOn, ...));                                 // :291
out.createEdge(arrivalNode, departureNode,
    new PtEdgeAttributes(GtfsStorage.EdgeType.DWELL, stopTime.departure_time - stopTime.arrival_time,...)); // :292
```
📌 `GtfsReader.java:263`–`:292`. `wireUpStops` connects each stop to the street network with an `ENTER_PT`
edge and builds the waiting timeline (`:306`–`:311`), so a rider can *walk* to a stop (road graph, Chapters
2–3) and then *board* (transit graph). It all lands in the time-expanded store:

```java
public class PtGraph implements GtfsReader.PtGraphOut {
    public int addEdge(int nodeA, int nodeB, long attrPointer) {   // :120
```
📌 `reader-gtfs/src/main/java/com/graphhopper/gtfs/PtGraph.java:32`,`:120` — same flat-array,
`DataAccess`-backed philosophy as the road `BaseGraph` (§2.6), with a per-node edge linked list.

## 5.4 The edge vocabulary

Every transit movement is one of a small enum of edge types — worth reading once, because a journey is just
a path that alternates between them:

```java
public enum EdgeType {
    HIGHWAY, ENTER_TIME_EXPANDED_NETWORK, LEAVE_TIME_EXPANDED_NETWORK,
    ENTER_PT, EXIT_PT, HOP, DWELL, BOARD, ALIGHT, OVERNIGHT, TRANSFER, WAIT, WAIT_ARRIVAL
}
```
📌 `reader-gtfs/src/main/java/com/graphhopper/gtfs/GtfsStorage.java:173`–`:175`. A typical trip reads:
`ENTER_PT` (walk in) → `WAIT` (until your bus) → `BOARD` → `HOP…HOP` (ride, with `DWELL` at intermediate
stops) → `ALIGHT` → `TRANSFER` (to another line) → … → `EXIT_PT` (walk out). Counting the `BOARD`/`TRANSFER`
edges on a path *is* counting the transfers — which is one of the criteria the search minimizes.

## 5.5 RAPTOR-style multi-criteria search

Because "best" is multi-dimensional, GraphHopper doesn't keep *one* best label per node — it keeps a
**Pareto set** of non-dominated labels. A `Label` is the state: arrival time, transfer count, accumulated
walk time, and a back-pointer:

```java
public final long currentTime;      // :43  arrival-time criterion
public final int  nTransfers;       // :48  #transfers criterion
public final long streetTime;       // :51  walking-time criterion
public final Label parent;          // :58  path reconstruction
```
📌 `reader-gtfs/src/main/java/com/graphhopper/gtfs/Label.java:23`,`:43`–`:58`. The search is a
label-setting algorithm with a priority queue, one label popped at a time, its neighbours explored:

```java
public class MultiCriteriaLabelSetting {
    private final PriorityQueue<Label> fromHeap;   // :62
    // main loop:
    Label label = fromHeap.poll();                                        // :95 (after skipping deleted)
    action.accept(label);
    for (GraphExplorer.MultiModalEdge edge : explorer.exploreEdgesAround(label))  // :103
```
📌 `reader-gtfs/src/main/java/com/graphhopper/gtfs/MultiCriteriaLabelSetting.java:35`,`:66`–`:105`. The heart
is **domination** — a label is only kept if no existing label beats it on *every* criterion:

```java
private boolean dominates(Label me, Label they) {
    if (weight(me) > weight(they))                    return false;
    if (mindTransfers && me.nTransfers > they.nTransfers) return false;
    // ...
    if (weight(me) < weight(they))                    return true;
    if (mindTransfers && me.nTransfers < they.nTransfers) return true;
    return queueComparator.compare(me, they) <= 0;
}
```
📌 `MultiCriteriaLabelSetting.java:225`–`:240`. New labels are inserted only if not dominated, and they prune
any existing label they dominate (`insertIfNotDominated`/`removeDominated`, `:184`–`:223`). The scalar
`weight` folds the criteria with tunable betas — how many seconds a transfer or a minute of walking is
"worth":

```java
long weight(Label label) {
    return timeSinceStartTime(label)
         + (long)(label.nTransfers * betaTransfers)
         + (long)(label.streetTime * (betaStreetTime - 1.0)) + label.extraWeight;   // :243
}
```
📌 `MultiCriteriaLabelSetting.java:242`–`:244`.

> 🧠 **Mental model:** road Dijkstra keeps *one* best entry per node (§3.3); transit keeps a *set* of
> Pareto-optimal labels per node. "Arrive at 09:40 with 0 transfers" and "arrive at 09:32 with 2 transfers"
> can *both* be answers — neither dominates the other — so both survive, and the rider (or the UI) picks.

## 5.6 The router and realtime

`PtRouterImpl` wires the search to a request and drives the solution loop:

```java
public final class PtRouterImpl implements PtRouter {           // :50
    public GHResponse route(Request request) {                  // :78
        return new RequestHandler(request).route();
    // ...builds the label-setting search:
    router = new MultiCriteriaLabelSetting(graphExplorer, arriveBy, !ignoreTransfers, ...);  // :240
    for (Label label : router.calcLabels(startNode, initialTime)) { ... }                    // :259
```
📌 `reader-gtfs/src/main/java/com/graphhopper/gtfs/PtRouterImpl.java:50`,`:78`,`:240`,`:259` (path
reconstruction via `findPaths`, `:195`). Live delays arrive as **GTFS-realtime** protobuf and are folded in
without rebuilding the graph — a `RealtimeFeed` holds blocked edges and per-edge delay maps that the search
consults:

```java
public class RealtimeFeed {
    private final IntHashSet blockedEdges;                 // :50  cancelled trips/stops
    private final IntLongHashMap delaysForBoardEdges;      // :51
    private final IntLongHashMap delaysForAlightEdges;     // :52
    // ...
    public static RealtimeFeed fromProtobuf(GtfsStorage staticGtfs, ..., feedMessages) {   // :73
```
📌 `reader-gtfs/src/main/java/com/graphhopper/gtfs/RealtimeFeed.java:48`–`:73`. The static schedule graph
stays put; realtime is an *overlay* of delays and blocks the label search reads as it goes.

> 💡 GraphHopper 11 also ships a newer **trip-based** transit router (`PtRouterTripBasedImpl` +
> `TripBasedRouter`) alongside this schedule/label-setting one. The label-setting router read here is the
> most instructive — it makes the multi-criteria idea explicit — so it's the one this book teaches.

## 5.7 Lab 5 — plan a journey

> 🧪 **Lab 5.** Server lab (imports a GTFS feed). Goal: run a `pt` query and read its legs and transfers.
> Record in [`labs/lab05-transit.md`](labs/lab05-transit.md).

```bash
cd ~/Documents/learning/graphhopper
# confirm the edge vocabulary and the domination rule resolve:
sed -n '173,175p' reader-gtfs/src/main/java/com/graphhopper/gtfs/GtfsStorage.java
sed -n '225,244p' reader-gtfs/src/main/java/com/graphhopper/gtfs/MultiCriteriaLabelSetting.java

# start a server with a GTFS feed (add a `pt` profile + gtfs.file to your config), then:
curl -s "http://localhost:8989/route?point=STOP_A_LAT,STOP_A_LON&point=STOP_B_LAT,STOP_B_LON\
&profile=pt&pt.earliest_departure_time=2026-07-06T08:00:00Z" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);p=d['paths'][0];\
legs=p.get('legs',[]);print('min',round(p['time']/60000,1),'transfers',sum(1 for l in legs if l.get('type')=='pt')-1 if legs else '?','legs',len(legs))"
```

**Expected:** `GtfsStorage.java:174` lists `HOP, DWELL, BOARD, ALIGHT, … TRANSFER, WAIT`;
`MultiCriteriaLabelSetting.java:225` is `private boolean dominates(...)`; and the `pt` query returns a path
with `legs` alternating walk and `pt`, a travel time, and a transfer count RAPTOR minimized. (You supply a
small GTFS feed and enable a `pt` profile — the lab note lists the config keys.)

## 5.8 Checkpoint

1. Why is the transit graph "time-expanded"? What is a *node* here, versus a node in the road graph?
2. Name the edge types a single bus trip touches from walking in to walking out. Which one counts as a
   transfer?
3. Road Dijkstra keeps one best label per node; the transit search keeps a *set*. Why — and what does
   "dominates" mean?
4. Two answers survive: "09:40, 0 transfers" and "09:32, 2 transfers." Which is correct, and how does the
   engine decide what to return?
5. A bus is running 5 minutes late. How does that reach the search *without* rebuilding the graph?

> If #1 is shaky, re-read §5.2. If #3 is shaky, re-read §5.5.

## 🔌 Connect to your past (this is BusMap's engine)

You have built this product. BusMap's "from here to there by bus" is `PtRouterImpl.route`; the "2 changes,
7 min walk, arrive 08:41" your UI renders is a `Label`'s `nTransfers` / `streetTime` / `currentTime`; the
setting where a user says "fewer transfers, I don't mind walking" is `betaTransfers` vs `betaStreetTime` in
the `weight` function (§5.5). VinBus's live ETA — "your bus is 4 minutes late, you'll now arrive 08:45" — is
exactly the GTFS-realtime overlay in `RealtimeFeed`: the static schedule graph unchanged, a delay map on
top. Everything you may have hand-rolled for a transit app — the multi-criteria trade-off, the walk+ride
composition, the realtime patch — is here as one readable module. Read `MultiCriteriaLabelSetting` once and
you'll never look at your own journey planner the same way.

**Next:** road routing and transit both assume you *know* where you are on the map. But a moving vehicle
only has noisy GPS. Chapter 6 snaps it back onto the roads.
→ **[Chapter 06 — Map-Matching](06-map-matching.md)**
