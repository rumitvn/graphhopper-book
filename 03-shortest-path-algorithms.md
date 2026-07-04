# Chapter 03 — The Shortest-Path Algorithm Family ★

> **Goal:** Understand how GraphHopper finds the fastest route across a continent in about a millisecond.
> We'll do it in **four case studies**: (A) plain **Dijkstra** and the pluggable `Weighting`; (B) **A\***
> and the **bidirectional** meeting condition; (C) **Contraction Hierarchies** and *why* it's ~1000×
> faster; and (D) **Landmarks / ALT** for when you can't precompute. By the end you can explain what each
> trades away and point at where every one of them calls `Weighting.calcEdgeWeight`. Pinned to **`11.0`**
> (`69e50f6`).

This is the flagship chapter, and the longest, because this is where a routing engine earns its name.
Everything before it *builds* the graph; everything after it *shapes* or *specializes* the search you're
about to read.

## 3.1 Why it matters

Dijkstra's algorithm is 65 years old and fits on a napkin. So why is there a whole family here? Because a
napkin Dijkstra over a graph of tens of millions of nodes takes *seconds*, and a routing API has a
*millisecond* budget. The entire family is a sequence of answers to one question — "how do we get the same
optimal path, but visit far less of the graph?" — and each answer trades away something (memory,
preprocessing time, or the freedom to change the cost function) to buy speed.

For you, this is also the ETA chapter. Every "how long from here to there" a ride-hailing or navigation
app shows is a shortest-path query underneath. Knowing which algorithm answers it — and what each one
assumes — is the difference between "the ETA is slow and I don't know why" and "we're on the flexible
path because our weighting changes per request; here's the fix."

## 3.2 Mental model: shrink the search frontier

```text
  Dijkstra (uninformed)        A* (goal-directed)           CH (hierarchical)
  ┌───────────────────┐        ┌───────────────────┐        ┌───────────────────┐
  │        ....        │        │        ..          │        │   S ─▶▲            │
  │      ..S....       │        │      ..S▶.         │        │       ▲  (only     │
  │    ....(o)....  T  │        │     ...▶▶▶.  T      │        │        ▲  climb to │
  │      ......        │        │        .▶.         │        │         ▲ higher-  │
  │        ....        │        │                    │        │          ▲ level   │
  └───────────────────┘        └───────────────────┘        │   T ─▶▶▶▶▶ shortcuts│
   settles a growing disc        heuristic pulls toward T     └───────────────────┘
   around S until it hits T      → fewer settled nodes         meet in the middle,
                                                               skipping via shortcuts
```

Three moves. **A\*** adds a *heuristic* — an optimistic guess of the remaining distance — so the frontier
stretches toward the target instead of ballooning in all directions. **Bidirectional** search runs two
frontiers, one from each end, and stops when they meet — each explores half the radius. **Contraction
Hierarchies** goes further: it *preprocesses* the graph into levels and adds "shortcut" edges, so a query
only ever climbs to more-important roads and meets in the middle, skipping thousands of local nodes.
**Landmarks/ALT** is A* with a *much* better heuristic derived from precomputed distances to a few anchor
nodes — the fallback when CH's fixed weighting won't do.

Everything below funnels edge costs through **one** interface. Meet it first:

```java
public interface Weighting {
    double calcMinWeightPerDistance();                                  // :35  (heuristic lower bound)
    double calcEdgeWeight(EdgeIteratorState edgeState, boolean reverse);// :48  (the per-edge cost)
    double calcTurnWeight(int inEdge, int viaNode, int outEdge);        // :56
    boolean hasTurnCosts();                                             // :65
```
📌 `core/src/main/java/com/graphhopper/routing/weighting/Weighting.java:27`. Hold `calcEdgeWeight` — every
algorithm in this chapter calls it (indirectly) to ask "what does traversing this edge cost?"

## 3.3 Case study A — Dijkstra

All the algorithms share a base that holds the graph, the weighting, and — note this — an `EdgeExplorer`:

```java
public abstract class AbstractRoutingAlgorithm implements RoutingAlgorithm {
    protected final Graph graph;
    protected final Weighting weighting;
    // ...
    edgeExplorer = graph.createEdgeExplorer();     // :56
```
📌 `core/src/main/java/com/graphhopper/routing/AbstractRoutingAlgorithm.java:33`–`:57`. Dijkstra adds the two
classic data structures — a priority queue ordered by weight, and a map from node id to its best-known
entry:

