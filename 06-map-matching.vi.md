# Chapter 06 — Map-Matching: snapping GPS to roads

> **Goal:** Hiểu cách một GPS trace nhiễu biến thành đúng con đường mà tài xế *thực sự* đã đi. Sau chương
> này bạn giải thích được **Hidden Markov Model** kiểu Newson–Krumm mà GraphHopper dùng: các candidate snap
> của mỗi GPS point là xác suất **emission**, việc route giữa các candidate là xác suất **transition**, và
> lượt **Viterbi** chọn ra đúng một chuỗi edge khả dĩ nhất. Pinned **`11.0`** (`69e50f6`).
> Đây là chương ride-hailing.

## 6.1 Vì sao quan trọng

GPS nói dối. Trong một hẻm núi đô thị (urban canyon), một điểm định vị có thể rơi lệch 30 mét, nằm sai phía
của một con đường có dải phân cách, hoặc rơi sang một con phố song song. Nếu bạn snap từng điểm một cách độc
lập vào edge gần nhất, bạn nhận được một đường đi cứ nhảy dịch qua dải phân cách rồi vòng ngược lại — vô dụng
khi cần tính quãng đường tài xế đã chạy, tính cước, hay xác định họ thực sự đang ở đâu. Map matching giải bài
toán *chuỗi*: cho cả một trace nhiễu và mạng lưới đường, đâu là con đường liên tục có xác suất cao nhất?

Với ride-hailing đây là phần đường ống nền móng. Dựng lại lộ trình thật của tài xế từ những mẩu vụn GPS chính
là cách bạn tính quãng đường và cước chuyến, phát hiện việc đi vòng lệch tuyến, và hiệu chỉnh ETA. Vẫn là cùng
một bài toán toán học dù bạn gọi nó là "trip reconstruction" hay "map matching."

## 6.2 Mental model: một Hidden Markov Model trên road graph

```text
  GPS observations:   o1 ······· o2 ······· o3        (noisy, ~1/sec)
                       │           │           │
        emission P ▼   │  ▼        │  ▼        │  ▼     (how close is each candidate snap?)
  candidates:      [a1 a2]     [b1 b2]     [c1 c2]     ← each obs snaps to a few nearby edges
                     │  \        /  \        /  │
        transition P  \  route  a→b  vs  route a→b'    (does the road distance ≈ the GPS distance?)
                       ▼           ▼           ▼
  Viterbi picks:      a2 ───────▶ b1 ───────▶ c2       ← the single most probable chain
```

Hai xác suất. **Emission**: khả năng vị trí thật đúng là *candidate edge này* là bao nhiêu, cho trước điểm GPS
rơi vào chỗ nó rơi? (Snap càng gần → xác suất càng cao, một phân phối chuẩn trên khoảng cách snap.)
**Transition**: khả năng tài xế đi từ candidate `a` sang candidate `b` giữa hai điểm GPS là bao nhiêu? (Nếu
khoảng cách *đường* giữa chúng gần với khoảng cách GPS đường thẳng → hợp lý; nếu con đường buộc phải đi vòng
một quãng lớn → khó xảy ra, một mức phạt mũ trên độ chênh lệch.) Thuật toán **Viterbi** tìm con đường có xác
suất cao nhất xuyên qua cái trellis các candidate này.

> ⚠️ **Reading note.** GraphHopper 11 **không** phụ thuộc vào một `hmm-lib` ngoài hay một class
> `ViterbiAlgorithm` (các phiên bản cũ thì có). Các kiểu HMM được nội bộ hoá vào package `matching` và phần
> Viterbi decode được **hand-inline** thành một label-setting kiểu priority-queue bên trong
> `computeViterbiSequence`. Nên hãy grep `HmmProbabilities` và `computeViterbiSequence`, chứ không phải
> `ViterbiAlgorithm`.

## 6.3 Pipeline: `MapMatching.match`

Một method điều phối toàn bộ:

