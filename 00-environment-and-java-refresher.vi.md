# Chapter 00 — Environment & Java Refresher

> **Goal:** Kết thúc chương này bạn có trong tay một bản GraphHopper *đọc được*, pinned ở **`11.0`**
> (`69e50f6`), một Maven build cho ra một server chạy được, server đó trả lời một `/route` thật trên một
> extract cỡ một thành phố, và bạn thạo bốn idiom mà codebase mặc định bạn đã biết: **fluent API
> `GraphHopper`/`GHRequest`**, layout **Maven multi-module**, storage **`DataAccess` dạng flat-array**, và
> lifecycle **hai pha "import rồi query"**. Bạn sẽ không đọc hết mọi module — bạn sẽ học cách *đọc* bất kỳ
> module nào.

## 0.1 Vì sao quan trọng

Nếu bạn mở `core/src/main/java/com/graphhopper/routing/Dijkstra.java` mà chưa có bối cảnh gì, nó trông đơn
giản đến mức đánh lừa — một priority queue và một vòng lặp. Cái rối không nằm ở thuật toán; nó nằm ở *phần
giàn giáo* xung quanh: một `Weighting` mà bạn không tự định nghĩa, một `EdgeExplorer` lặp qua một thứ không
phải collection, một `edgeId` kiểu integer ở chỗ bạn tưởng phải là object, và một graph sống trong các
segment `byte[]` thay vì một `Map<Node, List<Edge>>`. Chẳng cái nào khó một khi bạn biết mỗi thứ *thuộc
loại* gì. Chương này dồn các idiom đó lên đầu để phần còn lại của cuốn sách nói về *routing*, chứ không phải
về đường ống.

Lý do thứ hai: GraphHopper được xây để trả lời một route trong **dưới một mili-giây** trên một graph cỡ cả
lục địa, trên một server với ngân sách bộ nhớ cố định. Kỷ luật performance đó — nhồi graph vào các flat
array, preprocess một lần, rồi chỉ chạy query read-only — định hình mọi quyết định thiết kế bạn sắp đọc.
Nếu bạn từng bận tâm về latency và bộ nhớ trên một backend có người dùng thật gõ vào, cách đóng khung này
sẽ thấy như về nhà.

## 0.2 Lấy source, pinned

Chúng ta pin vào một release tag cố định để mọi `file:line` trong sách đều resolve đúng. Clone shallow ngay
tại tag:

```bash
cd ~/Documents/learning   # or wherever you keep the book
git clone --depth 1 --branch 11.0 \
  https://github.com/graphhopper/graphhopper.git graphhopper
cd graphhopper
git rev-parse --short HEAD     # → 69e50f6
git describe --tags            # → 11.0
```

> 📁 Để ý tag **không có tiền tố `v`** — nó là `11.0`, không phải `v11.0`. `git describe --tags` in ra đúng
> `11.0`. Dùng ref này thì số dòng của bạn sẽ khớp với cuốn sách.

Không có submodule nào phải chạy theo — GraphHopper không vendor thứ gì nặng trong git. Input lớn duy nhất là
OSM extract và (ở Chapter 5) một GTFS feed, đều tải riêng và bị `.gitignore` giữ ở ngoài.

## 0.3 Môi trường: Java 17 và Maven

GraphHopper rất dứt khoát về phiên bản Java. Trích từ build metadata:

```xml
<maven.compiler.target>17</maven.compiler.target>
```
📌 `pom.xml:19` (và `<release>17</release>` trong compiler plugin ở `pom.xml:187`; README ghi "≥ Java 17"
ở `README.md:106`). Java **17 trở lên** — JDK cũ hơn sẽ không compile được nó.

Đây là một project **Maven multi-module**. Root `pom.xml` liệt kê các module mà cuốn sách này đi qua:

```xml
<modules>
  <module>core</module>          <!-- the graph + the routing algorithms -->
  <module>reader-gtfs</module>   <!-- public transit (Chapter 5) -->
  <module>tools</module>
  <module>map-matching</module>  <!-- GPS → road (Chapter 6) -->
  <module>web-bundle</module>    <!-- the HTTP resources (RouteResource, …) -->
  <module>web-api</module>       <!-- the request/response value objects -->
  <module>web</module>           <!-- the Dropwizard server -->
  <module>client-hc</module>
  <module>navigation</module>
  <module>example</module>       <!-- runnable Java examples -->
</modules>
```
📌 `pom.xml:60`–`:71`. Parent artifact là `graphhopper-parent`, version `11.0-SNAPSHOT`, packaging
`pom` (`pom.xml:6`–`:10`).