```java
protected IntObjectMap<SPTEntry> fromMap;     // :40  node id → best entry so far
protected PriorityQueue<SPTEntry> fromHeap;   // :41  frontier, min-weight first
```
📌 `core/src/main/java/com/graphhopper/routing/Dijkstra.java:40`–`:41` (allocated in `initCollections`,
`:52`–`:55`). An `SPTEntry` is one node in the shortest-path tree — a weight, the edge used to reach it, and
a parent back-pointer, made heap-orderable by `compareTo`:

```java
public class SPTEntry implements Comparable<SPTEntry> {
    public int edge; public int adjNode; public double weight; public SPTEntry parent;
    // ...
    public int compareTo(SPTEntry o) { if (weight < o.weight) return -1; ...   // :68
```
📌 `core/src/main/java/com/graphhopper/routing/SPTEntry.java:28`–`:44`,`:67`–`:74`. The heart is the main
loop — poll the cheapest frontier node, relax its neighbours:

```java
currEdge = fromHeap.poll();
if (currEdge.isDeleted())          // :73  lazy deletion: skip a stale entry
    continue;
// ...for each neighbour edge `iter`:
double tmpWeight = GHUtility.calcWeightWithTurnWeight(weighting, iter, false, currEdge.edge)
                   + currEdge.weight;                                         // :85
// ...
if (nEdge == null) {               // first time we reach this neighbour
    nEdge = new SPTEntry(iter.getEdge(), iter.getAdjNode(), tmpWeight, currEdge);  // :93
} else if (nEdge.weight > tmpWeight) {   // found a cheaper way in
    nEdge.setDeleted();            // :97  mark the old entry dead, insert a fresh one
    // ...
}
```
📌 `Dijkstra.java:70`–`:107`; it stops when the polled node is the target (`finished()` returns
`currEdge.adjNode == to`, `:109`–`:111`).

> 💡 **A real-code detail worth catching:** GraphHopper does **not** do a textbook decrease-key. When it
> finds a cheaper path to a node, it marks the old heap entry `setDeleted()` and inserts a new one; stale
> entries are skipped on poll (`:73`). Lazy deletion is simpler and, with a binary heap, usually faster —
> a nice example of production code diverging from the textbook for good reasons.

And the choke point everything funnels through — where the pluggable `Weighting` is actually invoked:

```java
// GHUtility.calcWeightWithTurnWeight(...)
double weight = weighting.calcEdgeWeight(edgeState, reverse);   // :461
// ...+ turn cost via weighting.calcTurnWeight(...)
```
📌 `core/src/main/java/com/graphhopper/util/GHUtility.java:460`–`:469`. **Every** algorithm in this chapter
relaxes edges through this one call. Swap the `Weighting` (Chapter 4) and every algorithm's notion of
"shortest" changes, without touching the search code.

## 3.4 Case study B — A* and bidirectional

A* is Dijkstra plus a **heuristic**: an optimistic estimate `h(n)` of the remaining cost to the target,
added to the real cost so far `g(n)`. The frontier is ordered by `f = g + h`, so it leans toward the goal.
The heuristic is pluggable:

```java
private WeightApproximator weightApprox;   // :48
// default: a beeline (straight-line) estimate
```
📌 `core/src/main/java/com/graphhopper/routing/AStar.java:48`,`:52`–`:59`. The crux is that an `AStarEntry`
carries **two** weights — the heap key `g+h`, and the *real* path weight `g` used when it becomes a parent:

```java
// AStarEntry: weightForHeap (g+h)  vs  weightOfVisitedPath (g)
public double getWeightOfVisitedPath() { return weightOfVisitedPath; }   // :186
```
📌 `AStar.java:173`–`:194`. In the loop, `g` is the real cost, `h` is the approximation, and their sum is
what orders the queue:

```java
double tmpWeight = GHUtility.calcWeightWithTurnWeight(weighting, iter, false, currEdge.edge)
                   + currEdge.weightOfVisitedPath;                 // :119  g
double currWeightToGoal = weightApprox.approximate(neighborNode); // :128  h
double estimationFullWeight = tmpWeight + currWeightToGoal;       // :131  f = g + h → heap key
```
📌 `AStar.java:103`–`:148`. For A* to stay **optimal**, `h` must never overestimate — it must be an
*admissible* lower bound. The default beeline does this by multiplying straight-line distance by the
cheapest possible weight-per-metre:

```java
weight2goal = minWeightPerDistance * dist2goal;   // :70  (minWeightPerDistance from Weighting :35)
```
📌 `core/src/main/java/com/graphhopper/routing/weighting/BeelineWeightApproximator.java:66`–`:72`. Since the
real road can only be longer and slower than the straight line at top speed, this can only *under*estimate —
so A* never wrongly discards the true shortest path.

