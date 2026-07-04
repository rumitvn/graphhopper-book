# Chapter 02 — The Graph: turning a map into a routable network

> **Goal:** Understand the substrate every routing algorithm walks. After this chapter you can explain how
> `OSMReader` turns an `.osm.pbf` into a `BaseGraph` of integer-addressed nodes and edges, how an
> `EdgeExplorer` sweeps one node's neighbours, how the whole thing lives in flat `DataAccess` arrays (RAM
> or memory-mapped), where an edge's geometry is kept, and how turn restrictions attach to the graph.
> Pinned to **`11.0`** (`69e50f6`).

## 2.1 Why it matters

An algorithm is only as good as the graph it runs on. Chapter 3's Dijkstra and Contraction Hierarchies are
short and elegant precisely because the graph underneath them is *fast*: no object allocation per node, no
hash-map lookups per edge, just integer ids and byte offsets. To read the algorithms without confusion you
first have to stop picturing `class Node { List<Edge> edges; }` and start picturing **arrays**.

This is also the layer where the map itself lives. When BusMap places a stop or draws a road, that stop is
a **node** and that road is a sequence of **edges** in exactly this structure. Understanding it is
understanding what "the map" *is*, concretely, to a routing engine.

## 2.2 Mental model: nodes and edges as flat arrays

```text
  OSM ways ("Hauptstraße", a polyline of many points)
        │  OSMReader.addEdge()  — split at junctions, simplify geometry
        ▼
┌──────────────────────── BaseGraph ────────────────────────┐
│                                                            │
│  node store:   [ lat,lon | lat,lon | lat,lon | … ]  ← int node id indexes in
│                                                            │
│  edge store:   [ nodeA,nodeB, next_edge_A, next_edge_B,    │  ← int edge id indexes in
│                  flags(encoded values), dist, geo_ref | …] │
│                         │                                  │
│  geometry:     PointList per edge (the shape between A & B) │
│                                                            │
│  turn costs:   TurnCostStorage — (fromEdge, viaNode, toEdge) → cost/blocked
└────────────────────────────────────────────────────────────┘
        ▲                                   ▲
        │ EdgeExplorer.setBaseNode(n)       │ backed by DataAccess:
        │ → EdgeIterator.next()             │   RAMDataAccess (byte[][])  or
        │   walks A's edge linked-list      │   MMapDataAccess (mmap files)
```

The key idea: a node is an `int` that indexes into a node array; an edge is an `int` that indexes into an
edge array. Each edge record stores its two endpoints **and a pointer to the next edge of each endpoint** —
a linked list of edges per node, threaded through the same flat array. That's how you enumerate a node's
neighbours without any per-node `List`.

## 2.3 OSM → graph: `OSMReader`

Import is driven by `OSMReader`:

```java
public class OSMReader {
```
📌 `core/src/main/java/com/graphhopper/reader/osm/OSMReader.java:75`. The façade wires it up during import
(`GraphHopper.java:952`–`:961`, inside `importOSM()` at `:931`) and calls `readGraph()`, which runs a
two-pass parse over the PBF:

```java
public void readGraph() throws IOException {
    // ...
    WaySegmentParser waySegmentParser = new WaySegmentParser.Builder(baseGraph.getNodeAccess(), ...)
            .setWayFilter(this::acceptWay)
            // ...
            .setEdgeHandler(this::addEdge)     // ← the hinge
```
📌 `OSMReader.java:152`–`:172`. The first pass finds which OSM nodes are **junctions** (referenced by more
than one way); the second pass walks each accepted way and, at every junction, calls the edge handler. That
handler is where a stretch of road becomes a graph edge:

```java
protected void addEdge(int fromIndex, int toIndex, PointList pointList, ReaderWay way, ...) {
```
📌 `OSMReader.java:318` (geometry simplification and elevation happen at `:332`–`:347`). One OSM way like
"Hauptstraße" becomes *many* edges — one per junction-to-junction segment — each with the intermediate
points kept as geometry.