```java
public MatchResult match(List<Observation> observations) {
    // 1) emission: snap each GPS point to several candidate edges
    List<List<Snap>> snapsPerObservation = filteredObservations.stream()
            .map(o -> findCandidateSnaps(o.getPoint().lat, o.getPoint().lon))
            .collect(Collectors.toList());                                    // :203–:205
    // 2) build a query graph that includes the virtual snap nodes
    queryGraph = QueryGraph.create(graph, ...);                              // :210
    // 3) turn snaps into directed candidate States, one trellis column per observation
    List<ObservationWithCandidateStates> timeSteps = createTimeSteps(...);   // :214
    // 4) the Viterbi decode → most probable sequence of States
    List<SequenceState<State, Observation, Path>> seq = computeViterbiSequence(timeSteps);  // :217
    // 5) stitch the chosen edges into a MatchResult
    MatchResult result = new MatchResult(prepareEdgeMatches(seq));           // :226
```
📌 `map-matching/src/main/java/com/graphhopper/matching/MapMatching.java:198`–`:226` (class ở `:68`, hằng số
tinh chỉnh transition `transitionProbabilityBeta = 2.0` ở `:73`). Năm bước: emission, query graph, trellis,
Viterbi, result.

## 6.4 Emission — các candidate snap

Với mỗi GPS point, tìm vài edge lân cận để snap vào (không chỉ cái gần nhất — cái gần nhất thường sai), rồi
sắp xếp chúng theo khoảng cách của snap:

```java
// findCandidateSnaps: collect snaps within a bounding box around the GPS point,
// create a Snap per candidate edge, sort by query distance
// ...sorted by Snap::getQueryDistance                                       // :320
```
📌 `MapMatching.java:294`–`:321`. Mỗi candidate sau đó trở thành một `State` **có hướng** — một snap cộng thêm
một chiều di chuyển — bởi một con đường có thể đi theo cả hai chiều và hai chiều đó là hai giả thuyết khác
nhau:

```java
candidates.add(new State(observation, split, virtualEdges.get(0), virtualEdges.get(1)));   // :361
candidates.add(new State(observation, split, virtualEdges.get(1), virtualEdges.get(0)));   // :362
```
📌 `MapMatching.java:329`–`:373` (`State` = snap + virtual edge incoming/outgoing,
`matching/State.java:40`; `Observation` = một GPS point, `matching/Observation.java:24`).

## 6.5 & 6.6 Transition và lượt Viterbi decode

Lượt Viterbi là một label-setting trên trellis: mỗi node của trellis giữ giá trị `minusLogProbability` tích
luỹ tốt nhất của nó (ta minimize negative-log-probability = maximize probability) và một back-pointer. Nó
seed cột đầu tiên bằng chi phí **emission**, rồi ở mỗi bước route giữa các candidate để chấm điểm
**transition**:

```java
// seed: emission cost of each first-column candidate
label.minusLogProbability = probabilities.emissionLogProbability(distance) * -1.0;            // :397
// step: actually route from each current candidate to each next candidate
List<Path> paths = router.calcPaths(queryGraph, fromNode, fromOutEdge, toNodes, toInEdges);   // :418
double transitionLogProbability =
        probabilities.transitionLogProbability(path.getDistance(), linearDistance);            // :423
double minusLogProbability = qe.minusLogProbability
        - probabilities.emissionLogProbability(to.getSnap().getQueryDistance())
        - transitionLogProbability;                                                             // :426
```
📌 `MapMatching.java:382`–`:456`. Để ý `router.calcPaths` ở `:418` — xác suất transition được tính bằng cách
*thực sự chạy một shortest-path query* (Chương 3!) giữa từng cặp candidate rồi so chiều dài route với khoảng
cách GPS đường thẳng. Map matching chính là routing được dùng như một probability oracle.

Hai xác suất này chính là model Newson–Krumm, và chúng thẳng thớm đến bất ngờ:

```java
public double emissionLogProbability(double distance) {
    return Distributions.logNormalDistribution(sigma, distance);          // :47  closer snap → more likely
}
public double transitionLogProbability(double routeLength, double linearDistance) {
    // Transition metric taken from Newson & Krumm.
    double transitionMetric = Math.abs(linearDistance - routeLength);
    return Distributions.logExponentialDistribution(beta, transitionMetric);  // :62  detour → less likely
}
```
📌 `map-matching/src/main/java/com/graphhopper/matching/HmmProbabilities.java:24`,`:46`–`:63`. `sigma` là sai
số GPS giả định (mét); `beta` chỉnh mức phạt nặng nhẹ cho một road detour không khớp với khoảng trống GPS. Các
back-pointer của Viterbi dựng lại chuỗi thắng cuộc, và `MatchResult` phơi ra các edge đã match, chiều dài đã
match, và merged path:

```java
public class MatchResult {
    public List<EdgeMatch> getEdgeMatches() { ... }   // :77
    public double getMatchLength() { ... }            // :91  ← the driver's real distance
    public Path getMergedPath() { ... }               // :102
```
📌 `map-matching/src/main/java/com/graphhopper/matching/MatchResult.java:30`–`:102`.

> 🧠 **Mental model:** snapping độc lập vào edge gần nhất hỏi "mỗi điểm ở đâu?" một cách cô lập nên bị nhiễu
> quăng quật. HMM thì hỏi "*chuỗi* vị trí nào giải thích tốt nhất *tất cả* các điểm, với ràng buộc rằng tài
> xế phải đi trên một con đường thật giữa chúng?" Số hạng transition — road distance ≈ GPS distance — chính
> là thứ ngăn đáp án khỏi nhảy dịch qua dải phân cách.

## 6.7 Lab 6 — match một trace

> 🧪 **Lab 6.** Chỉ đọc. Mục tiêu: thấy được lằn ranh emission/transition và match một synthetic trace. Ghi
> vào [`labs/lab06-matching.md`](labs/lab06-matching.md).

```bash
cd ~/Documents/learning/graphhopper
# confirm the two probabilities and the pipeline steps resolve:
sed -n '46,63p' map-matching/src/main/java/com/graphhopper/matching/HmmProbabilities.java
sed -n '198,226p' map-matching/src/main/java/com/graphhopper/matching/MapMatching.java

# run the module's own map-matching test to watch it match a real trace:
mvn -q -pl map-matching -Dtest=MapMatchingTest test | tail -20
```

**Kết quả kỳ vọng:** `HmmProbabilities.java:47` là **emission** phân phối chuẩn, `:62` là **transition** phân
phối mũ ("taken from Newson & Krumm"); `MapMatching.java:419` cho thấy `router.calcPaths(...)` nằm bên trong
bước transition (routing đóng vai probability oracle); và test của module chạy pass, match các GPX trace mẫu
lên graph. Ghi lại matched length so với chiều dài trace đầu vào — chúng phải xấp xỉ nhau.

## 6.8 Checkpoint

1. Vì sao snapping độc lập vào edge gần nhất lại sai? Nêu lỗi mà nó gây ra trên một con đường có dải phân cách.
2. Trong HMM, xác suất **emission** chấm điểm cái gì, và phân phối nào mô hình hoá nó?
3. Xác suất **transition** chấm điểm cái gì, và vì sao tính nó lại đòi phải chạy một *shortest-path
   query*?
4. Mỗi candidate trở thành *hai* `State`. Vì sao lại hai?
5. Lượt Viterbi minimize `minusLogProbability`. Vì sao lại negative log, và back-pointer cho bạn cái gì ở
   cuối cùng?

> Nếu #3 còn lung lay, đọc lại §6.5/§6.6. Nếu #1 còn lung lay, đọc lại §6.2.

## 🔌 Connect to your past (reconstructing the driver's trip)

Đây là chương ride-hailing được kể theo nghĩa đen. Điện thoại của tài xế phát ra dòng GPS nhiễu;
`MapMatching.match` biến dòng đó thành `MatchResult.getMatchLength()` — số kilômét thực sự đã chạy, cũng chính
là **fare** và **trip distance** của bạn. Số hạng transition tóm được một tài xế đi vòng xa hơn (road distance
sẽ không khớp với khoảng trống GPS trừ phi họ thực sự đã chạy quãng đó), và đó là cách bạn gắn cờ những chuyến
đi off-route. Và vì bước transition *chính là* một routing query của Chương 3, mọi thứ bạn học về họ
shortest-path cũng áp dụng ở đây — map matching là chính những thuật toán đó đội thêm chiếc mũ xác suất. Khi
Uber/Lyft hay GreenSM hiện "chuyến của bạn: 8.4 km, 22 min," một phép tính có hình dạng y hệt thế này đã tạo
ra con số 8.4.

**Next:** ta đã tính route, journey, và matched trace. Giờ tới chặng cuối — engine biến một chuỗi edge thành
các chỉ dẫn turn-by-turn và phục vụ tất cả qua web API của nó ra sao.
→ **[Chapter 07 — Navigation, Isochrones & the Web/Tiles Surface](07-navigation-isochrones-web.md)**