> 🧠 **Mental model:** khi bạn muốn biết một thứ gì đó nằm ở đâu, hãy map mối quan tâm đó về một module
> trước. *Thuật toán?* `core`. *HTTP endpoint?* `web-bundle/.../resources/`. *Cái `GHRequest` bạn truyền
> vào?* `web-api`. *Transit?* `reader-gtfs`. Bạn gần như không bao giờ grep cả cây — bạn grep đúng một module.

Build tất cả (lệnh này compile các module và tạo ra server jar):

```bash
mvn -q -DskipTests clean install       # first run downloads deps; a few minutes
```

Rồi chạy server. Đường nhanh nhất dùng nước tí hon **Andorra** đi kèm sẵn trong repo:

```bash
# config-example.yml is at the repo root; andorra.osm.pbf is bundled under core/files/
java -D"dw.graphhopper.datareader.file=core/files/andorra.osm.pbf" \
     -jar web/target/graphhopper-web-*.jar server config-example.yml
# → open http://localhost:8989/  (a Leaflet map you can click to route on)
```

Entry point của server là một Dropwizard `Application`:

```java
public final class GraphHopperApplication extends Application<GraphHopperServerConfiguration> {
    public static void main(String[] args) throws Exception {
        new GraphHopperApplication().run(args);
    }
```
📌 `web/src/main/java/com/graphhopper/application/GraphHopperApplication.java:34`–`:38`. Nó lắng nghe ở
`8989` và config nó đọc (`config-example.yml`) khai báo `graph.location: graph-cache` (dòng 6), danh sách
`profiles:` (dòng 31 — cái đầu tiên là `car`), và block `profiles_ch:` (dòng 86) bật Contraction
Hierarchies. Chúng ta sẽ mổ hết những cái đó; giờ thì cứ lấy một `/route` xanh cái đã.

> 💡 Bạn có thể đọc và grep toàn bộ codebase mà **không cần build gì cả**. Chỉ những lab *chạy* một query mới
> cần server. Đừng để một lần `mvn install` đầu tiên chậm chạp cản bạn đọc source.

## 0.4 Idiom 1 — façade fluent: `GraphHopper`, `GHRequest`, `GHResponse`

Public API là một **builder**. Bạn cấu hình một object `GraphHopper` bằng các setter nối chuỗi, gọi
`importOrLoad()`, rồi hỏi nó lấy route. Ví dụ kinh điển là hòn đá Rosetta của cuốn sách:

```java
GraphHopper hopper = new GraphHopper();
hopper.setOSMFile("core/files/andorra.osm.pbf");
hopper.setGraphHopperLocation("target/routing-graph-cache");
hopper.setEncodedValuesString("car_access, car_average_speed");
hopper.setProfiles(new Profile("car").setCustomModel(...));
hopper.getCHPreparationHandler().setCHProfiles(new CHProfile("car"));
hopper.importOrLoad();
```
📌 `example/src/main/java/com/graphhopper/example/RoutingExample.java:32`–`:49` (`createGraphHopperInstance`).
Ở đây mỗi setter không trả gì để dễ đọc, nhưng API vốn là fluent — `GraphHopper.setOSMFile`
(`GraphHopper.java:350`), `setGraphHopperLocation` (`:333`), `setEncodedValuesString` (`:144`),
`setProfiles` (`:273`) — và bản thân class façade `GraphHopper` nằm ở `GraphHopper.java:85`.

Một route là: một request object vào, một response object ra:

```java
GHRequest req = new GHRequest(42.508552, 1.532936, 42.507508, 1.528773)
        .setProfile("car").setLocale(Locale.US);
GHResponse rsp = hopper.route(req);
ResponsePath path = rsp.getBest();
double distanceMeters = path.getDistance();   // :148
long timeMillis       = path.getTime();
```
📌 `RoutingExample.java:51`–`:73`. Ba value object bạn sẽ gặp ở mọi trang đều sống trong `web-api`:

- **`GHRequest`** — điểm + profile + options. `GHRequest.java:38`; constructor ở `:51/:62/:66/:81`;
  `addPoint` fluent trả về `this` (`:99`–`:104`), `setProfile` ở `:168`.
- **`GHResponse`** — best path cộng các alternative: `GHResponse.java:32`; `getBest()` trả về
  `responsePaths.get(0)` (`:48`–`:53`); `hasErrors()` ở `:94`.
