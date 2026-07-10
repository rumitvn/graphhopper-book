# Chapter 05 — Public Transit: GTFS & RAPTOR

> **Goal:** Hiểu cách GraphHopper lập kế hoạch cho một hành trình bus/tàu. Sau chương này bạn giải thích được
> cách `GtfsReader` biến một GTFS feed thành một `PtGraph` **time-expanded** (một node cho mỗi stop-time, edge
> cho việc boarding, riding, dwelling, transfer), cách `MultiCriteriaLabelSetting` chạy một tìm kiếm đa tiêu
> chí **kiểu RAPTOR** trên đó (thời điểm đến vs số transfer vs quãng đi bộ), và cách GTFS-realtime gấp các delay
> trực tiếp trở lại vào. Pinned tới **`11.0`** (`69e50f6`). Đây là chương BusMap / VinBus.

## 5.1 Vì sao quan trọng

Định tuyến đường bộ có đúng một cost và không có đồng hồ: một edge luôn ở đó và luôn cùng độ dài. Transit thì
ngược lại — bạn chỉ lên được một chuyến bus *khi nó khởi hành*, một tuyến "nhanh hơn" với ba transfer có thể tệ
hơn một tuyến đi thẳng chậm hơn, và "ngắn nhất" thực sự là đa chiều. RAPTOR (Round-bAsed Public Transit
Optimized Router) cùng những họ hàng label-setting của nó tồn tại chính là vì Dijkstra-trên-khoảng-cách không
diễn đạt nổi "đi trễ hơn, đến sớm hơn, nhưng chỉ khi bạn không ngại đổi tuyến hai lần."

Đây là chương ánh xạ thẳng vào công việc hằng ngày của bạn. Journey planner của BusMap và tính năng "chuyến bus
kế tiếp là khi nào, và khi nào tôi tới nơi" của VinBus chính xác là phép tính này. Đến cuối chương bạn sẽ nhận
ra chính sản phẩm của mình trong `MultiCriteriaLabelSetting`.

## 5.2 Mental model: gấp thời gian vào graph

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

Mẹo mấu chốt là **time expansion**: thay vì một node cho mỗi stop, ta có một node cho mỗi *sự kiện* (chuyến này
khởi hành A lúc 09:00; chuyến này tới B lúc 09:10). Đi trên một phương tiện là một edge `HOP` với trọng số là số
phút theo lịch; boarding và alighting là các edge `BOARD`/`ALIGHT` nối timeline khởi hành của một stop vào trip;
chờ tại một stop là một edge `WAIT` dọc theo timeline. Vì thời điểm đến đã được nướng sẵn vào node, một phép tìm
kiếm graph thông thường trên cấu trúc này tự động tôn trọng lịch trình.

## 5.3 GTFS → `PtGraph`

Quá trình build gồm ba bước:

```java
void buildPtNetwork() {
    createTrips();
    wireUpStops();
    insertGtfsTransfers();
}
```
📌 `reader-gtfs/src/main/java/com/graphhopper/gtfs/GtfsReader.java:118`–`:122`. `createTrips` duyệt qua
stop-times của từng trip và đặt xuống các edge theo từng trip — đây chính là việc dựng đúng nghĩa đen sơ đồ ở
trên:

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
📌 `GtfsReader.java:263`–`:292`. `wireUpStops` nối mỗi stop vào street network bằng một edge `ENTER_PT` và dựng
timeline chờ (`:306`–`:311`), nhờ vậy một hành khách có thể *đi bộ* tới một stop (road graph, Chương 2–3) rồi
*lên xe* (transit graph). Tất cả rơi vào cùng một store time-expanded:

```java
public class PtGraph implements GtfsReader.PtGraphOut {
    public int addEdge(int nodeA, int nodeB, long attrPointer) {   // :120
```
📌 `reader-gtfs/src/main/java/com/graphhopper/gtfs/PtGraph.java:32`,`:120` — cùng triết lý flat-array, dựa trên
`DataAccess` như `BaseGraph` của đường bộ (§2.6), với một linked list edge cho mỗi node.

## 5.4 Bộ từ vựng edge

Mọi chuyển động transit đều là một trong một enum nhỏ các edge type — đáng đọc một lần, vì một hành trình chẳng
qua là một path xen kẽ giữa chúng:

```java
public enum EdgeType {
    HIGHWAY, ENTER_TIME_EXPANDED_NETWORK, LEAVE_TIME_EXPANDED_NETWORK,
    ENTER_PT, EXIT_PT, HOP, DWELL, BOARD, ALIGHT, OVERNIGHT, TRANSFER, WAIT, WAIT_ARRIVAL
}
```
📌 `reader-gtfs/src/main/java/com/graphhopper/gtfs/GtfsStorage.java:173`–`:175`. Một trip điển hình đọc thành:
`ENTER_PT` (đi bộ vào) → `WAIT` (chờ tới chuyến bus của bạn) → `BOARD` → `HOP…HOP` (đi xe, có `DWELL` ở các stop
trung gian) → `ALIGHT` → `TRANSFER` (sang một tuyến khác) → … → `EXIT_PT` (đi bộ ra). Đếm các edge
`BOARD`/`TRANSFER` trên một path *chính là* đếm số transfer — một trong những tiêu chí mà phép tìm kiếm cực tiểu
hoá.

## 5.5 Tìm kiếm đa tiêu chí kiểu RAPTOR

Vì "tốt nhất" là đa chiều, GraphHopper không giữ *một* label tốt nhất cho mỗi node — nó giữ một **Pareto set**
các label không bị áp đảo. Một `Label` là state: thời điểm đến, số transfer, tổng thời gian đi bộ tích luỹ, và
một back-pointer:

```java
public final long currentTime;      // :43  arrival-time criterion
public final int  nTransfers;       // :48  #transfers criterion
public final long streetTime;       // :51  walking-time criterion
public final Label parent;          // :58  path reconstruction
```
📌 `reader-gtfs/src/main/java/com/graphhopper/gtfs/Label.java:23`,`:43`–`:58`. Phép tìm kiếm là một thuật toán
label-setting với một priority queue, mỗi lần pop ra một label, rồi khám phá các neighbour của nó:

```java
public class MultiCriteriaLabelSetting {
    private final PriorityQueue<Label> fromHeap;   // :62
    // main loop:
    Label label = fromHeap.poll();                                        // :95 (after skipping deleted)
    action.accept(label);
    for (GraphExplorer.MultiModalEdge edge : explorer.exploreEdgesAround(label))  // :103
```
📌 `reader-gtfs/src/main/java/com/graphhopper/gtfs/MultiCriteriaLabelSetting.java:35`,`:66`–`:105`. Trái tim của
nó là **domination** — một label chỉ được giữ lại nếu không có label nào đang tồn tại thắng nó trên *mọi* tiêu
chí:

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
📌 `MultiCriteriaLabelSetting.java:225`–`:240`. Label mới chỉ được chèn vào nếu không bị áp đảo, và chúng tỉa đi
bất kỳ label nào đang tồn tại mà chúng áp đảo (`insertIfNotDominated`/`removeDominated`, `:184`–`:223`). Scalar
`weight` gộp các tiêu chí lại bằng những beta chỉnh được — một transfer hay một phút đi bộ "đáng" bao nhiêu
giây:

```java
long weight(Label label) {
    return timeSinceStartTime(label)
         + (long)(label.nTransfers * betaTransfers)
         + (long)(label.streetTime * (betaStreetTime - 1.0)) + label.extraWeight;   // :243
}
```
📌 `MultiCriteriaLabelSetting.java:242`–`:244`.

> 🧠 **Mental model:** Dijkstra đường bộ giữ *một* entry tốt nhất cho mỗi node (§3.3); transit giữ *một tập* các
> label Pareto-tối ưu cho mỗi node. "Đến lúc 09:40 với 0 transfer" và "đến lúc 09:32 với 2 transfer" *cả hai*
> đều có thể là đáp án — không cái nào áp đảo cái kia — nên cả hai cùng sống sót, và hành khách (hoặc UI) chọn.

## 5.6 Router và realtime

`PtRouterImpl` nối phép tìm kiếm với một request và điều khiển vòng lặp tìm lời giải:

```java
public final class PtRouterImpl implements PtRouter {           // :50
    public GHResponse route(Request request) {                  // :78
        return new RequestHandler(request).route();
    // ...builds the label-setting search:
    router = new MultiCriteriaLabelSetting(graphExplorer, arriveBy, !ignoreTransfers, ...);  // :240
    for (Label label : router.calcLabels(startNode, initialTime)) { ... }                    // :259
```
📌 `reader-gtfs/src/main/java/com/graphhopper/gtfs/PtRouterImpl.java:50`,`:78`,`:240`,`:259` (tái dựng path qua
`findPaths`, `:195`). Các delay trực tiếp tới dưới dạng protobuf **GTFS-realtime** và được gấp vào mà không cần
dựng lại graph — một `RealtimeFeed` giữ các edge bị chặn cùng các map delay theo từng edge để phép tìm kiếm tra
cứu:

```java
public class RealtimeFeed {
    private final IntHashSet blockedEdges;                 // :50  cancelled trips/stops
    private final IntLongHashMap delaysForBoardEdges;      // :51
    private final IntLongHashMap delaysForAlightEdges;     // :52
    // ...
    public static RealtimeFeed fromProtobuf(GtfsStorage staticGtfs, ..., feedMessages) {   // :73
```
📌 `reader-gtfs/src/main/java/com/graphhopper/gtfs/RealtimeFeed.java:48`–`:73`. Graph lịch trình tĩnh vẫn nằm
nguyên; realtime là một *overlay* gồm các delay và các đoạn chặn mà phép tìm kiếm label đọc dần khi chạy.

> 💡 GraphHopper 11 còn kèm theo một transit router **trip-based** mới hơn (`PtRouterTripBasedImpl` +
> `TripBasedRouter`) song song với cái schedule/label-setting này. Router label-setting đọc ở đây là dễ khai
> sáng nhất — nó làm ý tưởng đa tiêu chí trở nên tường minh — nên đây là cái cuốn sách này dạy.

## 5.7 Lab 5 — lập một hành trình

> 🧪 **Lab 5.** Lab chạy server (import một GTFS feed). Mục tiêu: chạy một query `pt` rồi đọc các leg và transfer
> của nó. Ghi vào [`labs/lab05-transit.md`](labs/lab05-transit.md).

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

**Kỳ vọng:** `GtfsStorage.java:174` liệt kê `HOP, DWELL, BOARD, ALIGHT, … TRANSFER, WAIT`;
`MultiCriteriaLabelSetting.java:225` là `private boolean dominates(...)`; và query `pt` trả về một path với
`legs` xen kẽ đi bộ và `pt`, một thời gian di chuyển, cùng một số transfer đã được RAPTOR cực tiểu hoá. (Bạn tự
cung cấp một GTFS feed nhỏ và bật một profile `pt` — lab note liệt kê các config key.)

## 5.8 Checkpoint

1. Vì sao transit graph lại "time-expanded"? Một *node* ở đây là gì, so với một node trong road graph?
2. Kể tên các edge type mà một chuyến bus trip đơn lẻ chạm vào, từ lúc đi bộ vào tới lúc đi bộ ra. Cái nào được
   tính là một transfer?
3. Dijkstra đường bộ giữ một label tốt nhất cho mỗi node; phép tìm kiếm transit giữ hẳn một *tập*. Vì sao — và
   "dominates" nghĩa là gì?
4. Hai đáp án cùng sống sót: "09:40, 0 transfer" và "09:32, 2 transfer." Cái nào đúng, và engine quyết định trả
   về cái nào bằng cách nào?
5. Một chuyến bus đang trễ 5 phút. Thông tin đó tới được phép tìm kiếm *mà không* cần dựng lại graph bằng cách
   nào?

> Nếu #1 còn lung lay, đọc lại §5.2. Nếu #3 còn lung lay, đọc lại §5.5.

## 🔌 Connect to your past (this is BusMap's engine)

Bạn đã xây chính sản phẩm này. Cái "từ đây tới kia bằng bus" của BusMap là `PtRouterImpl.route`; cái "đổi 2 lần,
đi bộ 7 phút, đến 08:41" mà UI của bạn hiển thị là `nTransfers` / `streetTime` / `currentTime` của một `Label`;
cái tuỳ chọn nơi người dùng nói "ít transfer thôi, tôi không ngại đi bộ" chính là `betaTransfers` vs
`betaStreetTime` trong hàm `weight` (§5.5). ETA trực tiếp của VinBus — "xe của bạn trễ 4 phút, giờ bạn sẽ đến
lúc 08:45" — đúng là cái overlay GTFS-realtime trong `RealtimeFeed`: graph lịch trình tĩnh không đổi, một map
delay đắp lên trên. Mọi thứ bạn từng tự tay dựng cho một app transit — sự đánh đổi đa tiêu chí, cách ghép
đi-bộ+đi-xe, miếng vá realtime — đều nằm ở đây trong một module đọc-được duy nhất. Đọc `MultiCriteriaLabelSetting`
một lần và bạn sẽ không bao giờ nhìn journey planner của mình như cũ nữa.

**Next:** cả định tuyến đường bộ lẫn transit đều giả định rằng bạn *biết* mình đang ở đâu trên bản đồ. Nhưng một
phương tiện đang di chuyển chỉ có GPS nhiễu. Chương 6 kéo nó khớp trở lại lên các con đường.
→ **[Chapter 06 — Map-Matching](06-map-matching.md)**
