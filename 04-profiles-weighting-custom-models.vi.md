# Chapter 04 — Profiles, Weighting & Custom Models

> **Goal:** Học cách bạn *nắn* một tuyến đường. Sau chương này bạn giải thích được một `Profile` gắn một cái
> tên vào một `Weighting` như thế nào, `CustomModel` DSL biến các câu lệnh `speed`/`priority`/`distance_influence`
> thành một cost thật cho từng edge ra sao, và hệ thống `EncodedValue` (`EncodingManager`) đóng gói các thuộc
> tính per-edge — road class, max weight, access — vào các bit mà weighting đọc lại từng edge một như thế nào.
> Pinned ở **`11.0`** (`69e50f6`).

## 4.1 Vì sao quan trọng

Chương 3 đã bày ra các thuật toán nhưng coi `Weighting.calcEdgeWeight` như một hộp đen trả về "cost của edge
này". Chương này mở hộp đen đó ra. Chính cost mới là nơi *toàn bộ* tri thức miền cư ngụ: một chiếc xe hơi chạy
nhanh trên motorway và bị cấm trên footpath; một chiếc bus có thể đi vào làn dành riêng cho bus mà xe hơi không
được; một xe tải nặng không thể qua một cây cầu tải trọng 3.5 tấn. Không thứ nào trong số đó nằm ở thuật toán —
chúng nằm ở weighting, và GraphHopper cho bạn viết chúng dưới dạng cấu hình, chứ không phải code, thông qua
**custom model**.

Với bạn thì đây là chương tái dùng được trực tiếp nhất. Mọi luật kiểu "đội xe của tụi mình là đặc biệt" — VinBus
trên hạ tầng dành riêng cho bus, một chiếc EV né một hầm chui thấp trần, một chiếc xe gọi-xe ưu tiên đường lớn cho
tài xế đỡ mệt — đều là một câu lệnh custom-model đặt trên một encoded value. Học xong bạn sẽ tự viết được chúng.

## 4.2 Mental model: name → weighting → per-edge bits

```text
   config (yaml/json)                     per request
   ┌─────────────────┐   Profile("car")   ┌──────────────┐
   │ profiles:       │ ─────────────────▶ │  GHRequest    │  setProfile("car")
   │  - name: car    │                    └──────┬───────┘
   │    custom_model:│                           ▼
   │      priority:  │              ┌────────────────────────────┐
   │       - if road…│  compiled →  │  CustomWeighting            │
   │      speed: …   │  (Janino)    │   calcEdgeWeight(edge):     │
   └─────────────────┘              │     speed  = f(edge's EVs)  │──┐
                                    │     prio   = g(edge's EVs)  │  │ reads per-edge
                                    │     return dist/(speed·prio)│  │ encoded values
                                    │            + dist·distInfl  │  ▼
                                    └────────────────────────────┘  [ road_class | max_weight |
                                                                      roundabout | access | … ]
                                                                      ← EncodingManager packs these
                                                                        into the edge's flag bits
```

Chuỗi mắt xích: một `Profile` đặt tên cho một `Weighting`; với weighting `custom` mặc định, một `CustomModel`
(các câu lệnh `speed`/`priority` của bạn) được **compile** thành một class có `calcEdgeWeight` đọc **encoded
value** trên từng edge. Encoded value là các thuộc tính per-edge được đóng gói bit mà `EncodingManager` đã đặt
xuống lúc import.

## 4.3 `Profile` — một cái tên gắn với một cost

```java
public class Profile {
    // fields: name, weighting (default "custom"), turnCostsConfig, hints
    public String getWeighting() { ... }          // :89
    public CustomModel getCustomModel() {          // :105  stored inside hints under CustomModel.KEY
```
📌 `core/src/main/java/com/graphhopper/config/Profile.java:41`–`:107`. Một profile *chỉ là cấu hình*: một cái
tên (được validate ở `:47`), một loại weighting (`"custom"`, `"fastest"`, `"shortest"`…), việc nó có dùng turn
cost hay không (`hasTurnCosts`, `:109`–`:111`), và — với custom weighting — một `CustomModel` giấu bên trong
hints của nó. Profile `car` trong `config-example.yml` (§0.3) đúng y như vậy, với model của nó nằm ở `car.json`.

