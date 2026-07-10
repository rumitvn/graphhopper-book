# Chapter 03 — The Shortest-Path Algorithm Family ★

> **Goal:** Hiểu cách GraphHopper tìm ra route nhanh nhất băng qua cả một lục địa chỉ trong khoảng một
> mili-giây. Ta sẽ làm điều đó qua **bốn case study**: (A) **Dijkstra** thuần và cái `Weighting`
> cắm-thay-được; (B) **A\*** và điều kiện gặp nhau của **bidirectional**; (C) **Contraction Hierarchies**
> và *vì sao* nó nhanh hơn ~1000×; và (D) **Landmarks / ALT** cho những lúc bạn không thể precompute. Hết
> chương bạn giải thích được mỗi cái đánh đổi gì và chỉ được ra chỗ mà cái nào cũng gọi
> `Weighting.calcEdgeWeight`. Pinned tới **`11.0`** (`69e50f6`).

Đây là chương flagship, và cũng dài nhất, bởi đây là nơi một routing engine thật sự xứng với cái tên của
nó. Mọi chương trước nó *dựng* graph; mọi chương sau nó *định hình* hoặc *chuyên biệt hoá* cuộc search mà
bạn sắp đọc.

## 3.1 Vì sao quan trọng

Thuật toán Dijkstra đã 65 tuổi và viết vừa một mảnh giấy ăn. Vậy tại sao lại có nguyên một họ thuật toán ở
đây? Vì một Dijkstra cỡ mảnh-giấy-ăn chạy trên một graph hàng chục triệu node mất tới *hàng giây*, trong khi
một routing API chỉ có ngân sách *một mili-giây*. Cả họ thuật toán này là một chuỗi câu trả lời cho đúng một
câu hỏi — "làm sao lấy được cùng một optimal path, nhưng thăm ít phần của graph hơn nhiều?" — và mỗi câu trả
lời đều đánh đổi một thứ gì đó (memory, thời gian preprocessing, hay quyền tự do thay đổi cost function) để
mua lấy tốc độ.

Với bạn, đây cũng là chương ETA. Mỗi con số "từ đây tới đó mất bao lâu" mà một app gọi xe hay dẫn đường hiển
thị, bên dưới đều là một shortest-path query. Biết thuật toán nào trả lời nó — và mỗi thuật toán giả định
những gì — chính là ranh giới giữa "ETA chậm mà tôi không biết vì sao" và "chúng ta đang chạy trên flexible
path vì weighting đổi theo từng request; và đây là cách sửa".

## 3.2 Mental model: thu hẹp search frontier

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

Ba nước đi. **A\*** thêm một *heuristic* — một phỏng đoán lạc quan về quãng đường còn lại — để frontier vươn
về phía target thay vì phình ra mọi hướng. **Bidirectional** search chạy hai frontier, mỗi cái xuất phát từ
một đầu, và dừng khi chúng gặp nhau — mỗi bên chỉ khám phá nửa bán kính. **Contraction Hierarchies** đi xa
hơn: nó *preprocess* graph thành các level rồi thêm các edge "shortcut", nên một query chỉ leo lên những con
đường quan trọng hơn rồi gặp nhau ở giữa, bỏ qua hàng nghìn node cục bộ. **Landmarks/ALT** là A* với một
heuristic tốt hơn *rất nhiều*, dựng từ các khoảng cách tính sẵn tới một vài node mỏ neo — là phương án dự
phòng khi weighting cố định của CH không dùng được.

Mọi thứ bên dưới đều dồn edge cost qua **một** interface duy nhất. Làm quen với nó trước đã:

```java
public interface Weighting {
    double calcMinWeightPerDistance();                                  // :35  (heuristic lower bound)
    double calcEdgeWeight(EdgeIteratorState edgeState, boolean reverse);// :48  (the per-edge cost)
    double calcTurnWeight(int inEdge, int viaNode, int outEdge);        // :56
    boolean hasTurnCosts();                                             // :65
```
📌 `core/src/main/java/com/graphhopper/routing/weighting/Weighting.java:27`. Nhớ lấy `calcEdgeWeight` — mọi
thuật toán trong chương này đều gọi nó (gián tiếp) để hỏi "đi qua edge này tốn bao nhiêu?"

## 3.3 Case study A — Dijkstra

