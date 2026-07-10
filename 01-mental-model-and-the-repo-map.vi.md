# Chapter 01 — Mental Model & the Repo Map

> **Goal:** Giữ được cả engine trong đầu cùng một lúc. Sau chương này bạn gọi tên được bốn tầng của
> GraphHopper — **import → store → query → shape** — chỉ ra được module mà mỗi tầng nằm trong đó, và lần
> theo một request `/route?point=A&point=B` qua từng chặng, từ HTTP resource cho tới `ResponsePath` mà nó
> trả về rồi ra ngoài dưới dạng JSON. Pinned tại **`11.0`** (`69e50f6`).

## 1.1 Vì sao quan trọng

Một routing engine nghe như chỉ làm một việc — "tìm đường ngắn nhất" — nhưng thật ra nó làm **bốn** việc,
và chúng chạy vào những thời điểm khác nhau. Nếu không tách bạch ra, code trông như một mê cung; một khi
tách rồi, file nào cũng có chỗ ở rõ ràng của nó:

1. **Import** — biến một file bản đồ (`.osm.pbf`) thành một graph nội bộ. Chạy một lần.
2. **Store** — giữ graph đó ở dạng gọn, memory-mappable trên đĩa (`graph-cache/`). Tồn tại lâu dài.
3. **Query** — cho hai điểm, chạy một thuật toán trên graph đã lưu. Chạy mỗi request, trong khoảng ~1 ms.
4. **Shape** — biến chuỗi edge thô thành thứ client cần: turn instructions, geometry, một cái ETA.

Toàn bộ phần còn lại của cuốn sách là một chuyến đi vòng qua bốn tầng đó. Chương này vẽ ra tấm bản đồ để
các chương sau trở thành "đào sâu vào một cái ô bạn đã đặt sẵn vị trí", chứ không phải "cái này rốt cuộc
nằm ở đâu?".

## 1.2 Mental model: import → store → query → shape

```text
   OSM .pbf                                          graph-cache/ (on disk)
      │                                                    ▲   │
      ▼                                                    │   ▼
┌───────────┐   BaseGraph    ┌──────────────┐  CH/LM prep  │  ┌──────────────────────────────┐
│  IMPORT   │ ─────────────▶ │    STORE     │ ────────────▶│  │           QUERY              │
│ OSMReader │  nodes+edges   │ DataAccess   │  shortcuts   │  │ Router → RoutingAlgorithm    │
│  (core)   │                │ (flat arrays)│  landmarks   │  │  Dijkstra / A* / CH / LM     │
└───────────┘                └──────────────┘              │  └──────────────┬───────────────┘
   Chapter 2                     Chapter 2                     Chapter 3      │ ResponsePath
                                                                             ▼
   ┌─────────────────────────────────────────────────────────────┐  ┌───────────────┐
   │  SHAPE: InstructionsFromEdges → InstructionList, PathDetail   │  │  web layer     │
   │         (Chapter 7)                                           │◀─│ RouteResource  │──▶ JSON
   └─────────────────────────────────────────────────────────────┘  └───────────────┘
                                                                        Chapter 1 (this trace)
```

Hai điều cần giữ trong đầu. Thứ nhất, **import + store diễn ra trước bất kỳ request nào** — đó là pha
`importOrLoad()` từ §0.5. Đến lúc một `/route` chạy tới, graph, các Contraction-Hierarchies shortcut, và
các landmark đã được dựng sẵn và memory-map rồi; một query chỉ *đọc*. Thứ hai, **web layer mỏng** — nó
parse một request, gọi đúng một method, rồi serialize câu trả lời. Mọi thứ thú vị đều nằm bên dưới nó.

## 1.3 Bản đồ module

Ánh xạ bốn tầng lên các Maven module từ §0.3:

| Tầng | Nằm trong | Symbol chủ chốt |
|-------|----------|--------------|
| Import | `core` | `OSMReader`, `WaySegmentParser` |
| Store | `core` | `BaseGraph`, `DataAccess`, `EdgeIterator`, `TurnCostStorage` |
| Query | `core` | `Router`, `RoutingAlgorithm`, `Dijkstra`, `AStar`, CH (`ch/`), Landmarks (`lm/`) |
| Shape | `core` + `web-api` | `InstructionsFromEdges` (core), `Instruction`/`ResponsePath` (web-api) |
| Transit | `reader-gtfs` | `GtfsReader`, `PtGraph`, `MultiCriteriaLabelSetting` |
| Map-matching | `map-matching` | `MapMatching`, `HmmProbabilities` |
| HTTP surface | `web-bundle` + `web` | `RouteResource`, `IsochroneResource`, `GraphHopperApplication` |
| Request/response object | `web-api` | `GHRequest`, `GHResponse`, `ResponsePath` |

