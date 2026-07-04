# Glossary & Source Index

> Terms and the **Key files** source index for the **GraphHopper Internals Handbook**, grounded in
> [`graphhopper/graphhopper`](https://github.com/graphhopper/graphhopper) @ **`11.0`** (`69e50f6`). Line
> numbers are pinned to this ref — re-verify after re-pinning (Chapter 8).

## Graph & storage

| Term | Meaning |
|------|---------|
| **`GraphHopper` (façade)** | The public entry class; configure with fluent setters, then `importOrLoad()` and `route()`. |
| **import vs query** | The two phases: `importOrLoad()` builds/loads the graph + CH/LM once; `route()` runs read-only per request. |
| **`graph-cache/`** | The on-disk directory the import writes; a warm start memory-maps it instead of re-parsing OSM. |
| **`BaseGraph`** | The road network stored as flat, integer-addressed node and edge arrays (not objects). |
| **node / edge** | Each is an `int` id indexing into a flat array; an edge stores its two endpoints + a next-edge pointer per endpoint. |
| **`OSMReader`** | Parses an `.osm.pbf`; splits ways at junctions and calls `addEdge` to create graph edges. |
| **`EdgeExplorer` / `EdgeIterator`** | A cursor that sweeps a node's edge linked-list; the iterator is a flyweight, mutated in place per `next()`. |
| **`EdgeIteratorState`** | The read view of one edge: `getEdge()`, `getAdjNode()`, `getDistance()`, `fetchWayGeometry()`. |
| **`PointList`** | An edge's geometry — the polyline of points between its two endpoint nodes. |
| **`DataAccess`** | The storage abstraction: `RAMDataAccess` (on-heap `byte[][]`) or `MMapDataAccess` (memory-mapped files). |
| **`TurnCostStorage`** | Stores turn restrictions/costs against a `(fromEdge, viaNode, toEdge)` triple. |
| **frozen graph** | After import, the graph is frozen — no new base edges, only CH shortcuts. |

## Algorithms (shortest path)

| Term | Meaning |
|------|---------|
| **`Weighting`** | The pluggable per-edge cost function; `calcEdgeWeight(edge, reverse)` is called (indirectly) by every algorithm. |
| **`SPTEntry`** | A shortest-path-tree node: weight + reaching edge + parent back-pointer; heap-ordered by weight. |
| **lazy deletion** | GraphHopper's substitute for decrease-key: mark a stale heap entry deleted, insert a fresh one, skip deleted on poll. |
| **Dijkstra** | Uninformed shortest path; settles a growing frontier by weight until it reaches the target. |
| **A\*** | Dijkstra + an admissible heuristic `h`; orders the frontier by `f = g + h` so it leans toward the goal. |
| **admissible heuristic** | A lower bound that never overestimates remaining cost — required for A* to stay optimal. |
| **beeline approximator** | Default A* heuristic: straight-line distance × cheapest weight-per-metre. |
| **bidirectional search** | Two frontiers (from source and target); stops when they can no longer beat the best meeting weight. |
| **Contraction Hierarchies (CH)** | Preprocess nodes into levels + shortcut edges; the query only traverses upward, skipping local nodes. ~1000× faster, fixed weighting. |
| **shortcut** | An edge added during contraction that preserves a shortest path around a removed node; records the two edges it bridges. |
| **witness search** | The check during contraction that avoids adding a shortcut if a cheaper alternative path already exists. |
| **stall-on-demand** | CH query optimization: abandon a frontier node if a cheaper route to it exists via a higher edge. |
| **Landmarks / ALT** | A* with a sharp heuristic from precomputed distances to anchor nodes; fast *and* flexible (unlike CH). |
| **triangle inequality (LM)** | `d(v,t) ≥ |d(v,L) − d(t,L)|` for any landmark `L` — the ALT lower bound. |

## Weighting & profiles

| Term | Meaning |
|------|---------|
| **`Profile`** | Config binding a name to a weighting (default `custom`), turn-cost setting, and a `CustomModel`. |
| **`CustomWeighting`** | The default weighting: `weight = distance/(speed·priority) + distance·distance_influence`. |
| **`CustomModel`** | Config DSL of `speed` / `priority` / `distance_influence` statements evaluated per edge. |
| **`CustomModelParser`** | Compiles a `CustomModel` to Java bytecode (Janino) at import time — statements aren't interpreted per edge. |
| **`ValueExpressionVisitor`** | The security boundary: whitelists methods (`sqrt` only) and the encoded values an expression may touch. |
| **encoded value** | A named, fixed-bit-width per-edge attribute (`road_class`, `max_weight`, `roundabout`, access). |
| **`EncodingManager`** | The registry that owns all encoded values and hands out non-overlapping bit slices. |
| **`EncodedValue.init`** | Where a value claims its bits (shift + mask) in the edge record. |

## Public transit (GTFS & RAPTOR)

| Term | Meaning |
|------|---------|
| **GTFS** | General Transit Feed Specification — the static feed (stops, trips, stop_times, transfers) GraphHopper imports. |
| **`GtfsReader`** | Builds the transit graph: `createTrips()` + `wireUpStops()` + `insertGtfsTransfers()`. |
| **`PtGraph`** | The time-expanded transit graph — one node per stop-time *event*, DataAccess-backed like `BaseGraph`. |
| **time expansion** | Folding schedule time into the graph so a plain search respects departure times automatically. |
| **`EdgeType`** | The transit edge vocabulary: `BOARD`, `ALIGHT`, `HOP`, `DWELL`, `TRANSFER`, `WAIT`, `ENTER_PT`, … |
| **`Label`** | A transit search state: arrival time (`currentTime`), `nTransfers`, walk time (`streetTime`), parent. |
| **`MultiCriteriaLabelSetting`** | RAPTOR-style search keeping a Pareto set of non-dominated labels per node. |
| **domination** | A label is kept only if no existing label beats it on every criterion; it prunes ones it dominates. |
| **`RealtimeFeed`** | A GTFS-realtime overlay of blocked edges + per-edge delay maps read by the search (no graph rebuild). |

## Map-matching

| Term | Meaning |
|------|---------|
| **map-matching** | Recovering the road path a vehicle actually took from a noisy GPS trace. |
| **`MapMatching.match`** | The pipeline: candidate snaps → query graph → trellis → Viterbi → `MatchResult`. |
| **emission probability** | How likely a candidate snap is given the GPS point — a normal distribution on snap distance. |
| **transition probability** | How plausible the move between two candidates is — exponential penalty on `|route − straight-line|` (Newson & Krumm). |
| **`HmmProbabilities`** | Holds the emission (normal) and transition (exponential) log-probability functions. |
| **Viterbi** | The decode that picks the single most probable candidate sequence; here, an inlined PQ label-setting. |
| **`MatchResult`** | The output: matched edges, matched length (real distance driven), merged path. |

## Web / API

| Term | Meaning |
|------|---------|
| **`GHRequest` / `GHResponse`** | The request (points + profile) and response (best path + alternatives + errors) value objects in `web-api`. |
| **`Router`** | Built per request; validates, then dispatches to a CH / LM / flexible solver. |
| **`ResponsePath`** | One route: distance, time, geometry (`PointList`), `InstructionList`, `PathDetail`s. |
| **`InstructionsFromEdges`** | Turns a path's edges into turn-by-turn `Instruction`s with sign codes. |
| **sign code** | Integer turn code: `CONTINUE=0`, `TURN_LEFT=-2`, `TURN_RIGHT=2`, `FINISH=4`, `USE_ROUNDABOUT=6`, `PT_*=101+`. |
| **`PathDetail`** | An interval-tagged value along a route (e.g. `road_class` over edges 6–9). |
| **`/route` `/isochrone` `/nearest` `/mvt` `/spt`** | The HTTP endpoints — projections of the same graph + shortest-path machinery. |
| **isochrone** | Everywhere reachable within a time/distance limit — a shortest-path *tree*, contoured to a polygon. |

---

## Key files — the source index

The symbols this book is built on. After re-pinning (Chapter 8), re-verify these first.

| Symbol / concept | file:line |
|------------------|-----------|
| `GraphHopper` façade / `importOrLoad()` | `core/.../GraphHopper.java:85` / `:793` |
| `GraphHopper.route()` → fresh `Router` | `core/.../GraphHopper.java:1333` |
| `Router` / `route()` / `createSolver()` (CH·LM·flex) | `core/.../routing/Router.java:58` / `:97` / `:190` |
| `OSMReader` / `readGraph()` / `addEdge()` | `core/.../reader/osm/OSMReader.java:75` / `:152` / `:318` |
| `BaseGraph` / `edge(nodeA, nodeB)` | `core/.../storage/BaseGraph.java:49` / `:291` |
| `EdgeExplorer.setBaseNode` / `EdgeIterator.next` | `core/.../util/EdgeExplorer.java:37` / `EdgeIterator.java:60` |
| `EdgeIteratorState` (`getEdge`/`getAdjNode`/`getDistance`) | `core/.../util/EdgeIteratorState.java:104` / `:133` / `:158` |
| `NodeAccess` / `PointList` | `core/.../storage/NodeAccess.java:30` / `web-api/.../util/PointList.java:40` |
| `DataAccess` / `RAMDataAccess` / `MMapDataAccess.map` | `core/.../storage/DataAccess.java:28` / `RAMDataAccess.java:35` / `MMapDataAccess.java:163` |
| `TurnCostStorage` | `core/.../storage/TurnCostStorage.java:39` |
| `Weighting.calcEdgeWeight` / `calcMinWeightPerDistance` | `core/.../routing/weighting/Weighting.java:48` / `:35` |
| `Weighting` choke point (turn-aware) | `core/.../util/GHUtility.java:461` |
| `AbstractRoutingAlgorithm` (base) | `core/.../routing/AbstractRoutingAlgorithm.java:33` |
| `Dijkstra` main loop / `finished()` | `core/.../routing/Dijkstra.java:70` / `:109` |
| `SPTEntry` / `compareTo` | `core/.../routing/SPTEntry.java:28` / `:68` |
| `AStar` loop (f = g + h) / `AStarEntry` | `core/.../routing/AStar.java:103` / `:173` |
| `BeelineWeightApproximator` (admissible h) | `core/.../routing/weighting/BeelineWeightApproximator.java:66` |
| `AbstractBidirAlgo` stop cond / `updateBestPath` | `core/.../routing/AbstractBidirAlgo.java:169` / `:176` |
| `AStarBidirection` (offset stop cond) | `core/.../routing/AStarBidirection.java:58` |
| `PrepareContractionHierarchies` loop / `contractNode` | `core/.../routing/ch/PrepareContractionHierarchies.java:213` / `:343` |
| CH priority (edge diff) / witness / add shortcut | `core/.../routing/ch/NodeBasedNodeContractor.java:108` / `:242` / `:137` |
| CH upward-only filter | `core/.../routing/AbstractBidirCHAlgo.java:295` |
| `DijkstraBidirectionCH` (stall-on-demand) | `core/.../routing/DijkstraBidirectionCH.java:49` |
| `CHRoutingAlgorithmFactory` | `core/.../routing/ch/CHRoutingAlgorithmFactory.java:84` |
| `PrepareLandmarks` / landmark selection | `core/.../routing/lm/PrepareLandmarks.java:111` / `LandmarkStorage.java:734` |
| `LMApproximator` (triangle-inequality h) | `core/.../routing/lm/LMApproximator.java:170` / `:126` |
| `RoutingAlgorithmFactorySimple` (string → algo) | `core/.../routing/RoutingAlgorithmFactorySimple.java:40` |
| `Profile` / `getCustomModel()` | `core/.../config/Profile.java:41` / `:105` |
| `CustomWeighting` formula / `calcEdgeWeight` | `core/.../routing/weighting/custom/CustomWeighting.java:63` / `:114` |
| `CustomModel` (speed/priority statements) | `web-api/.../util/CustomModel.java:30` |
| `CustomModelParser` (Janino compile) | `core/.../routing/weighting/custom/CustomModelParser.java:97` |
| `ValueExpressionVisitor` (method whitelist) | `core/.../routing/weighting/custom/ValueExpressionVisitor.java:38` |
| `EncodingManager` / `Builder.add` | `core/.../routing/util/EncodingManager.java:44` / `:137` |
| `EncodedValue.init` (bit packing) / `DecimalEncodedValue.getDecimal` | `core/.../routing/ev/EncodedValue.java:37` / `DecimalEncodedValue.java:20` |
| `RoadClass` / `MaxWeight` / `Roundabout` | `core/.../routing/ev/RoadClass.java:26` / `MaxWeight.java:31` / `Roundabout.java:20` |
| `GtfsReader.buildPtNetwork` / `addTrip` (HOP/BOARD/ALIGHT/DWELL) | `reader-gtfs/.../gtfs/GtfsReader.java:118` / `:263` |
| `GtfsStorage.EdgeType` | `reader-gtfs/.../gtfs/GtfsStorage.java:174` |
| `PtGraph` | `reader-gtfs/.../gtfs/PtGraph.java:32` |
| `Label` criteria (time / transfers / walk) | `reader-gtfs/.../gtfs/Label.java:43` / `:48` / `:51` |
| `MultiCriteriaLabelSetting` loop / `dominates` / `weight` | `reader-gtfs/.../gtfs/MultiCriteriaLabelSetting.java:66` / `:225` / `:243` |
| `PtRouterImpl.route` | `reader-gtfs/.../gtfs/PtRouterImpl.java:78` |
| `RealtimeFeed` (GTFS-realtime overlay) | `reader-gtfs/.../gtfs/RealtimeFeed.java:48` |
| `MapMatching.match` / `findCandidateSnaps` | `map-matching/.../matching/MapMatching.java:198` / `:294` |
| `computeViterbiSequence` / `router.calcPaths` | `map-matching/.../matching/MapMatching.java:382` / `:419` |
| `HmmProbabilities` emission / transition | `map-matching/.../matching/HmmProbabilities.java:47` / `:62` |
| `MatchResult.getMatchLength` | `map-matching/.../matching/MatchResult.java:91` |
| `RouteResource` (route call) / `GHRequest` | `web-bundle/.../resources/RouteResource.java:154` / `web-api/.../GHRequest.java:38` |
| `IsochroneResource` / `ShortestPathTree` | `web-bundle/.../resources/IsochroneResource.java:46` / `:105` |
| `NearestResource.findClosest` / `MVTResource` | `web-bundle/.../resources/NearestResource.java:70` / `MVTResource.java:48` |
| `InstructionsFromEdges.calcInstructions` / `getTurn` | `core/.../routing/InstructionsFromEdges.java:111` / `:355` |
| `Instruction` sign codes | `web-api/.../util/Instruction.java:34` |
| `ResponsePath` / `GHResponse.getBest` / `PathDetail` | `web-api/.../ResponsePath.java:34` / `GHResponse.java:48` / `util/details/PathDetail.java:25` |
| build root (Java 17) / server entry | `pom.xml:19` / `web/.../application/GraphHopperApplication.java:34` |

*A RumitX publication · [rumitx.com](https://rumitx.com)*