Tất cả các thuật toán dùng chung một lớp base giữ graph, weighting, và — để ý chỗ này — một `EdgeExplorer`:

```java
public abstract class AbstractRoutingAlgorithm implements RoutingAlgorithm {
    protected final Graph graph;
    protected final Weighting weighting;
    // ...
    edgeExplorer = graph.createEdgeExplorer();     // :56
```
📌 `core/src/main/java/com/graphhopper/routing/AbstractRoutingAlgorithm.java:33`–`:57`. Dijkstra thêm hai cấu
trúc dữ liệu kinh điển — một priority queue sắp theo weight, và một map từ node id tới entry tốt nhất đã biết
của nó:

```java
protected IntObjectMap<SPTEntry> fromMap;     // :40  node id → best entry so far
protected PriorityQueue<SPTEntry> fromHeap;   // :41  frontier, min-weight first
```
📌 `core/src/main/java/com/graphhopper/routing/Dijkstra.java:40`–`:41` (được cấp phát trong `initCollections`,
`:52`–`:55`). Một `SPTEntry` là một node trong shortest-path tree — một weight, edge đã dùng để tới nó, và một
con trỏ back-pointer về parent, được làm cho heap sắp xếp được nhờ `compareTo`:

```java
public class SPTEntry implements Comparable<SPTEntry> {
    public int edge; public int adjNode; public double weight; public SPTEntry parent;
    // ...
    public int compareTo(SPTEntry o) { if (weight < o.weight) return -1; ...   // :68
```
📌 `core/src/main/java/com/graphhopper/routing/SPTEntry.java:28`–`:44`,`:67`–`:74`. Trái tim là vòng lặp
chính — poll node rẻ nhất trên frontier, relax các neighbour của nó:

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
📌 `Dijkstra.java:70`–`:107`; nó dừng khi node vừa poll ra chính là target (`finished()` trả về
`currEdge.adjNode == to`, `:109`–`:111`).

> 💡 **Một chi tiết đáng nhặt trong code thật:** GraphHopper **không** làm một decrease-key kiểu sách giáo
> khoa. Khi tìm được một đường rẻ hơn tới một node, nó đánh dấu heap entry cũ là `setDeleted()` rồi chèn một
> cái mới; các entry cũ kỹ (stale) sẽ bị bỏ qua lúc poll (`:73`). Lazy deletion đơn giản hơn và, với một
> binary heap, thường nhanh hơn — một ví dụ đẹp về chuyện code production đi chệch sách giáo khoa vì lý do
> chính đáng.

Và điểm nghẽn mà mọi thứ dồn qua — nơi cái `Weighting` cắm-thay-được thật sự được gọi:

```java
// GHUtility.calcWeightWithTurnWeight(...)
double weight = weighting.calcEdgeWeight(edgeState, reverse);   // :461
// ...+ turn cost via weighting.calcTurnWeight(...)
```
📌 `core/src/main/java/com/graphhopper/util/GHUtility.java:460`–`:469`. **Mọi** thuật toán trong chương này
đều relax edge qua đúng một lời gọi này. Đổi `Weighting` (Chương 4) là khái niệm "ngắn nhất" của mọi thuật
toán đổi theo, mà không cần đụng vào code search.

## 3.4 Case study B — A* and bidirectional

A* là Dijkstra cộng thêm một **heuristic**: một ước lượng lạc quan `h(n)` cho chi phí còn lại tới target,
cộng với chi phí thực đã đi `g(n)`. Frontier được sắp theo `f = g + h`, nên nó nghiêng về phía goal.
Heuristic này cắm-thay-được:

```java
private WeightApproximator weightApprox;   // :48
// default: a beeline (straight-line) estimate
```
📌 `core/src/main/java/com/graphhopper/routing/AStar.java:48`,`:52`–`:59`. Điểm mấu chốt: một `AStarEntry`
mang **hai** weight — heap key `g+h`, và weight *thực* của path `g` dùng khi nó trở thành parent:

```java
// AStarEntry: weightForHeap (g+h)  vs  weightOfVisitedPath (g)
public double getWeightOfVisitedPath() { return weightOfVisitedPath; }   // :186
```
📌 `AStar.java:173`–`:194`. Trong vòng lặp, `g` là chi phí thực, `h` là phần approximation, và tổng của chúng
là thứ sắp thứ tự cho queue:

```java
double tmpWeight = GHUtility.calcWeightWithTurnWeight(weighting, iter, false, currEdge.edge)
                   + currEdge.weightOfVisitedPath;                 // :119  g
double currWeightToGoal = weightApprox.approximate(neighborNode); // :128  h
double estimationFullWeight = tmpWeight + currWeightToGoal;       // :131  f = g + h → heap key
```
📌 `AStar.java:103`–`:148`. Để A* còn **optimal**, `h` không bao giờ được ước lượng vượt (overestimate) — nó
phải là một lower bound *admissible*. Beeline mặc định làm điều đó bằng cách nhân khoảng cách đường thẳng với
weight-trên-mét rẻ nhất có thể:

```java
weight2goal = minWeightPerDistance * dist2goal;   // :70  (minWeightPerDistance from Weighting :35)
```
📌 `core/src/main/java/com/graphhopper/routing/weighting/BeelineWeightApproximator.java:66`–`:72`. Vì con
đường thật chỉ có thể dài hơn và chậm hơn so với đường thẳng đi ở tốc độ tối đa, nên giá trị này chỉ có thể
*thấp hơn* thực tế (underestimate) — nhờ vậy A* không bao giờ vứt nhầm cái true shortest path.

**Bidirectional** search nhân đôi phần lợi. Một lớp base tổng quát chạy hai frontier và ghi nhớ chỗ chúng gặp
nhau:

```java
// two everything: bestWeightMapFrom / bestWeightMapTo, pqOpenSetFrom / pqOpenSetTo, bestWeight
```
📌 `core/src/main/java/com/graphhopper/routing/AbstractBidirAlgo.java:37`–`:50`. Mỗi khi một lần relax edge
rơi vào một node mà search *phía kia* đã chạm tới, nó cập nhật best meeting weight `μ`:

```java
double weight = entry.getWeightOfVisitedPath() + entryOther.getWeightOfVisitedPath();  // :183
if (weight < bestWeight) { bestFwdEntry = ...; bestBwdEntry = ...; bestWeight = weight; }  // :193
```
📌 `AbstractBidirAlgo.java:176`–`:198`. Và nó dừng khi hai đỉnh frontier không còn cơ hội nào thắng được cái
best meeting đó nữa — đúng cái điều kiện dừng bidirectional kinh điển:

```java
return currFrom.weight + currTo.weight >= bestWeight;   // :169
```
📌 `AbstractBidirAlgo.java:165`–`:170`. Bidirectional Dijkstra/A* không-CH đổ đầy cả hai frontier qua
`fillEdgesFrom`/`fillEdgesTo`, lại một lần nữa dẫn edge cost qua `calcWeight` → `calcEdgeWeight`
(`AbstractNonCHBidirAlgo.java:110`–`:198`).

> ⚠️ **Bidirectional A\* rất tinh vi.** Hai heuristic độc lập (mỗi hướng một cái) không *consistent* với
> nhau, nên điều kiện dừng ngây thơ là sai. `AStarBidirection` dùng một approximator **balanced** và thêm một
> `stoppingCriterionOffset` vào `finished()` (`AStarBidirection.java:58`–`:95`, đặc biệt `:77`–`:82`). Chính
> comment ở class của GraphHopper cũng ghi rằng bidirectional A* *kém* hiệu quả hơn bidirectional Dijkstra —
> và đó đúng là lý do vì sao bước tiếp theo không phải là "heuristic tốt hơn" mà là "preprocess cái graph".

## 3.5 Case study C — Contraction Hierarchies

Đây là cú tăng tốc dùng trong production, và nó là một ý tưởng hai pha: **preprocess** graph thành một hệ
phân cấp các "shortcut," rồi chạy một query chỉ leo lên trong hệ phân cấp đó.