> 🧠 **Mental model:** `core` là engine; `web-api` là *bộ từ vựng* mà engine và thế giới bên ngoài dùng
> chung (`GHRequest`/`GHResponse`); `web-bundle` + `web` là lớp da HTTP. Các module transit và map-matching
> là anh em ngang hàng với `core`, tái dùng graph và thuật toán của nó.

## 1.4 Một request, đầu đến cuối

Cùng lần theo `GET /route?point=52.52,13.39&point=52.50,13.42&profile=car` qua từng chặng. Mở từng file
ra khi ta đi tới.

**Hop 1 — HTTP resource.** Endpoint là một JAX-RS resource:

```java
@Path("route")
public class RouteResource {
```
📌 `web-bundle/src/main/java/com/graphhopper/resources/RouteResource.java:57`–`:58`. Cái `GET` handler
(`:82`–`:108`) khai báo các query parameter, bao gồm `point` lặp lại và `profile`:

```java
@QueryParam("point") @NotNull List<GHPointParam> pointParams,   // :89
@QueryParam("profile") String profileName,                      // :96
```

**Hop 2 — params thành một `GHRequest`.** Resource lắp ráp lại đúng cái domain object bạn từng dựng thủ
công ở §0.4:

```java
GHRequest request = new GHRequest();                 // :116
// ...
request.setPoints(points).setProfile(profileName)
       .setAlgorithm(algoStr).setLocale(localeStr);  // :122–:133
```
📌 `RouteResource.java:116`–`:133`. Một chút xử lý resolve profile chạy trước (`:145`–`:152`), rồi đến đúng
một dòng bắc cầu từ web layer sang engine:

```java
GHResponse ghResponse = graphHopper.route(request);
```
📌 `RouteResource.java:154`. Mọi thứ phía trên dòng này là HTTP; mọi thứ phía dưới là engine. Nếu response
có lỗi, resource ánh xạ chúng thành HTTP 400 (`:159`–`:165`).

**Hop 3 — façade dựng một `Router` mới toanh.** `GraphHopper.route` bé xíu — và hé lộ nhiều điều:

```java
public GHResponse route(GHRequest request) {
    return createRouter().route(request);
}
```
📌 `core/src/main/java/com/graphhopper/GraphHopper.java:1333`–`:1335`. `createRouter()` (`:1337`–`:1347`)
kiểm tra engine đã load đầy đủ chưa, rồi `doCreateRouter()` (`:1349`–`:1355`) dựng `new Router(...)`, trao
cho nó `baseGraph`, `encodingManager`, `locationIndex`, các profile, và — mấu chốt — các **CH graph** cùng
**landmark** đã prepare sẵn.

> 🧠 **Mental model:** một `Router` được tạo **mỗi request**, nhưng nó rẻ — chỉ đơn thuần nối dây tham
> chiếu tới những cấu trúc đã dựng sẵn, chia sẻ, chỉ-đọc. Phần nặng (graph, các shortcut) đã được dựng lúc
> import và không bao giờ dựng lại. Đây chính là ranh giới import/query được cụ thể hoá.

**Hop 4 — `Router` validate và dispatch.** Class là `Router.java:58`; method `route` của nó mới là phần
điều phối thật sự:

```java
public GHResponse route(GHRequest request) {
    try {
        checkNoLegacyParameters(request);
        checkAtLeastOnePoint(request);
        checkIfPointsAreInBoundsAndNotNull(request.getPoints());
        // ...
        Solver solver = createSolver(request);
        solver.checkRequest();
        solver.init();
        // ...
        return routeVia(request, solver);
```
📌 `Router.java:97`–`:120`. Cái quyết định duy nhất định đoạt mọi thứ về *tốc độ* của query là nó tạo ra
solver nào:

```java
if (chEnabled && !disableCH)      // Contraction Hierarchies — fastest, fixed weighting
    return createCHSolver(...);
else if (lmEnabled && !disableLM) // Landmarks/ALT — fast, flexible weighting
    return createLMSolver(...);
else                              // plain bidirectional Dijkstra/A* — slowest, fully flexible
    return createFlexSolver(...);
```
📌 `Router.java:190`–`:198` (`chEnabled`/`lmEnabled` được set ở `:88`–`:89` tuỳ vào có tồn tại CH graph /
landmark hay không). Cái lựa chọn ba nhánh đó **chính là** Chương 3.

**Hop 5 — câu trả lời quay về.** Solver chạy một thuật toán (Chương 3), dựng một `ResponsePath` kèm
geometry, distance, time và instructions (Chương 7), rồi resource rút ra cái tốt nhất:

```java
public ResponsePath getBest() { return responsePaths.get(0); }
```
📌 `web-api/src/main/java/com/graphhopper/GHResponse.java:48`. `RouteResource` serialize nó thành JSON và
ghi HTTP 200. Request hoàn tất.

## 1.5 Một insight duy nhất cần giữ

Mọi lời gọi `/route` đều dồn qua **một method** (`GraphHopper.route`, `:1333`) vào **một dispatcher**
(`Router.route`, `:97`), nơi đưa ra **một lựa chọn** (CH vs LM vs flexible, `:190`). Chỉ cần nhớ cái xương
sống đó, bạn có thể lần từ ngoài vào để tìm đường tới bất kỳ hành vi routing nào trong codebase.

## 1.6 Lab 1 — tự tay lần theo request

> 🧪 **Lab 1.** Không cần build gì thêm ngoài server ở Chương 0. Mục tiêu: xác nhận cái trace bằng cách đọc
> sáu chặng và quan sát request từ bên ngoài. Ghi vào [`labs/lab01-trace.md`](labs/lab01-trace.md).

```bash
cd ~/Documents/learning/graphhopper
# read each hop and confirm the line resolves to the symbol:
sed -n '57,58p;89p;96p;154p' web-bundle/src/main/java/com/graphhopper/resources/RouteResource.java
sed -n '1333,1335p' core/src/main/java/com/graphhopper/GraphHopper.java
sed -n '58p;97,120p;190,198p' core/src/main/java/com/graphhopper/routing/Router.java

# now the outside view — with the Chapter 0 server running:
python3 ~/Documents/learning/graphhopper-book/labs/query_route/query.py 52.517,13.389 52.508,13.421
curl -s "http://localhost:8989/route?point=52.517,13.389&point=52.508,13.421&profile=car" | head -c 400
```

**Expected:** `RouteResource.java:154` đọc ra `GHResponse ghResponse = graphHopper.route(request);`;
`GraphHopper.java:1333` đọc ra `public GHResponse route(GHRequest request)`; `Router.java:190`–`:198` cho
thấy nhánh CH/LM/flex. `query.py` in ra một dòng distance/time; cái `curl` cho thấy một JSON body với một
mảng `paths` và một `info.took` tính bằng millisecond. Để ý con số `took` đó — đó là toàn bộ query, và nó
tí xíu.

## 1.7 Checkpoint

1. Gọi tên bốn tầng của GraphHopper và nói tầng nào chạy *trước khi* một request tới, tầng nào chạy *mỗi*
   request.
2. Một request `/route` đi vào engine tại đúng một dòng. File:line nào, và cái gì nằm trên so với nằm dưới nó?
3. Vì sao `GraphHopper.route` dựng một **`Router` mới mỗi request**, và vì sao chuyện đó không tốn kém?
4. `Router.route` đưa ra một quyết định ba nhánh định đoạt tốc độ của query. Ba lựa chọn là gì và mỗi cái
   đánh đổi điều gì?
5. Module nào giữ `GHRequest`/`GHResponse`, và vì sao nó nằm *giữa* `core` và web layer?

> Nếu câu #2 còn lung lay, đọc lại §1.4 Hop 2–3. Nếu câu #4 còn lung lay, đọc lại §1.4 Hop 4 và giữ lấy nó
> cho Chương 3.

## 🔌 Connect to your past (your app already calls this boundary)

Dù app của bạn hôm nay làm routing kiểu gì, nó đều băng qua đúng cái ranh giới bạn vừa lần theo — thường là
một lời gọi HTTP tới một routing service. BusMap hỏi "đi từ điểm dừng A tới điểm dừng B thế nào", một
backend gọi xe hỏi "ETA từ tài xế tới khách là bao nhiêu" — cả hai đều gửi đi thứ tương đương một
`GHRequest` và đọc về thứ tương đương một `ResponsePath`. Thứ chương này trao cho bạn là *phía bên kia* của
lời gọi đó: cái xương sống `RouteResource` → `GraphHopper.route` → `Router` → `ResponsePath` mà request của
bạn vẫn luôn chạm vào. Từ đây trở đi, mỗi khi app của bạn thực hiện một lời gọi routing, bạn sẽ biết server
làm gì với nó trong cái millisecond trước khi nó trả lời.

**Next:** query layer cần một cái gì đó để đi trên đó. Hãy dựng nó — làm sao một file OSM trở thành cái
`BaseGraph` mà mọi thuật toán quét qua. → **[Chapter 02 — The Graph](02-the-graph-map-to-network.md)**