> 🧠 **Mental model:** a routing **edge** is not an OSM way. It is a way *segment between two junctions*.
> The bends in the road between those junctions are geometry (a `PointList`), not extra nodes. This keeps
> the graph small (few nodes) while preserving the shape for drawing and distance.

## 2.4 The `BaseGraph`: creating an edge

`BaseGraph` is the store:

```java
public class BaseGraph implements Graph, Closeable {
```
📌 `core/src/main/java/com/graphhopper/storage/BaseGraph.java:49`. `addEdge` ultimately calls:

```java
public EdgeIteratorState edge(int nodeA, int nodeB) {
    if (isFrozen())
        throw new IllegalStateException("Cannot create edge if graph is already frozen");
    // ...
    int edgeId = store.edge(nodeA, nodeB);
    EdgeIteratorStateImpl edge = new EdgeIteratorStateImpl(this);
    boolean valid = edge.init(edgeId, nodeB);
```
📌 `BaseGraph.java:291`–`:307`. Note `isFrozen()`: once import finishes and CH/LM preparation begins, the
graph is **frozen** — no new base edges, only shortcuts (Chapter 3). Node coordinates go through
`getNodeAccess()` (`:156`); edge iteration through `createEdgeExplorer(...)` (`:410`–`:412`); turn costs
through `getTurnCostStorage()` (`:425`–`:427`).

The coordinates themselves live in `NodeAccess` (a `PointAccess`):

```java
public interface NodeAccess extends PointAccess
```
📌 `core/src/main/java/com/graphhopper/storage/NodeAccess.java:30`; coordinates via
`PointAccess.setNode(...)` (`:50`), `getLat(int)` (`:55`), `getLon(int)` (`:60`). An edge's *shape* between
its endpoints is a `PointList`:

```java
public class PointList implements Iterable<GHPoint3D>, PointAccess {
```
📌 `web-api/src/main/java/com/graphhopper/util/PointList.java:40` (`add(lat, lon)` at `:199`).

## 2.5 Sweeping a node's edges: the cursor idiom

You never get a `List<Edge>`. You get a **cursor** that advances over the edge linked-list:

```java
public interface EdgeExplorer {
    EdgeIterator setBaseNode(int baseNode);
```
📌 `core/src/main/java/com/graphhopper/util/EdgeExplorer.java:29`,`:37`. The returned iterator is *itself*
an edge view, mutated in place as you advance:

```java
public interface EdgeIterator extends EdgeIteratorState {
    boolean next();
```
📌 `core/src/main/java/com/graphhopper/util/EdgeIterator.java:41`,`:60`. So the loop reads:

```java
EdgeExplorer explorer = graph.createEdgeExplorer();
EdgeIterator iter = explorer.setBaseNode(node);
while (iter.next()) {
    int adj  = iter.getAdjNode();     // the neighbour
    double d = iter.getDistance();    // edge length in metres
    int edge = iter.getEdge();        // the edge id
}
```
Those accessors are `EdgeIteratorState` — the read interface for one edge: `getEdge()` (`:104`),
`getBaseNode()` (`:127`), `getAdjNode()` (`:133`), `fetchWayGeometry(FetchMode)` (`:145`), `getDistance()`
(`:158`). 📌 `core/src/main/java/com/graphhopper/util/EdgeIteratorState.java:42`.

> ⚠️ The iterator is a **flyweight**: `iter` doesn't hold one edge, it *is* a moving window. Don't stash a
> reference to it expecting it to stay put — read the fields you need each iteration. This is the classic
> footgun when you first write graph-walking code against GraphHopper.

## 2.6 Storage: RAM vs memory-mapped

All of the above — node array, edge array, geometry — is bytes behind a `DataAccess` (§0.6). Two backings:

```java
public class RAMDataAccess extends AbstractDataAccess {
    private byte[][] segments = new byte[0][];     // on-heap
```
📌 `core/src/main/java/com/graphhopper/storage/RAMDataAccess.java:35`–`:36` (the default). Or memory-mapped,
so a country-sized graph never fully enters the JVM heap:

```java
buf = raFile.getChannel().map(
        allowWrites ? FileChannel.MapMode.READ_WRITE : FileChannel.MapMode.READ_ONLY, offset, byteCount);
```
📌 `core/src/main/java/com/graphhopper/storage/MMapDataAccess.java:163`–`:164` (class at `:49`). This is the
knob that lets the same code serve Andorra on a laptop and a continent on a server.

## 2.7 Turn restrictions live on the graph

"No left turn here" isn't a property of a road — it's a property of a *(fromEdge, viaNode, toEdge)* triple.
GraphHopper stores exactly that:

```java
public class TurnCostStorage {
    // set(BooleanEncodedValue bev, int fromEdge, int viaNode, int toEdge, boolean value)   :90
    // set(DecimalEncodedValue turnCostEnc, int fromEdge, int viaNode, int toEdge, double)   :100
```
📌 `core/src/main/java/com/graphhopper/storage/TurnCostStorage.java:39`. A restriction is a turn cost of
infinity; a cost is a finite penalty (seconds). The via-node links back through
`getNodeAccess().setTurnCostIndex(viaNode, index)` (`:114`). Chapter 3 shows where the algorithms add this
turn weight (spoiler: through one shared `GHUtility` call).

## 2.8 Lab 2 — read the graph

> 🧪 **Lab 2.** Read-only. Goal: size the graph you imported and sweep one node's edges. Record in
> [`labs/lab02-graph.md`](labs/lab02-graph.md).

```bash
cd ~/Documents/learning/graphhopper
# confirm the storage & cursor symbols resolve:
sed -n '291,307p' core/src/main/java/com/graphhopper/storage/BaseGraph.java
sed -n '37p'      core/src/main/java/com/graphhopper/util/EdgeExplorer.java
sed -n '163,164p' core/src/main/java/com/graphhopper/storage/MMapDataAccess.java

# after the Chapter 0 import, the graph's size is logged; find it:
grep -R "nodes:" graph-cache/ 2>/dev/null || echo "check the server import log for 'nodes:...edges:...'"
```

Then reason about the numbers: for a road network, edges ≈ 1.1–1.3 × nodes, so average degree (edges·2 /
nodes) is small — **~2–3**. That low degree is *why* graph search is fast: each settled node only relaxes a
handful of neighbours.

**Expected:** `BaseGraph.java:291` reads `public EdgeIteratorState edge(int nodeA, int nodeB)`;
`EdgeExplorer.java:37` reads `EdgeIterator setBaseNode(int baseNode);`; and the import log reports node/edge
counts whose ratio is close to 1. Record the counts and the average degree.

## 2.9 Checkpoint

1. A node and an edge are each an `int`. How does the graph enumerate a node's neighbours *without* a
   per-node `List`?
2. One OSM way "Hauptstraße" becomes several routing edges. What splits it, and where do the road's bends
   go if not into nodes?
3. What does `isFrozen()` protect against, and which later phase needs the graph frozen?
4. When would you choose `MMapDataAccess` over `RAMDataAccess`, and what line actually does the mapping?
5. A "no left turn" rule is stored against what triple, in which class?

> If #1 is shaky, re-read §2.2 and §2.5. If #3 is shaky, hold it — Chapter 3 §3.4 pays it off.

## 🔌 Connect to your past (a transit map *is* a graph)

BusMap's world maps directly onto this structure. A **stop** is a node; a **route segment** between two
stops is an edge; the shape of the road the bus follows between them is the edge's `PointList` geometry;
"buses can't turn here" is a `TurnCostStorage` entry. When Chapter 5 builds a *transit* graph from GTFS,
it reuses this exact machinery — stops and platforms become nodes, boarding/riding/alighting become edges —
just with time folded in. And for ride-hailing, this is the network a driver's GPS trace gets matched onto
in Chapter 6: map-matching is "which sequence of *these edges* did the driver actually travel?" Every later
chapter is an algorithm walking the arrays you just met.

**Next:** the graph is built and frozen. Now the main event — the algorithms that find the shortest path
across it. → **[Chapter 03 — The Shortest-Path Algorithm Family](03-shortest-path-algorithms.md)**