## 4.4 `CustomWeighting` — công thức cost

Công thức của weighting mặc định đủ nhỏ để giữ gọn trong đầu; Javadoc của class *chính là* bản spec:

```text
        distance
weight = ─────────────────────────  +  distance · distance_influence
         base_speed · speed_factor · priority
```
📌 `core/src/main/java/com/graphhopper/routing/weighting/custom/CustomWeighting.java:63`–`:73`. Đọc nó thành:
thời gian (distance chia cho speed hiệu dụng), chia cho một `priority` cho phép bạn khiến một con đường *cảm thấy*
dài hơn hay ngắn hơn mà không nói dối về speed của nó, cộng thêm một số hạng distance để đánh đổi giữa đi vòng và
thời gian. Mỗi edge:

```java
public double calcEdgeWeight(EdgeIteratorState edgeState, boolean reverse) {
    double priority = edgeToPriorityMapping.get(edgeState, reverse);   // :116
    double seconds  = calcSeconds(distance, edgeState, reverse);       // :120
    double distanceCosts = distance * distanceInfluence;               // :124
    return seconds / priority + distanceCosts;                         // :126
}
// calcSeconds → edgeToSpeedMapping.get(edgeState, reverse)            // :130
```
📌 `CustomWeighting.java:114`–`:137`. Để ý `edgeToPriorityMapping.get(edgeState, …)` và
`edgeToSpeedMapping.get(edgeState, …)` — đây chính là các câu lệnh đã compile từ model của bạn, được đánh giá
trên encoded value của *chính* edge này.

## 4.5 `CustomModel` DSL và cách nó được compile

Một `CustomModel` là ba danh sách: các câu lệnh `speed`, các câu lệnh `priority`, và một scalar
`distance_influence`:

```java
private Double distanceInfluence;                    // :35
private List<Statement> speedStatements;             // :39
private List<Statement> priorityStatements;          // :40
```
📌 `web-api/src/main/java/com/graphhopper/util/CustomModel.java:30`–`:41`. Trong YAML bạn viết chúng thành các
luật `if`/`else_if`/`multiply_by`/`limit_to` đặt trên encoded value:

```yaml
priority:
  - if: road_class == MOTORWAY
    multiply_by: 0.0          # forbid motorways for this profile
  - if: road_environment == FERRY
    multiply_by: 0.5
speed:
  - if: true
    limit_to: 90
```

Các câu lệnh đó không được interpret trên từng edge — như thế sẽ chậm khủng khiếp. Chúng được **compile thành
Java bytecode** ngay lúc import qua Janino. `CustomModelParser` dựng một subclass của `CustomWeightingHelper` và
nối `getSpeed`/`getPriority` của nó thành các method reference mà `CustomWeighting` gọi tới:

```java
clazz = createClazz(...);              // :97   compile + cache the generated class
CustomWeightingHelper prio = clazz.getDeclaredConstructor()....newInstance();   // :113
return new CustomWeighting.Parameters(prio::getSpeed, prio::calcMaxSpeed,
                                      prio::getPriority, prio::calcMaxPriority, ...);  // :115
```
📌 `core/src/main/java/com/graphhopper/routing/weighting/custom/CustomModelParser.java:91`–`:124` (template của
subclass sinh ra nằm ở `:473`–`:498`; class cơ sở với các stub có thể override là
`CustomWeightingHelper.java:37`–`:58`). Các cận `calcMaxSpeed`/`calcMaxPriority`
(`CustomWeightingHelper.java:64`–`:91`) quan trọng cho §3.4/§3.6 — chúng cho A*/LM cái cận trên admissible về
speed.