- **`ResponsePath`** — một route: `ResponsePath.java:34`; `getPoints()` (`:99`), `getDistance()` (`:148`).

> 🧠 **Mental model:** `GraphHopper` là một *façade*. Nó giấu graph, location index, các CH graph và các
> landmark sau đúng hai động từ — `importOrLoad()` (build hoặc mở) và `route()` (hỏi). Cả lớp web (Chapter 1)
> chỉ là chính cái API này được với tới qua HTTP.

## 0.5 Idiom 2 — lifecycle hai pha: import một lần, query nhiều lần

Hình khối quan trọng nhất trong GraphHopper là **preprocessing và querying là hai pha khác nhau**.
`importOrLoad()` nói thẳng điều đó ra:

```java
public GraphHopper importOrLoad() {
    if (!load()) {
        printInfo();
        process(false);   // parse OSM, build the graph, run CH/LM preparation, write graph-cache/
    } else {
        printInfo();       // graph-cache/ already exists → just memory-map it
    }
    return this;
}
```
📌 `GraphHopper.java:793`–`:801`. Lần chạy đầu parse cái `.osm.pbf`, build graph, chạy phần *preparation*
Contraction-Hierarchies / Landmarks nặng nề (Chapter 3), và ghi tất cả ra thư mục `graph-cache/`. Mọi lần
chạy sau đó chỉ **load** thư mục đó — vì thế một warm start là tức thì và query không bao giờ đụng lại OSM.

> 💡 Nếu bạn đổi một profile, một encoded value, hay file OSM, bạn phải **xoá `graph-cache/`** và re-import.
> Một cache cũ là gotcha "sao thay đổi của tôi không có tác dụng?" số 1. (Chapter 4 giải thích vì sao một
> chỉnh sửa `CustomModel` là ở import-time, không phải query-time.)

## 0.6 Idiom 3 — graph là flat array, không phải object

Đây là idiom làm app developer bất ngờ nhất. GraphHopper **không** lưu mạng lưới đường dưới dạng các object
`Node` và `Edge`. Nó lưu chúng dưới dạng **các mảng byte nguyên thuỷ**, đánh địa chỉ bằng integer id, phía
sau một `DataAccess`:

```java
public interface DataAccess extends Closeable {
    void setInt(long bytePos, int value);   // :37
    int  getInt(long bytePos);              // :42
    boolean loadExisting();                 // :105
```
📌 `core/src/main/java/com/graphhopper/storage/DataAccess.java:28`. Một node là một `int`; một edge là một
`int`; đọc "khoảng cách của edge 42" là một *phép tính offset vào một mảng byte*, không phải một truy cập
field trên một object. Có hai implementation, chọn theo `DAType`:

- **`RAMDataAccess`** — `byte[][] segments` on-heap (`RAMDataAccess.java:35`–`:36`). Mặc định.
- **`MMapDataAccess`** — các file memory-mapped, để một graph cỡ lục địa không bao giờ vào hết heap:

```java
buf = raFile.getChannel().map(
        allowWrites ? FileChannel.MapMode.READ_WRITE : FileChannel.MapMode.READ_ONLY, offset, byteCount);
```
📌 `core/src/main/java/com/graphhopper/storage/MMapDataAccess.java:163`–`:164` (class ở `:49`,
`DAType.MMAP` ở `DAType.java:49`). Đây chính là cùng cái kỷ luật "thao tác trên một mapped buffer, đừng
`memcpy` cả thế giới vào không gian địa chỉ của mình" mà bạn sẽ dùng cho một dataset lớn, đọc là chính.

> 🧠 **Mental model:** mọi thứ "graph" đều là một `int` id và một byte offset. Khi Chapter 2 cho bạn xem một
> `EdgeIterator`, nó không lặp qua một `List` — nó đang đẩy một con trỏ chạy dọc các flat array này. Nắm lấy
> điều đó thì lớp storage hết bí ẩn.

## 0.7 Idiom 4 — encoded value: thuộc tính mỗi edge nhồi vào các bit

