# Glossary & Source Index

> Terms and the **Key files** source index for the **GraphHopper Internals Handbook**, grounded in
> [`graphhopper/graphhopper`](https://github.com/graphhopper/graphhopper) @ **`11.0`** (`69e50f6`). Line
> numbers are pinned to this ref — re-verify after re-pinning (Chapter 8).

## Graph & lưu trữ

| Term | Nghĩa |
|------|---------|
| **`GraphHopper` (façade)** | Class entry công khai; cấu hình bằng các fluent setter, rồi gọi `importOrLoad()` và `route()`. |
| **import vs query** | Hai pha: `importOrLoad()` build/load graph + CH/LM một lần; `route()` chạy read-only cho mỗi request. |
| **`graph-cache/`** | Thư mục trên đĩa mà bước import ghi ra; một warm start sẽ memory-map nó thay vì parse lại OSM. |
| **`BaseGraph`** | Mạng lưới đường được lưu dưới dạng các mảng node và edge phẳng, đánh địa chỉ bằng integer (không phải object). |
| **node / edge** | Mỗi cái là một id kiểu `int` trỏ vào một mảng phẳng; một edge lưu hai endpoint của nó + một con trỏ next-edge cho mỗi endpoint. |
| **`OSMReader`** | Parse một file `.osm.pbf`; cắt các way tại giao lộ rồi gọi `addEdge` để tạo edge của graph. |
| **`EdgeExplorer` / `EdgeIterator`** | Một con trỏ quét qua linked-list các edge của một node; iterator là một flyweight, được mutate tại chỗ sau mỗi `next()`. |
| **`EdgeIteratorState`** | View đọc của một edge: `getEdge()`, `getAdjNode()`, `getDistance()`, `fetchWayGeometry()`. |
| **`PointList`** | Hình học (geometry) của một edge — polyline gồm các điểm nằm giữa hai node endpoint của nó. |
| **`DataAccess`** | Lớp abstraction cho storage: `RAMDataAccess` (`byte[][]` on-heap) hoặc `MMapDataAccess` (file memory-mapped). |
| **`TurnCostStorage`** | Lưu các turn restriction/cost theo bộ ba `(fromEdge, viaNode, toEdge)`. |
| **frozen graph** | Sau khi import, graph bị freeze — không thêm base edge mới, chỉ còn các CH shortcut. |

## Thuật toán (shortest path)

| Term | Nghĩa |
|------|---------|
| **`Weighting`** | Hàm chi phí per-edge có thể cắm thay (pluggable); `calcEdgeWeight(edge, reverse)` được (gián tiếp) gọi bởi mọi thuật toán. |
| **`SPTEntry`** | Một node của shortest-path-tree: weight + edge dẫn tới + con trỏ ngược về parent; được sắp trên heap theo weight. |
| **lazy deletion** | Cách GraphHopper thay cho decrease-key: đánh dấu một entry cũ trên heap là đã xóa, chèn một entry mới, và bỏ qua các entry đã xóa khi poll. |
| **Dijkstra** | Shortest path không có thông tin dẫn hướng; nới rộng dần một frontier theo weight cho tới khi chạm target. |
| **A\*** | Dijkstra + một heuristic admissible `h`; sắp frontier theo `f = g + h` nên nó nghiêng về phía đích. |
| **admissible heuristic** | Một chặn dưới không bao giờ ước lượng vượt quá chi phí còn lại — điều kiện để A* vẫn tối ưu. |
| **beeline approximator** | Heuristic mặc định của A*: khoảng cách đường thẳng × weight-per-metre rẻ nhất. |
| **bidirectional search** | Hai frontier (xuất phát từ source và từ target); dừng khi chúng không còn cải thiện được weight gặp nhau tốt nhất. |
| **Contraction Hierarchies (CH)** | Tiền xử lý các node thành level + shortcut edge; query chỉ đi lên trên, bỏ qua các node cục bộ. Nhanh hơn ~1000×, nhưng cố định weighting. |
| **shortcut** | Một edge được thêm trong lúc contraction để giữ nguyên shortest path đi vòng qua một node đã gỡ; nó ghi lại hai edge mà nó bắc cầu. |
| **witness search** | Phép kiểm tra trong lúc contraction, tránh thêm một shortcut nếu đã tồn tại một đường thay thế rẻ hơn. |
| **stall-on-demand** | Tối ưu cho CH query: bỏ một node ở frontier nếu tồn tại một đường tới nó rẻ hơn qua một edge cao hơn. |
| **Landmarks / ALT** | A* với một heuristic sắc bén dựng từ các khoảng cách tính sẵn tới các anchor node; vừa nhanh *vừa* linh hoạt (khác với CH). |
| **triangle inequality (LM)** | `d(v,t) ≥ |d(v,L) − d(t,L)|` với mọi landmark `L` — chặn dưới của ALT. |

## Weighting & profile

| Term | Nghĩa |
|------|---------|
| **`Profile`** | Config gắn một cái tên với một weighting (mặc định `custom`), một thiết lập turn-cost, và một `CustomModel`. |
| **`CustomWeighting`** | Weighting mặc định: `weight = distance/(speed·priority) + distance·distance_influence`. |
| **`CustomModel`** | Một DSL cấu hình gồm các câu lệnh `speed` / `priority` / `distance_influence` được đánh giá trên từng edge. |
| **`CustomModelParser`** | Biên dịch một `CustomModel` thành Java bytecode (Janino) lúc import — các câu lệnh không bị thông dịch lại trên từng edge. |
| **`ValueExpressionVisitor`** | Ranh giới bảo mật: whitelist các method (chỉ `sqrt`) và các encoded value mà một biểu thức được phép chạm tới. |
| **encoded value** | Một thuộc tính per-edge có tên, độ rộng bit cố định (`road_class`, `max_weight`, `roundabout`, access). |
| **`EncodingManager`** | Registry sở hữu toàn bộ encoded value và cấp phát các lát bit không chồng lấn. |
| **`EncodedValue.init`** | Nơi một value giành lấy các bit của nó (shift + mask) trong bản ghi edge. |

## Giao thông công cộng (GTFS & RAPTOR)

| Term | Nghĩa |
|------|---------|
| **GTFS** | General Transit Feed Specification — feed tĩnh (stops, trips, stop_times, transfers) mà GraphHopper import vào. |
| **`GtfsReader`** | Dựng transit graph: `createTrips()` + `wireUpStops()` + `insertGtfsTransfers()`. |
| **`PtGraph`** | Transit graph đã time-expand — mỗi *event* stop-time là một node, được lưu trên DataAccess giống `BaseGraph`. |
| **time expansion** | Gấp thời gian biểu vào trong graph để một phép tìm kiếm thường vẫn tự động tôn trọng giờ khởi hành. |
| **`EdgeType`** | Bộ từ vựng cho transit edge: `BOARD`, `ALIGHT`, `HOP`, `DWELL`, `TRANSFER`, `WAIT`, `ENTER_PT`, … |
| **`Label`** | Một trạng thái tìm kiếm transit: giờ đến (`currentTime`), `nTransfers`, thời gian đi bộ (`streetTime`), parent. |
| **`MultiCriteriaLabelSetting`** | Tìm kiếm kiểu RAPTOR, giữ một tập Pareto các label không bị lấn át (non-dominated) trên mỗi node. |
| **domination** | Một label chỉ được giữ nếu không có label nào hiện có thắng nó trên mọi tiêu chí; nó cũng loại bỏ những label mà nó lấn át. |
| **`RealtimeFeed`** | Một lớp phủ GTFS-realtime gồm các edge bị chặn + các map delay theo từng edge, được phép tìm kiếm đọc vào (không phải build lại graph). |

## Map-matching

| Term | Nghĩa |
|------|---------|
| **map-matching** | Khôi phục lại đường đi thực tế của một xe từ một vệt GPS nhiễu. |
| **`MapMatching.match`** | Pipeline: candidate snap → query graph → trellis → Viterbi → `MatchResult`. |
| **emission probability** | Mức khả dĩ của một candidate snap khi đã biết điểm GPS — một phân phối normal theo khoảng cách snap. |
| **transition probability** | Mức hợp lý của bước chuyển giữa hai candidate — phạt theo hàm exponential trên `|route − straight-line|` (Newson & Krumm). |
| **`HmmProbabilities`** | Giữ các hàm log-probability cho emission (normal) và transition (exponential). |
| **Viterbi** | Bước decode chọn ra chuỗi candidate khả dĩ nhất; ở đây là một label-setting bằng PQ được inline vào. |
| **`MatchResult`** | Kết quả đầu ra: các edge đã match, chiều dài đã match (quãng đường thực đã đi), và path đã gộp. |

## Web / API

| Term | Nghĩa |
|------|---------|
| **`GHRequest` / `GHResponse`** | Các value object request (points + profile) và response (best path + alternative + error) trong `web-api`. |
| **`Router`** | Được dựng cho mỗi request; validate, rồi dispatch tới một solver CH / LM / flexible. |
| **`ResponsePath`** | Một tuyến đường: distance, time, geometry (`PointList`), `InstructionList`, và các `PathDetail`. |
| **`InstructionsFromEdges`** | Biến các edge của một path thành các `Instruction` chỉ đường từng chặng, kèm sign code. |
| **sign code** | Mã rẽ dạng integer: `CONTINUE=0`, `TURN_LEFT=-2`, `TURN_RIGHT=2`, `FINISH=4`, `USE_ROUNDABOUT=6`, `PT_*=101+`. |
| **`PathDetail`** | Một value gắn theo khoảng dọc tuyến đường (ví dụ `road_class` trên các edge 6–9). |
| **`/route` `/isochrone` `/nearest` `/mvt` `/spt`** | Các HTTP endpoint — những phép chiếu của cùng một bộ máy graph + shortest-path. |
| **isochrone** | Toàn bộ những nơi có thể tới trong một giới hạn time/distance — một *cây* shortest-path, được vẽ đường viền thành polygon. |

---

## Key files — chỉ mục source

Các symbol mà cuốn sách này dựng trên. Sau khi re-pin (Chương 8), hãy re-verify những cái này trước.

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