> ⚠️ **The security boundary.** Model của bạn là text do người dùng cung cấp rồi biến thành code thực thi được,
> nên GraphHopper ràng buộc nó rất chặt: các biểu thức được parse bởi `ValueExpressionVisitor`, thứ chỉ whitelist
> một tập rất nhỏ các method (đúng nghĩa đen là `Set.of("sqrt")`), từ chối bất cứ thứ gì còn token thừa phía sau,
> và trích xuất chính xác những encoded value nào một biểu thức được phép đụng tới. 📌
> `core/.../weighting/custom/ValueExpressionVisitor.java:38`–`:42`,`:135`–`:157`. Nếu có ngày bạn cho end user
> nhập custom model, đây chính là đoạn code giữ cho "priority: `System.exit(0)`" không compile được.

> 💡 Một thay đổi custom-model diễn ra **lúc import**, không phải lúc query (nó thay đổi weighting đã compile), và
> đó là lý do bạn không thể chạy CH với một custom model theo từng request — weighting của CH đã bị đóng băng
> (§3.5). Custom model linh hoạt chạy trên đường LM hoặc flexible. Đây chính là cái gotcha §0.5 "xoá `graph-cache/`
> rồi import lại" ở một dạng trá hình.

## 4.6 Encoded value — thuộc tính per-edge trong từng bit

Các câu lệnh phía trên đọc những thứ như `road_class` và `max_weight`. Chúng là **encoded value**: các trường có
tên, độ rộng bit cố định, được đóng gói vào bản ghi của từng edge. `Weighting` đọc chúng qua một lookup:

```java
public interface EncodedValueLookup {
    BooleanEncodedValue getBooleanEncodedValue(String key);   // :28
    DecimalEncodedValue getDecimalEncodedValue(String key);   // :30
    EnumEncodedValue<?> getEnumEncodedValue(String key, ...); // :34
```
📌 `core/src/main/java/com/graphhopper/routing/ev/EncodedValueLookup.java:22`–`:39`. Mỗi `EncodedValue` giành
lấy một lát bit khi graph được dựng:

```java
int init(InitializerConfig init);   // :37  — asks the allocator for `usedBits`, gets a shift + mask
```
📌 `core/src/main/java/com/graphhopper/routing/ev/EncodedValue.java:28`–`:82`. Một giá trị decimal (như speed)
được lưu dưới dạng scaled vào một trường integer; đọc nó ra lại chính là điểm cuối mà câu lệnh `speed` đã compile
của bạn chạm đến:

```java
double getDecimal(boolean reverse, int edgeId, EdgeIntAccess edgeIntAccess);   // :20
```
📌 `core/src/main/java/com/graphhopper/routing/ev/DecimalEncodedValue.java:11`–`:46`. Các giá trị cụ thể được
khai báo với một `KEY` và một `create()` cố định ngân sách bit của chúng — một minh hoạ tuyệt vời cho sự đánh đổi
giữa không gian và độ chính xác:

```java
// MaxWeight: 9 bits, 0.1-tonne resolution
public static DecimalEncodedValue create() {
    return new DecimalEncodedValueImpl(KEY, 9, 0, 0.1, ...);   // MaxWeight.java:~31
}
```
📌 `core/src/main/java/com/graphhopper/routing/ev/MaxWeight.java:27`–`:37` (xem thêm `RoadClass.java:26`–`:35`
như một enum value và `Roundabout.java:20`–`:25` như một boolean). **`EncodingManager`** là cái registry sở hữu
tất cả chúng và phát ra những lát bit không chồng lấn:

```java
public class EncodingManager implements EncodedValueLookup {
    // Builder.add(ev): ev.init(edgeConfig); encodedValueMap.put(ev.getName(), ev);   :137
```
📌 `core/src/main/java/com/graphhopper/routing/util/EncodingManager.java:44`–`:45`,`:126`–`:166` (các lookup ném
lỗi khi thiếu key ở `:225`–`:257`). Nhớ lại §0.4:
`setEncodedValuesString("car_access, car_average_speed")` chính là lúc bạn nói cho manager này biết cần đóng gói
những giá trị nào — và một custom model chỉ có thể tham chiếu những giá trị đã được đóng gói.

## 4.7 Lab 4 — nắn một tuyến đường