**Bidirectional** search doubles the win. A generic base runs two frontiers and remembers where they meet:

```java
// two everything: bestWeightMapFrom / bestWeightMapTo, pqOpenSetFrom / pqOpenSetTo, bestWeight
```
📌 `core/src/main/java/com/graphhopper/routing/AbstractBidirAlgo.java:37`–`:50`. Whenever an edge relaxation
lands on a node the *other* search has already reached, it updates the best meeting weight `μ`:

```java
double weight = entry.getWeightOfVisitedPath() + entryOther.getWeightOfVisitedPath();  // :183
if (weight < bestWeight) { bestFwdEntry = ...; bestBwdEntry = ...; bestWeight = weight; }  // :193
```
📌 `AbstractBidirAlgo.java:176`–`:198`. And it stops when the two frontier tops can no longer possibly beat
that best meeting — the classic bidirectional stopping condition:

```java
return currFrom.weight + currTo.weight >= bestWeight;   // :169
```
📌 `AbstractBidirAlgo.java:165`–`:170`. Non-CH bidirectional Dijkstra/A* fill both frontiers via
`fillEdgesFrom`/`fillEdgesTo`, again routing edge cost through `calcWeight` → `calcEdgeWeight`
(`AbstractNonCHBidirAlgo.java:110`–`:198`).

> ⚠️ **Bidirectional A\* is subtle.** Two independent heuristics (one per direction) aren't *consistent*
> with each other, so the naïve stop condition is wrong. `AStarBidirection` uses a **balanced**
> approximator and adds a `stoppingCriterionOffset` to `finished()`
> (`AStarBidirection.java:58`–`:95`, esp. `:77`–`:82`). GraphHopper's own class comment notes bidirectional
> A* is *less* effective than bidirectional Dijkstra — which is exactly why the next step isn't "better
> heuristics" but "preprocess the graph."

## 3.5 Case study C — Contraction Hierarchies

This is the production speedup, and it's a two-phase idea: **preprocess** the graph into a hierarchy of
"shortcuts," then run a query that only ever climbs the hierarchy.

**Preprocessing — contract nodes, add shortcuts.** Contraction removes nodes one at a time, cheapest
("least important") first, and whenever removing a node would break a shortest path, it adds a **shortcut**
edge that preserves it. The contraction order is a priority queue that supports updates:

```java
// nodes with highest priority come last
private MinHeapWithUpdate sortedNodes;   // :69
```
📌 `core/src/main/java/com/graphhopper/routing/ch/PrepareContractionHierarchies.java:68`–`:69`. Every node
gets an initial priority (`updatePrioritiesOfRemainingNodes`, `:201`–`:211`), then the loop repeatedly polls
the least-important node, re-checking its priority lazily before committing (priorities go stale as
neighbours contract):

```java
while (!sortedNodes.isEmpty()) {
    int polledNode = sortedNodes.poll();                 // :264
    if (priority > sortedNodes.peekValue()) { re-push; continue; }  // :266  lazy update
    contractNode(polledNode, level);                     // :279
    // recompute priorities of the contracted node's neighbours   :288–:295
```
📌 `PrepareContractionHierarchies.java:213`–`:313`. Contracting a node assigns it a CH **level** and hands
off to a `NodeContractor`:

```java
chBuilder.setLevel(node, level);       // :347
nodeContractor.contractNode(node);     // :348
```
📌 `PrepareContractionHierarchies.java:343`–`:351`. The priority itself is (roughly) *edge difference* — how
many shortcuts adding this node would create versus how many edges it removes:

```java
int edgeDifference = shortcutsCount - prepareGraph.getDegree(node);                 // :108
return params.edgeDifferenceWeight * edgeDifference
     + params.originalEdgesCountWeight * originalEdgesCount;                          // :111
```
📌 `core/src/main/java/com/graphhopper/routing/ch/NodeBasedNodeContractor.java:90`–`:115`. Before adding a
shortcut, a **witness search** checks whether a cheaper path already exists that avoids the node — if so, no
shortcut is needed:

```java
double maxWeight = witnessPathSearcher.findUpperBound(toNode, existingDirectWeight, maxVisitedNodes); // :242
if (maxWeight <= existingDirectWeight) continue;   // :245  witness found → skip the shortcut
// else: handler.handleShortcut(...)                :249
```
📌 `NodeBasedNodeContractor.java:209`–`:254`. A real shortcut records the two edges it bridges, so a query
can later expand it back into the real path:

```java
int shortcut = chBuilder.addShortcutNodeBased(sc.from, sc.to, sc.flags, sc.weight,
                                              sc.skippedEdge1, sc.skippedEdge2);   // :137
```
📌 `NodeBasedNodeContractor.java:131`–`:148`.

**Query — only climb.** A CH query is bidirectional, but with one rule: only ever traverse toward an
**equal-or-higher** level. That single filter is what makes it skip the millions of unimportant local nodes:

```java
return graph.getLevel(base) <= graph.getLevel(adj);   // :295  upward edges only
```
📌 `core/src/main/java/com/graphhopper/routing/AbstractBidirCHAlgo.java:278`–`:297` (forward uses the
out-explorer, backward the in-explorer, `:135`–`:175`; both searches must finish, `:125`–`:133`). The
concrete query algorithm adds **stall-on-demand** — abandoning a frontier node if a cheaper route to it
exists via a higher edge, avoiding wasted expansion:

```java
// entryIsStallable(...): if a neighbour offers a cheaper route to this node, stall it
```
📌 `core/src/main/java/com/graphhopper/routing/DijkstraBidirectionCH.java:33`–`:68`. The factory picks it
by default (`CHRoutingAlgorithmFactory.java:47`–`:95`, node-based default `DijkstraBidirectionCH` at
`:84`–`:89`).

> 🧠 **Mental model:** CH trades **preprocessing time and shortcut memory** for **query speed**, and it
> gives up **flexibility** — the weighting is baked in at preprocessing time, so you can't change the cost
> function per request. That trade is why the next case study exists.

## 3.6 Case study D — Landmarks / ALT

Landmarks (the "ALT" = A*, Landmarks, Triangle-inequality) is the middle ground: much faster than plain A*,
but — unlike CH — it still works when the weighting can vary. It's just A* with a *sharp* heuristic built
from precomputed distances to a handful of **landmark** nodes.

Preparation picks landmarks and stores, for each, the distance to and from every node:

```java
lms.createLandmarks();   // :118
lms.flush();             // :119
```
📌 `core/src/main/java/com/graphhopper/routing/lm/PrepareLandmarks.java:111`–`:125`. Landmarks are chosen by
a greedy **farthest-point** heuristic (first landmark = the farthest node; each next = farthest from all
chosen so far), spreading them to the graph's corners:

```java
landmarkNodeIdsToReturn[0] = explorer.getLastEntry().adjNode;   // :744  first = farthest node
// each subsequent landmark = farthest from ALL current landmarks
```
📌 `core/src/main/java/com/graphhopper/routing/lm/LandmarkStorage.java:734`–`:760`; the from/to weights are
computed by a Dijkstra from each landmark and stored compactly as 16-bit shorts (`:406`–`:475`, read at
`:525`–`:566`).

The heuristic is the **triangle inequality**. For any landmark `L`, the true distance `d(v,t)` is at least
`|d(v,L) − d(t,L)|` — a bound you get for free from the stored tables, and a *much* tighter lower bound than
a beeline:

```java
int rhs1Int = lms.getToWeight(activeLandmarkIndices[i], v)   - weightsFromTToActiveLandmarks[i];   // :170
int rhs2Int = weightsFromActiveLandmarksToT[i] - lms.getFromWeight(activeLandmarkIndices[i], v);   // :171
// ...
return Math.max(rhs1Int, rhs2Int);   // :177  best bound over the two directions
```
📌 `core/src/main/java/com/graphhopper/routing/lm/LMApproximator.java:139`–`:178`; `approximate()` takes the
best active landmark and falls back to the beeline, keeping whichever bound is *larger* (both are admissible,
so the larger is tighter):

```java
return Math.max(lmApproximation, beelineApproximation.approximate(v));   // :126
```
📌 `LMApproximator.java:94`–`:137`. Because `LMApproximator implements WeightApproximator` (`:34`), it plugs
straight into the *same* A* machinery from §3.4 — Landmarks is literally "A* with a better `h`."

## 3.7 Tie-together — who picks which

`Router` makes the call, based purely on what was prepared at import time:

