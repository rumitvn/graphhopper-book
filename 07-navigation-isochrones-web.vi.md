# Chapter 07 — Navigation, Isochrones & the Web/Tiles Surface

> **Goal:** Thấy engine vươn tới được app bằng cách nào. Sau chương này bạn giải thích được
> `InstructionsFromEdges` biến một chuỗi edge thô thành các `Instruction` turn-by-turn (kèm sign code) ra
> sao, cặp value object `ResponsePath` + `PathDetail` mang một route tới client thế nào, và mỗi endpoint
> trong họ HTTP endpoint — `/route`, `/isochrone`, `/nearest`, `/mvt` — làm gì. Pinned tới **`11.0`** (`69e50f6`).

## 7.1 Vì sao quan trọng

Các Chương 3–6 đã sản xuất ra *path* — những chuỗi edge kèm tổng distance và time. Nhưng tài xế đâu cần một
danh sách edge; họ cần "Còn 200 m nữa, rẽ trái vào Hauptstraße." Một hệ dispatch không cần một polyline; nó
cần một JSON envelope gồm distance, duration, và có thể là các road class dọc đường. Một map UI thì cần
vector tile để render. Chương này chính là tầng **shape** từ Chương 1 — bước biến đổi cuối cùng, từ "đáp án
của thuật toán" thành "thứ mà sản phẩm tiêu thụ."

Với bạn, đây chính là bề mặt mà các app của bạn vốn đã nói chuyện cùng. Mọi thứ ở đây là phía bên kia của
những HTTP call mà BusMap, VinBus, và một backend gọi xe thực hiện mỗi ngày.

## 7.2 Mental model: từ edges tới một câu trả lời đã render

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

Hai object gánh phần lớn công việc: `InstructionList` (các bước turn-by-turn) và `ResponsePath` (trọn câu
trả lời). Các endpoint chỉ là những lớp bọc mỏng: gọi engine rồi serialize một trong hai object này.

## 7.3 Turn instruction từ edges

Biến một path thành instruction nghĩa là đi dọc từng edge của nó và, tại mỗi junction, quyết định "con đường
có bẻ góc đủ nhiều, hay tên đường có đổi, để đáng phải báo cho tài xế điều gì đó không?" Đó là việc của
`InstructionsFromEdges`, một edge visitor:

```java
public class InstructionsFromEdges implements Path.EdgeVisitor {              // :36
    public static InstructionList calcInstructions(Path path, Graph graph, Weighting weighting,
                                                   EncodedValueLookup evLookup, Translation tr) {  // :111
        final InstructionList ways = new InstructionList(tr);
        // ...
        ways.add(new FinishInstruction(graph.getNodeAccess(), path.getEndNode()));   // :115
```
📌 `core/src/main/java/com/graphhopper/routing/InstructionsFromEdges.java:36`,`:111`–`:118`. Bước đầu tiên
luôn là một `CONTINUE_ON_STREET`; mỗi junction tiếp theo nhận một **sign** được tính từ geometry:

```java
int sign = Instruction.CONTINUE_ON_STREET;                                    // :160  (first instruction)
// ...at each junction:
int sign = getTurn(edge, baseNode, prevNode, adjNode, name, ...);             // :257
// getTurn → InstructionsHelper.calculateSign(prevLat, prevLon, lat, lon, prevOrientation)  // :362
```
📌 `InstructionsFromEdges.java:158`–`:161`,`:256`–`:257`,`:355`–`:362`. Cái sign là một mã integer mà client
render thành một mũi tên:

```java
public static final int TURN_LEFT        = -2;   // :32
public static final int CONTINUE_ON_STREET = 0;  // :34
public static final int TURN_RIGHT       = 2;    // :36
public static final int FINISH           = 4;    // :38
public static final int USE_ROUNDABOUT   = 6;    // :40
public static final int PT_START_TRIP    = 101;  // :47  (transit instructions, Chapter 5)
```
📌 `web-api/src/main/java/com/graphhopper/util/Instruction.java:28`–`:47`. Góc càng gắt thì magnitude càng
lớn (`SHARP_LEFT`/`SHARP_RIGHT`), và *dấu* của sign chính là hướng tay — âm là trái, dương là phải. Để ý các
mã `PT_*`: các hành trình transit (Chương 5) tái dùng đúng bộ máy instruction này.

## 7.4 Response model

Một route rời khỏi engine dưới dạng một `ResponsePath`:

```java
public class ResponsePath {                                   // :34
    private InstructionList instructions;                     // :43
    private Map<String, List<PathDetail>> pathDetails;        // :50
    public PointList getPoints() { ... }                      // :99   geometry
    public double getDistance() { ... }                       // :148  metres
    public long getTime() { ... }                             // :197  milliseconds
    public InstructionList getInstructions() { ... }          // :246
```
📌 `web-api/src/main/java/com/graphhopper/ResponsePath.java:34`–`:246`. Ngoài distance/time/geometry/turn,
nó còn mang theo **path detail** — những giá trị được gắn nhãn theo từng khoảng dọc route ("edge 0–5 là
`road_class=primary`, 6–9 là `residential`"):

```java
public class PathDetail {                 // :25
    private final Object value;           // :26   e.g. "primary", or a speed
    // first / last point index the value spans
    public Object getValue() { ... }      // :37
```
📌 `web-api/src/main/java/com/graphhopper/util/details/PathDetail.java:25`–`:37`. Toàn bộ được bọc trong một
`GHResponse` (best path + alternatives + errors), và chính `getBest()` của nó (`GHResponse.java:48`, đã gặp
ở §1.4) là thứ mà resource serialize.

## 7.5 Họ endpoint

Mỗi capability là một JAX-RS resource trong `web-bundle`. `/route` thì bạn đã trace rồi (§1.4):

```java
@Path("route")   public class RouteResource { ... GHResponse ghResponse = graphHopper.route(request); // :154 }
```

**`/isochrone`** — "mọi nơi tới được trong N giây/mét" — mọc lên một *cây* shortest-path (không phải một
path đơn) rồi contour nó thành một polygon:

```java
@Path("isochrone")
// ...
ShortestPathTree shortestPathTree = new ShortestPathTree(queryGraph, ..., reverseFlow, traversalMode);  // :105
// ...bucket the reachable area by time/distance, then triangulate + contour:
Triangulator.Result result = triangulator.triangulate(snap, queryGraph, shortestPathTree, fz, ...);     // :127
```
📌 `web-bundle/src/main/java/com/graphhopper/resources/IsochroneResource.java:46`–`:128` (đoạn dispatch giới
hạn weight/distance/time nằm ở `:109`–`:122`).

**`/nearest`** — snap một toạ độ về graph — chỉ là một lần tra location-index:

```java
@Path("nearest")
Snap snap = index.findClosest(point.lat, point.lon, EdgeFilter.ALL_EDGES);   // :70
```
📌 `NearestResource.java:42`–`:70`. **`/mvt/{z}/{x}/{y}.mvt`** phục vụ **vector tile** kiểu Mapbox để client
vẽ được mạng lưới routable:

```java
@Path("mvt")
@GET @Path("{z}/{x}/{y}.mvt")
public Response doGetXyz(@PathParam("z") int zInfo, @PathParam("x") int xInfo, @PathParam("y") int yInfo, ...)
// ...uses a VectorTileEncoder                                                // :93
```
📌 `MVTResource.java:34`–`:93`. (Còn có một endpoint `/spt` cho shortest-path-tree và các resource riêng cho
PT phục vụ isochrone và tile của transit.)

> 🧠 **Mental model:** tất cả các endpoint đều là *cùng một* engine nhìn qua những lăng kính khác nhau.
> `/route` là một path; `/isochrone` là toàn bộ tập điểm tới được (một cây, không phải một path); `/nearest`
> chỉ là bước snap; `/mvt` là chính cái graph, được vẽ ra. Một khi bạn thấy chúng đều là hình chiếu của
> graph + bộ máy shortest-path, thì ở đây chẳng có khái niệm nào mới — chỉ có output mới.

## 7.6 Lab 7 — chạm vào bề mặt

> 🧪 **Lab 7.** Lab server. Mục tiêu: luyện chạy cả họ endpoint và đọc response model. Ghi lại vào
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

**Kết quả kỳ vọng:** `Instruction.java:34` là `CONTINUE_ON_STREET = 0`, `:32` là `TURN_LEFT = -2`;
`IsochroneResource.java:105` dựng một `ShortestPathTree`; `query.py` in ra route kèm dăm dòng instruction và
mã sign của chúng, rồi tới số đỉnh của polygon isochrone; `/nearest` trả về một toạ độ đã snap và distance
của nó. Ghi lại những mã sign nào đã xuất hiện trên route của bạn.

## 7.7 Checkpoint

1. Một path là một danh sách edge; tài xế thì cần instruction. Cái gì quyết định một junction xứng đáng có
   một instruction, và integer nào mã hoá "turn left" so với "turn right"?
2. `ResponsePath` mang theo những gì ngoài distance và time, và một `PathDetail` là gì?
3. `/isochrone` và `/route` dùng cùng một engine nhưng trả về những shape khác nhau. Khác biệt về mặt cấu
   trúc là gì (path so với …)?
4. Các hành trình transit (Chương 5) tái dùng hệ instruction. Cái gì trong `Instruction` chứng minh điều đó?
5. Trace trong một câu: từ `GHResponse.getBest()` tới JSON mà app của bạn parse — ai là người serialize?

> Nếu #1 còn lung lay, đọc lại §7.3. Nếu #3 còn lung lay, đọc lại §7.5.

## 🔌 Connect to your past (the on-screen map and the ETA)

Chương này là tất cả những gì UI của bạn chạm vào. Mấy mũi tên turn và cái banner "300 m nữa, rồi rẽ trái"
trên một màn hình navigation chính là `InstructionList` + sign code được render ra. Cái ETA mà VinBus hiển
thị là `ResponsePath.getTime()`. Cái "mình đang đi trên những con đường nào" mà một màn trip-detail tô màu
chính là `PathDetail`. Lớp overlay vùng-tới-được mà một tính năng service-coverage hay "xe gần bạn" vẽ ra
chính là `/isochrone`. Bản thân base map có thể đến từ `/mvt`. Mọi thứ các thuật toán đã tính ở Chương 3–6
chỉ thực sự trở thành *sản phẩm* tại đây — và giờ thì bạn đọc được chính xác cái object mà app của bạn
deserialize và chính xác cái endpoint nó đã gọi để lấy về.

**Next:** bạn đã đọc hết cả engine. Chương cuối sẽ giúp bạn tự lực — một capstone, tự đọc một PR thật mà
không cần trợ giúp, và re-sync cuốn sách này khi bạn re-pin.
→ **[Chapter 08 — Capstone & Staying Current](08-capstone-and-staying-current.md)**