**Preprocessing — contract node, thêm shortcut.** Contraction gỡ node từng cái một, rẻ nhất ("ít quan trọng
nhất") trước, và mỗi khi việc gỡ một node làm đứt một shortest path, nó thêm một edge **shortcut** để giữ
path đó lại. Thứ tự contraction là một priority queue có hỗ trợ cập nhật:

```java
// nodes with highest priority come last
private MinHeapWithUpdate sortedNodes;   // :69
```
📌 `core/src/main/java/com/graphhopper/routing/ch/PrepareContractionHierarchies.java:68`–`:69`. Mỗi node nhận
một priority khởi tạo (`updatePrioritiesOfRemainingNodes`, `:201`–`:211`), rồi vòng lặp liên tục poll node
ít-quan-trọng-nhất, kiểm tra lại priority của nó một cách lazy trước khi chốt (priority trở nên cũ kỹ khi các
neighbour bị contract dần):

```java
while (!sortedNodes.isEmpty()) {
    int polledNode = sortedNodes.poll();                 // :264
    if (priority > sortedNodes.peekValue()) { re-push; continue; }  // :266  lazy update
    contractNode(polledNode, level);                     // :279
    // recompute priorities of the contracted node's neighbours   :288–:295
```
📌 `PrepareContractionHierarchies.java:213`–`:313`. Contract một node sẽ gán cho nó một CH **level** rồi
chuyển tiếp cho một `NodeContractor`:

```java
chBuilder.setLevel(node, level);       // :347
nodeContractor.contractNode(node);     // :348
```
📌 `PrepareContractionHierarchies.java:343`–`:351`. Bản thân priority (đại khái) chính là *edge difference* —
thêm node này vào sẽ tạo ra bao nhiêu shortcut so với việc nó gỡ đi bao nhiêu edge:

```java
int edgeDifference = shortcutsCount - prepareGraph.getDegree(node);                 // :108
return params.edgeDifferenceWeight * edgeDifference
     + params.originalEdgesCountWeight * originalEdgesCount;                          // :111
```
📌 `core/src/main/java/com/graphhopper/routing/ch/NodeBasedNodeContractor.java:90`–`:115`. Trước khi thêm một
shortcut, một **witness search** kiểm tra xem đã có sẵn một đường rẻ hơn né được node đó chưa — nếu có thì
khỏi cần shortcut:

```java
double maxWeight = witnessPathSearcher.findUpperBound(toNode, existingDirectWeight, maxVisitedNodes); // :242
if (maxWeight <= existingDirectWeight) continue;   // :245  witness found → skip the shortcut
// else: handler.handleShortcut(...)                :249
```
📌 `NodeBasedNodeContractor.java:209`–`:254`. Một shortcut thật sẽ ghi lại hai edge mà nó bắc cầu, để về sau
một query có thể bung nó trở lại thành đường đi thật:

```java
int shortcut = chBuilder.addShortcutNodeBased(sc.from, sc.to, sc.flags, sc.weight,
                                              sc.skippedEdge1, sc.skippedEdge2);   // :137
```
📌 `NodeBasedNodeContractor.java:131`–`:148`.

**Query — chỉ leo lên.** Một CH query là bidirectional, nhưng có đúng một luật: chỉ đi về phía level
**bằng-hoặc-cao-hơn**. Đúng một bộ lọc đó là thứ khiến nó bỏ qua hàng triệu node cục bộ không quan trọng:

```java
return graph.getLevel(base) <= graph.getLevel(adj);   // :295  upward edges only
```
📌 `core/src/main/java/com/graphhopper/routing/AbstractBidirCHAlgo.java:278`–`:297` (chiều forward dùng
out-explorer, chiều backward dùng in-explorer, `:135`–`:175`; cả hai search đều phải kết thúc,
`:125`–`:133`). Thuật toán query cụ thể thêm **stall-on-demand** — bỏ một node trên frontier nếu đã có một
đường rẻ hơn tới nó qua một edge cao hơn, tránh mở rộng phí công:

```java
// entryIsStallable(...): if a neighbour offers a cheaper route to this node, stall it
```
📌 `core/src/main/java/com/graphhopper/routing/DijkstraBidirectionCH.java:33`–`:68`. Factory chọn nó làm mặc
định (`CHRoutingAlgorithmFactory.java:47`–`:95`, mặc định node-based là `DijkstraBidirectionCH` tại
`:84`–`:89`).

> 🧠 **Mental model:** CH đánh đổi **thời gian preprocessing và bộ nhớ cho shortcut** để lấy **tốc độ
> query**, và nó hy sinh **tính linh hoạt** — weighting bị nướng cứng vào lúc preprocessing, nên bạn không
> thể đổi cost function theo từng request. Chính cú đánh đổi đó là lý do case study tiếp theo tồn tại.

## 3.6 Case study D — Landmarks / ALT

Landmarks (chữ "ALT" = A*, Landmarks, Triangle-inequality) là điểm trung dung: nhanh hơn A* thuần rất nhiều,
nhưng — khác với CH — nó vẫn chạy được khi weighting có thể thay đổi. Nó chỉ đơn giản là A* với một heuristic
*sắc bén*, dựng từ các khoảng cách tính sẵn tới một nhúm node **landmark**.

Bước chuẩn bị chọn ra các landmark rồi lưu, cho mỗi landmark, khoảng cách đi tới và đi từ mọi node:

```java
lms.createLandmarks();   // :118
lms.flush();             // :119
```
📌 `core/src/main/java/com/graphhopper/routing/lm/PrepareLandmarks.java:111`–`:125`. Các landmark được chọn
bằng một heuristic **farthest-point** kiểu greedy (landmark đầu tiên = node xa nhất; mỗi landmark kế = xa nhất
so với tất cả những cái đã chọn), rải chúng ra các góc của graph:

```java
landmarkNodeIdsToReturn[0] = explorer.getLastEntry().adjNode;   // :744  first = farthest node
// each subsequent landmark = farthest from ALL current landmarks
```
📌 `core/src/main/java/com/graphhopper/routing/lm/LandmarkStorage.java:734`–`:760`; các weight from/to được
tính bằng một Dijkstra xuất phát từ mỗi landmark và lưu gọn dưới dạng short 16-bit (`:406`–`:475`, đọc ở
`:525`–`:566`).

Heuristic ở đây chính là **triangle inequality** (bất đẳng thức tam giác). Với bất kỳ landmark `L` nào,
khoảng cách thật `d(v,t)` luôn ít nhất bằng `|d(v,L) − d(t,L)|` — một cận bạn có miễn phí từ các bảng đã lưu,
và là một lower bound chặt hơn beeline *rất* nhiều:

```java
int rhs1Int = lms.getToWeight(activeLandmarkIndices[i], v)   - weightsFromTToActiveLandmarks[i];   // :170
int rhs2Int = weightsFromActiveLandmarksToT[i] - lms.getFromWeight(activeLandmarkIndices[i], v);   // :171
// ...
return Math.max(rhs1Int, rhs2Int);   // :177  best bound over the two directions
```
📌 `core/src/main/java/com/graphhopper/routing/lm/LMApproximator.java:139`–`:178`; `approximate()` lấy
landmark active tốt nhất và lùi về beeline khi cần, giữ lấy cận nào *lớn hơn* (cả hai đều admissible, nên cận
lớn hơn là chặt hơn):

```java
return Math.max(lmApproximation, beelineApproximation.approximate(v));   // :126
```
📌 `LMApproximator.java:94`–`:137`. Vì `LMApproximator implements WeightApproximator` (`:34`), nó cắm thẳng
vào *đúng* bộ máy A* ở §3.4 — Landmarks đúng nghĩa đen là "A* với một `h` tốt hơn."

## 3.7 Ghép lại — ai chọn cái nào

`Router` là nơi đưa ra quyết định, hoàn toàn dựa trên thứ đã được chuẩn bị lúc import:

```java
if (chEnabled && !disableCH)        return createCHSolver(...);    // :193  fastest, fixed weighting
else if (lmEnabled && !disableLM)   return createLMSolver(...);    // :195  fast, flexible weighting
else                                return createFlexSolver(...);  // :197  plain Dijkstra/A*, fully flexible
```
📌 `core/src/main/java/com/graphhopper/routing/Router.java:190`–`:200` (`chEnabled`/`lmEnabled` = "đã build CH
graph / landmark chưa?", `:88`–`:89`). Đường flexible phân giải một string thành một thuật toán cụ thể:

```java
case DIJKSTRA_BI: return new DijkstraBidirectionRef(...);   // :44
case ASTAR_BI:    return new AStarBidirection(...);         // :49  (the default)
```
📌 `core/src/main/java/com/graphhopper/routing/RoutingAlgorithmFactorySimple.java:40`–`:60`. Thế nên cùng một
interface `RoutingAlgorithm` (`calcPath`, `getVisitedNodes`, `RoutingAlgorithm.java:28`) được thoả mãn bởi
Dijkstra thuần, A*, một CH query, hay một A* dẫn-đường-bằng-LM — và toàn bộ khác biệt về tốc độ chỉ là *mỗi
cái thăm bao nhiêu phần của graph* để trả về đúng cùng một optimal path.

## 3.8 Lab 3 — Dijkstra vs A* vs CH

> 🧪 **Lab 3.** Chỉ đọc. Mục tiêu: thấy, gói trong đúng một con số — số node đã thăm — vì sao cả họ thuật
> toán này tồn tại. Ghi vào [`labs/lab03-algorithms.md`](labs/lab03-algorithms.md).

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

**Kết quả kỳ vọng:** `GHUtility.java:461` đọc ra `weighting.calcEdgeWeight(edgeState, reverse)`;
`AbstractBidirCHAlgo.java:295` chính là bộ lọc đi-lên `getLevel(base) <= getLevel(adj)`; request CH trả về
trong một phần nhỏ thời gian của request flexible — **cùng** một khoảng cách, ít việc hơn nhiều. (Muốn tắt CH
thì server phải cho phép `ch.disable`; nếu không thì so với một build có `profiles_ch: []`.)

## 3.9 Checkpoint

1. Mọi thuật toán ở đây đều gọi cùng một method để định giá một edge. Method nào, trong file nào, và vì sao
   điều đó khiến `Weighting` thay-đổi-được mà không cần đụng vào code search?
2. Dijkstra của GraphHopper không làm decrease-key. Vậy nó làm gì thay thế, và một stale entry bị bỏ qua ở
   đâu?
3. Trong A*, một `AStarEntry` giữ hai weight. Đó là những weight nào, cái nào sắp thứ tự cho heap còn cái nào
   trở thành path cost của parent? Vì sao heuristic bắt buộc phải ước lượng thấp hơn thực tế?
4. Contraction Hierarchies tính sẵn (precompute) những gì, *query* của nó thực thi đúng một luật nào, và nó
   hy sinh gì để có tốc độ đó?
5. Landmarks là "A* với một `h` tốt hơn." Cái `h` đó đến từ đâu, và vì sao `|d(v,L) − d(t,L)|` là một lower
   bound hợp lệ?
6. Với một request, `Router` chọn CH, LM, hay flexible. Cái gì quyết định, và khi nào thì mỗi cái là đúng?

> Nếu #4 còn lung lay, đọc lại §3.5. Nếu #3 hoặc #5 còn lung lay, đọc lại §3.4 và §3.6 cùng nhau — chúng là
> cùng một bộ máy A* với các heuristic khác nhau.

## 🔌 Connect to your past (ETA, dispatch & the matrix)

Chương này chính là lý do GraphHopper là engine đúng để nghiên cứu cho công việc của *bạn*. Một backend gọi
xe sống chết bằng các shortest-path query: ETA của khách là một `route`; "trong 30 tài xế gần đây, ai gần
nhất tính theo đường đi" là một **matrix** các shortest path (`/matrix`/SPT ở Chương 7), chạy mỗi lần điều
phối. Giờ bạn đã biết các cần gạt. Nếu những query đó cần tôn trọng điều kiện thời gian thực — một cost theo
từng request thay đổi theo traffic hay loại xe — bạn *không thể* dùng CH (weighting của nó bị đóng băng lúc
import); bạn sẽ muốn **Landmarks**, đường linh-hoạt-mà-vẫn-nhanh ở §3.6. Nếu cost function cố định, cú tăng
tốc ~1000× của CH là tiền chùa. Và với VinBus/BusMap, chính điểm nghẽn `Weighting` (§3.3) là nơi một luật "xe
buýt né phố này" sẽ cắm vào — một method, mọi thuật toán đều tôn trọng nó. Họ thuật toán này không phải chuyện
hàn lâm; nó là thực đơn mà bạn gọi món ETA từ đó.

**Next:** bạn đã thấy search chạy *thế nào*. Giờ tới nửa còn lại — cách bạn *định hình* nghĩa của "ngắn
nhất": profiles, custom models, và các encoded value mà `Weighting` đọc.
→ **[Chapter 04 — Profiles, Weighting & Custom Models](04-profiles-weighting-custom-models.md)**