```java
if (chEnabled && !disableCH)        return createCHSolver(...);    // :193  fastest, fixed weighting
else if (lmEnabled && !disableLM)   return createLMSolver(...);    // :195  fast, flexible weighting
else                                return createFlexSolver(...);  // :197  plain Dijkstra/A*, fully flexible
```
📌 `core/src/main/java/com/graphhopper/routing/Router.java:190`–`:200` (`chEnabled`/`lmEnabled` = "were CH
graphs / landmarks built?", `:88`–`:89`). The flexible path resolves a string to a concrete algorithm:

```java
case DIJKSTRA_BI: return new DijkstraBidirectionRef(...);   // :44
case ASTAR_BI:    return new AStarBidirection(...);         // :49  (the default)
```
📌 `core/src/main/java/com/graphhopper/routing/RoutingAlgorithmFactorySimple.java:40`–`:60`. So the same
`RoutingAlgorithm` interface (`calcPath`, `getVisitedNodes`, `RoutingAlgorithm.java:28`) is satisfied by
plain Dijkstra, A*, a CH query, or an LM-guided A* — and the whole difference in speed is *how much of the
graph each visits* to return the identical optimal path.

## 3.8 Lab 3 — Dijkstra vs A* vs CH

> 🧪 **Lab 3.** Read-only. Goal: see, in one number — visited nodes — why the family exists. Record in
> [`labs/lab03-algorithms.md`](labs/lab03-algorithms.md).

```bash
cd ~/Documents/learning/graphhopper
# confirm the choke point and the CH upward-only rule:
sed -n '460,469p' core/src/main/java/com/graphhopper/util/GHUtility.java
sed -n '295p'     core/src/main/java/com/graphhopper/routing/AbstractBidirCHAlgo.java
sed -n '169p'     core/src/main/java/com/graphhopper/routing/AbstractBidirAlgo.java

# every RoutingAlgorithm exposes getVisitedNodes(); compare CH vs flexible on the SAME route.
# In config-example.yml, profiles_ch enables CH; add ?ch.disable=true to force the flexible path:
curl -s "http://localhost:8989/route?point=52.55,13.35&point=52.47,13.50&profile=car" \
     | python3 -c "import sys,json; d=json.load(sys.stdin); print('CH  took(ms)=', d['info']['took'])"
curl -s "http://localhost:8989/route?point=52.55,13.35&point=52.47,13.50&profile=car&ch.disable=true&lm.disable=true" \
     | python3 -c "import sys,json; d=json.load(sys.stdin); print('flex took(ms)=', d['info']['took'])"
```

**Expected:** `GHUtility.java:461` reads `weighting.calcEdgeWeight(edgeState, reverse)`;
`AbstractBidirCHAlgo.java:295` is the `getLevel(base) <= getLevel(adj)` upward filter; the CH request returns
in a fraction of the flexible request's time — the **same** distance, far less work. (To disable CH the
server must have `ch.disable` allowed; otherwise compare against a build with `profiles_ch: []`.)

## 3.9 Checkpoint

1. Every algorithm here calls the same method to price an edge. Which method, in which file, and why does
   that make the `Weighting` swappable without touching search code?
2. GraphHopper's Dijkstra doesn't do a decrease-key. What does it do instead, and where is a stale entry
   skipped?
3. In A*, an `AStarEntry` holds two weights. What are they, and which one orders the heap vs becomes the
   parent's path cost? Why must the heuristic under-estimate?
4. What does Contraction Hierarchies precompute, what single rule does its *query* enforce, and what does it
   give up to get its speed?
5. Landmarks is "A* with a better `h`." Where does that `h` come from, and why is `|d(v,L) − d(t,L)|` a
   valid lower bound?
6. Given a request, `Router` chooses CH, LM, or flexible. What decides, and when would each be right?

> If #4 is shaky, re-read §3.5. If #3 or #5 is shaky, re-read §3.4 and §3.6 together — they're the same
> A* machinery with different heuristics.

## 🔌 Connect to your past (ETA, dispatch & the matrix)

This chapter is why GraphHopper is the right engine to study for *your* work. A ride-hailing backend lives
and dies on shortest-path queries: the rider's ETA is one `route`; "which of my 30 nearby drivers is
closest by road" is a **matrix** of shortest paths (Chapter 7's `/matrix`/SPT), run on every dispatch. Now
you know the levers. If those queries need to respect live conditions — a per-request cost that changes with
traffic or vehicle type — you *can't* use CH (its weighting is frozen at import); you want **Landmarks**,
the flexible-but-fast path from §3.6. If the cost function is fixed, CH's ~1000× speedup is free money. And
for VinBus/BusMap, the same `Weighting` choke point (§3.3) is where a "buses avoid this street" rule would
plug in — one method, every algorithm respects it. The family isn't academic; it's the menu you order ETAs
from.

**Next:** you've seen *how* the search runs. Now the other half — how you *shape* what "shortest" means:
profiles, custom models, and the encoded values the `Weighting` reads.
→ **[Chapter 04 — Profiles, Weighting & Custom Models](04-profiles-weighting-custom-models.md)**