> 🧪 **Lab 4.** Chỉ đọc + một request custom. Mục tiêu: đổi một tuyến đường bằng một custom model, và truy vết
> các encoded value nó đọc. Ghi vào [`labs/lab04-profiles.md`](labs/lab04-profiles.md).

```bash
cd ~/Documents/learning/graphhopper
# read the formula and the choke where a model is evaluated per edge:
sed -n '63,73p;114,137p' core/src/main/java/com/graphhopper/routing/weighting/custom/CustomWeighting.java
sed -n '38,42p' core/src/main/java/com/graphhopper/routing/weighting/custom/ValueExpressionVisitor.java

# a custom model over the flexible engine (POST). Down-weight primary roads and re-route:
curl -s -X POST "http://localhost:8989/route" -H "Content-Type: application/json" -d '{
  "points": [[13.389,52.517],[13.421,52.508]],
  "profile": "car", "ch.disable": true,
  "custom_model": { "priority": [ {"if": "road_class == PRIMARY", "multiply_by": 0.2} ] }
}' | python3 -c "import sys,json;d=json.load(sys.stdin);p=d['paths'][0];print('km',round(p['distance']/1000,2),'min',round(p['time']/60000,1))"
```

**Expected:** `CustomWeighting.java:126` đọc `return seconds / priority + distanceCosts;`;
`ValueExpressionVisitor.java:38` cho thấy whitelist method chỉ-có-`sqrt`; và request custom trả về distance/time
*khác* so với tuyến `car` thường (nó né các primary road). Ghi lại cả hai. (Custom model cần đường flexible hoặc
LM — nên mới có `ch.disable`.)

## 4.8 Checkpoint

1. Một `Profile` thực chất chứa những gì, và `CustomModel` của nó sống ở đâu?
2. Viết lại công thức cost của `CustomWeighting` từ trí nhớ. `priority` cho bạn làm được điều gì mà đổi `speed`
   không làm được?
3. Một custom model là text người dùng nhập rồi biến thành code thực thi. Hai cơ chế giữ cho việc đó an toàn —
   gọi tên chúng và file chúng nằm trong.
4. Vì sao một thay đổi custom-model bắt buộc phải import lại, và vì sao nó không chạy được trên CH?
5. `road_class == MOTORWAY` — `road_class` *là gì* ở tầng lưu trữ, và ai đã đảm bảo có đủ bit cho nó và cho mọi
   encoded value khác?

> If #2 is shaky, re-read §4.4. If #5 is shaky, re-read §4.6.

## 🔌 Connect to your past (your vehicles are the custom model)

Đây là nơi những nét oái oăm của đội xe nhà bạn trở thành code bạn viết được. Một **làn dành riêng cho bus** mà
VinBus được đi còn xe hơi thì không là một câu lệnh `priority` gate trên một access encoded value. Một hầm chui
**giới hạn chiều cao hoặc tải trọng** mà một chiếc EV hay một xe cỡ lớn phải né là một `priority: 0` khi
`max_height`/`max_weight` xuống dưới ngưỡng — đúng cái `MaxWeight` value ở §4.6. Một sở thích của xe gọi-xe với
**đường to, êm hơn** (dễ chịu cho khách, nhàn cho tài) là một `multiply_by` trên `road_class`. Và quan trọng nhất:
giờ bạn đã biết *vì sao* các luật đó không thể đi trên đường CH nhanh (weighting của chúng theo từng request), nên
bạn sẽ phục vụ chúng trên đường Landmarks ở §3.6. Cuộc trao đổi "đội xe của tụi mình là đặc biệt" mà bạn đã có cả
trăm lần, trong GraphHopper, chỉ là một khối YAML ngắn đặt trên đúng encoded value.

**Next:** ta đã đi hết định tuyến đường bộ từ trên xuống dưới. Giờ đến mạng lưới còn lại mà app của bạn sống trên
đó — **public transit**, nơi bản thân thời gian là một phần của graph. → **[Chapter 05 — Public Transit: GTFS & RAPTOR](05-public-transit-gtfs-raptor.md)**