Idiom cuối: những thuộc tính mà một route quan tâm — đường này ô tô đi được không? tốc độ trung bình bao
nhiêu? road class của nó là gì? — được lưu theo từng edge dưới dạng **encoded value**, các field nhỏ
bit-packed bên trong bản ghi edge. Bạn đã cấu hình hai cái trong số đó ở §0.4 với
`setEncodedValuesString("car_access, car_average_speed")`. `Weighting` (Chapter 3) đọc chúng lại theo từng
edge để tính ra một cost. Bạn chưa cần biết internal của encoder ngay bây giờ; chỉ cần nhận ra hình khối:
một `EncodedValue` là một accessor có tên, cố định bit-width, vào storage phẳng của edge, được resolve qua
một `EncodingManager`. Chapter 4 là chỗ cái này trở thành công cụ chính của bạn.

## 0.8 Lab 0 — build và lấy route đầu tiên

> 🧪 **Lab 0.** Mục tiêu: xác nhận clone của bạn đã pinned, build xanh, và server trả lời một route thật.
> Ghi kết quả vào [`labs/lab00-build.md`](labs/lab00-build.md).

```bash
cd ~/Documents/learning/graphhopper
git describe --tags                                  # expect: 11.0
git rev-parse --short HEAD                            # expect: 69e50f6

# count the Maven modules the build knows about:
grep -c "<module>" pom.xml                            # expect: 10

# build (skip tests for speed), then run on the bundled Andorra extract:
mvn -q -DskipTests clean install
java -D"dw.graphhopper.datareader.file=core/files/andorra.osm.pbf" \
     -jar web/target/graphhopper-web-*.jar server config-example.yml &
sleep 20   # first import parses OSM + runs CH prep, then writes graph-cache/

# ask for a route across Andorra la Vella and read the answer:
python3 ~/Documents/learning/graphhopper-book/labs/query_route/query.py \
        42.508,1.533 42.5075,1.5288
```

**Expected:** `git describe` in ra `11.0`; số module là `10`; lần khởi động server đầu tiên log một OSM
import và CH preparation, rồi "Started server" trên port `8989`; và `query.py` in ra một dòng với khoảng
cách theo ki-lô-mét, thời gian theo phút, và một nhúm instruction. Ghi thời gian import và kích thước
`graph-cache/` vào lab note của bạn — bạn sẽ so một lần restart warm (chỉ load) với con số đó.

## 0.9 Checkpoint

1. Vì sao cuốn sách này pin theo một tag *và* một SHA thay vì bám `master`? `git describe --tags` in ra
   đúng chuỗi nào?
2. Bạn muốn tìm HTTP endpoint xử lý `/route`. Bạn nhìn vào *module* nào, và module nào giữ class `GHRequest`
   bạn truyền vào nó?
3. Hai pha mà `importOrLoad()` lựa giữa là gì, và cái gì sống trong `graph-cache/`?
4. Một node và một edge mỗi cái chỉ là một `int`. Vậy cái gì thực sự giữ "khoảng cách của edge 42", và hai
   implementation `DataAccess` chống lưng cho nó là gì?
5. Phiên bản Java nào là bắt buộc, và hai dòng nào trong `pom.xml` pin nó?

> Nếu #3 còn mờ, đọc lại §0.5. Nếu #4 còn mờ, đọc lại §0.6.

## 🔌 Connect to your past (transit & ride-hailing backends)

Hai cây cầu lặp lại xuyên suốt cả cuốn sách:

- **Transit apps (BusMap / VinBus).** Một transit backend đúng là hình khối này: import một feed tĩnh một
  lần (ở đó là GTFS thay vì OSM), preprocess nó thành một cấu trúc query nhanh, rồi phục vụ các journey query
  read-only. Lifecycle import-rồi-query của GraphHopper (§0.5) *chính là* cách bạn sẽ tổ chức một dịch vụ
  stop-and-schedule, và Chapter 5 cho thấy GraphHopper làm đúng điều đó với `reader-gtfs`.
- **Ride-hailing / navigation.** Mỗi lần cuốn sách này nói "`hopper.route(req)` trả về một `ResponsePath`",
  hãy đọc nó là "microservice routing đã trả lời câu query ETA/dispatch mà app của bạn gửi tới." Ranh giới
  fluent `GHRequest` → `GHResponse` chính là cùng cái contract mà app của bạn đã có sẵn với bất kỳ dịch vụ
  routing nào nó gọi hôm nay — bạn sắp thấy phía bên kia của nó.

**Next:** với các idiom và một server đang chạy trong tay, hãy xem cả cỗ máy cùng một lúc — module map, và
hành trình của một request `/route` từ HTTP đến câu trả lời. → **[Chapter 01 — Mental Model & the Repo Map](01-mental-model-and-the-repo-map.md)**
