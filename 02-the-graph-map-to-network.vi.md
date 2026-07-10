# Chapter 02 — The Graph: turning a map into a routable network

> **Goal:** Hiểu cái nền mà mọi thuật toán routing đi bộ trên đó. Sau chương này bạn giải thích được cách
> `OSMReader` biến một file `.osm.pbf` thành một `BaseGraph` gồm các node và edge đánh địa chỉ bằng số nguyên,
> cách một `EdgeExplorer` quét qua các neighbour của một node, cách toàn bộ thứ này nằm trong các mảng phẳng
> `DataAccess` (trên RAM hoặc memory-mapped), geometry của một edge được giữ ở đâu, và turn restriction gắn
> vào graph ra sao. Pinned to **`11.0`** (`69e50f6`).

## 2.1 Vì sao quan trọng

Một thuật toán chỉ tốt ngang cái graph nó chạy trên đó. Dijkstra và Contraction Hierarchies ở Chương 3 ngắn
gọn và thanh lịch chính là nhờ cái graph bên dưới *nhanh*: không cấp phát object cho mỗi node, không tra
hash-map cho mỗi edge, chỉ có id số nguyên và byte offset. Muốn đọc các thuật toán mà không rối, trước hết
bạn phải thôi hình dung `class Node { List<Edge> edges; }` và bắt đầu hình dung **các mảng**.

Đây cũng là lớp mà bản thân tấm bản đồ sống. Khi BusMap đặt một trạm hay vẽ một con đường, thì trạm đó là
một **node** còn con đường đó là một chuỗi **edge** đúng trong cấu trúc này. Hiểu nó là hiểu "tấm bản đồ"
*thực sự là gì*, một cách cụ thể, dưới mắt một routing engine.

## 2.2 Mental model: node và edge là những mảng phẳng

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

Ý tưởng cốt lõi: một node là một `int` đánh chỉ mục vào một mảng node; một edge là một `int` đánh chỉ mục vào
một mảng edge. Mỗi bản ghi edge lưu hai đầu mút của nó **cùng một con trỏ tới edge kế tiếp của từng đầu mút** —
một linked list các edge cho mỗi node, luồn xuyên qua chính cái mảng phẳng đó. Đó là cách bạn liệt kê được các
neighbour của một node mà không cần một `List` riêng cho từng node.

## 2.3 OSM → graph: `OSMReader`

Việc import do `OSMReader` điều khiển:

```java
public class OSMReader {
```
📌 `core/src/main/java/com/graphhopper/reader/osm/OSMReader.java:75`. Cái façade nối dây nó lại lúc import
(`GraphHopper.java:952`–`:961`, bên trong `importOSM()` ở `:931`) và gọi `readGraph()`, hàm này chạy một
pass parse hai lượt trên file PBF:

```java
public void readGraph() throws IOException {
    // ...
    WaySegmentParser waySegmentParser = new WaySegmentParser.Builder(baseGraph.getNodeAccess(), ...)
            .setWayFilter(this::acceptWay)
            // ...
            .setEdgeHandler(this::addEdge)     // ← the hinge
```
📌 `OSMReader.java:152`–`:172`. Lượt thứ nhất tìm xem OSM node nào là **junction** (được tham chiếu bởi nhiều
hơn một way); lượt thứ hai đi qua từng way được chấp nhận và, tại mỗi junction, gọi edge handler. Cái handler
đó chính là nơi một đoạn đường trở thành một edge của graph:

```java
protected void addEdge(int fromIndex, int toIndex, PointList pointList, ReaderWay way, ...) {
```
📌 `OSMReader.java:318` (đơn giản hoá geometry và độ cao xảy ra ở `:332`–`:347`). Một OSM way kiểu như
"Hauptstraße" trở thành *nhiều* edge — mỗi đoạn junction-tới-junction một edge — mỗi cái giữ lại các điểm
trung gian làm geometry.

> 🧠 **Mental model:** một **edge** routing không phải là một OSM way. Nó là một *đoạn của way nằm giữa hai
> junction*. Những chỗ đường cong giữa hai junction đó là geometry (một `PointList`), không phải node phụ.
> Cách này giữ cho graph nhỏ (ít node) mà vẫn bảo toàn hình dạng để vẽ và tính khoảng cách.

## 2.4 `BaseGraph`: tạo một edge

`BaseGraph` là cái kho:

```java
public class BaseGraph implements Graph, Closeable {
```
📌 `core/src/main/java/com/graphhopper/storage/BaseGraph.java:49`. Rốt cuộc `addEdge` gọi tới:

```java
public EdgeIteratorState edge(int nodeA, int nodeB) {
    if (isFrozen())
        throw new IllegalStateException("Cannot create edge if graph is already frozen");
    // ...
    int edgeId = store.edge(nodeA, nodeB);
    EdgeIteratorStateImpl edge = new EdgeIteratorStateImpl(this);
    boolean valid = edge.init(edgeId, nodeB);
```
📌 `BaseGraph.java:291`–`:307`. Để ý `isFrozen()`: khi import xong và quá trình chuẩn bị CH/LM bắt đầu, graph
bị **frozen** — không thêm base edge mới nữa, chỉ có shortcut (Chương 3). Toạ độ node đi qua `getNodeAccess()`
(`:156`); việc lặp edge đi qua `createEdgeExplorer(...)` (`:410`–`:412`); turn cost đi qua
`getTurnCostStorage()` (`:425`–`:427`).

Bản thân toạ độ sống trong `NodeAccess` (một `PointAccess`):

```java
public interface NodeAccess extends PointAccess
```
📌 `core/src/main/java/com/graphhopper/storage/NodeAccess.java:30`; toạ độ qua `PointAccess.setNode(...)`
(`:50`), `getLat(int)` (`:55`), `getLon(int)` (`:60`). *Hình dạng* của một edge giữa hai đầu mút của nó là một
`PointList`:

```java
public class PointList implements Iterable<GHPoint3D>, PointAccess {
```
📌 `web-api/src/main/java/com/graphhopper/util/PointList.java:40` (`add(lat, lon)` ở `:199`).

## 2.5 Quét các edge của một node: idiom cursor

Bạn không bao giờ nhận được một `List<Edge>`. Bạn nhận được một **cursor** tiến dần qua linked list các edge:

```java
public interface EdgeExplorer {
    EdgeIterator setBaseNode(int baseNode);
```
📌 `core/src/main/java/com/graphhopper/util/EdgeExplorer.java:29`,`:37`. Cái iterator trả về *bản thân nó*
là một khung nhìn edge, bị mutate tại chỗ khi bạn tiến tới:

```java
public interface EdgeIterator extends EdgeIteratorState {
    boolean next();
```
📌 `core/src/main/java/com/graphhopper/util/EdgeIterator.java:41`,`:60`. Nên vòng lặp đọc như sau:

```java
EdgeExplorer explorer = graph.createEdgeExplorer();
EdgeIterator iter = explorer.setBaseNode(node);
while (iter.next()) {
    int adj  = iter.getAdjNode();     // the neighbour
    double d = iter.getDistance();    // edge length in metres
    int edge = iter.getEdge();        // the edge id
}
```
Những accessor đó thuộc `EdgeIteratorState` — interface đọc cho một edge: `getEdge()` (`:104`),
`getBaseNode()` (`:127`), `getAdjNode()` (`:133`), `fetchWayGeometry(FetchMode)` (`:145`), `getDistance()`
(`:158`). 📌 `core/src/main/java/com/graphhopper/util/EdgeIteratorState.java:42`.

> ⚠️ Cái iterator là một **flyweight**: `iter` không nắm giữ một edge, nó *là* một cửa sổ di chuyển. Đừng cất
> một reference tới nó rồi mong nó đứng yên — hãy đọc các field bạn cần ở từng vòng lặp. Đây là footgun kinh
> điển khi bạn lần đầu viết code đi bộ trên graph với GraphHopper.

## 2.6 Storage: RAM vs memory-mapped

Tất cả những thứ ở trên — mảng node, mảng edge, geometry — là byte nằm sau một `DataAccess` (§0.6). Có hai
backing:

```java
public class RAMDataAccess extends AbstractDataAccess {
    private byte[][] segments = new byte[0][];     // on-heap
```
📌 `core/src/main/java/com/graphhopper/storage/RAMDataAccess.java:35`–`:36` (mặc định). Hoặc memory-mapped, để
một graph cỡ cả một quốc gia không bao giờ vào hẳn trong JVM heap:

```java
buf = raFile.getChannel().map(
        allowWrites ? FileChannel.MapMode.READ_WRITE : FileChannel.MapMode.READ_ONLY, offset, byteCount);
```
📌 `core/src/main/java/com/graphhopper/storage/MMapDataAccess.java:163`–`:164` (class ở `:49`). Đây chính là
cái núm cho phép cùng một đoạn code phục vụ Andorra trên một laptop và cả một lục địa trên một server.

## 2.7 Turn restriction sống trên graph

"Cấm rẽ trái ở đây" không phải là thuộc tính của một con đường — nó là thuộc tính của một bộ ba *(fromEdge,
viaNode, toEdge)*. GraphHopper lưu đúng như thế:

```java
public class TurnCostStorage {
    // set(BooleanEncodedValue bev, int fromEdge, int viaNode, int toEdge, boolean value)   :90
    // set(DecimalEncodedValue turnCostEnc, int fromEdge, int viaNode, int toEdge, double)   :100
```
📌 `core/src/main/java/com/graphhopper/storage/TurnCostStorage.java:39`. Một restriction là một turn cost vô
cực; một cost là một penalty hữu hạn (tính bằng giây). Via-node liên kết ngược qua
`getNodeAccess().setTurnCostIndex(viaNode, index)` (`:114`). Chương 3 chỉ ra nơi các thuật toán cộng cái turn
weight này (spoiler: qua đúng một lời gọi `GHUtility` dùng chung).

## 2.8 Lab 2 — đọc graph

> 🧪 **Lab 2.** Chỉ đọc. Mục tiêu: đo kích thước graph bạn đã import và quét các edge của một node. Ghi vào
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

Rồi suy luận về các con số: với một mạng lưới đường bộ, edge ≈ 1.1–1.3 × node, nên bậc trung bình (edge·2 /
node) khá nhỏ — **~2–3**. Cái bậc thấp đó *chính là lý do* graph search nhanh: mỗi node đã settle chỉ relax
một dúm neighbour.

**Expected:** `BaseGraph.java:291` đọc ra `public EdgeIteratorState edge(int nodeA, int nodeB)`;
`EdgeExplorer.java:37` đọc ra `EdgeIterator setBaseNode(int baseNode);`; và log import báo số lượng node/edge
với tỉ lệ gần bằng 1. Ghi lại các con số và bậc trung bình.

## 2.9 Checkpoint

1. Một node và một edge đều là một `int`. Graph liệt kê các neighbour của một node *mà không* cần một `List`
   riêng cho mỗi node bằng cách nào?
2. Một OSM way "Hauptstraße" trở thành vài edge routing. Cái gì chẻ nó ra, và các chỗ cong của con đường đi
   đâu nếu không vào node?
3. `isFrozen()` bảo vệ chống lại điều gì, và pha nào về sau cần graph ở trạng thái frozen?
4. Khi nào bạn sẽ chọn `MMapDataAccess` thay vì `RAMDataAccess`, và dòng nào thực sự làm việc mapping?
5. Một luật "cấm rẽ trái" được lưu theo bộ ba nào, trong class nào?

> Nếu #1 còn lung lay, đọc lại §2.2 và §2.5. Nếu #3 còn lung lay, cứ giữ lấy — Chương 3 §3.4 sẽ trả cả vốn lẫn lãi.

## 🔌 Connect to your past (a transit map *is* a graph)

Thế giới của BusMap ánh xạ thẳng vào cấu trúc này. Một **trạm** là một node; một **đoạn tuyến** giữa hai trạm
là một edge; hình dạng con đường mà xe buýt đi theo giữa chúng là geometry `PointList` của edge; "xe buýt
không rẽ được ở đây" là một entry trong `TurnCostStorage`. Khi Chương 5 dựng một graph *transit* từ GTFS, nó
tái dùng đúng bộ máy này — trạm và platform trở thành node, boarding/riding/alighting trở thành edge — chỉ là
có thêm thời gian gấp vào. Còn với ride-hailing, đây là mạng lưới mà một GPS trace của tài xế được map-match
lên trong Chương 6: map-matching là "chuỗi *các edge này* nào là chuỗi mà tài xế thực sự đã đi?". Mọi chương
về sau đều là một thuật toán đi bộ trên chính những mảng bạn vừa gặp.

**Next:** graph đã được dựng và frozen. Giờ là màn chính — các thuật toán tìm đường ngắn nhất băng qua nó. →
**[Chapter 03 — The Shortest-Path Algorithm Family](03-shortest-path-algorithms.md)**
