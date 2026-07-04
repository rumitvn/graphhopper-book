# Chapter 06 — Map-Matching: snapping GPS to roads

> **Goal:** Understand how a noisy GPS trace becomes the road path a driver *actually* took. After this
> chapter you can explain the Newson–Krumm **Hidden Markov Model** GraphHopper uses: candidate snaps per
> GPS point as **emission** probabilities, routing between candidates as **transition** probabilities, and
> the **Viterbi** pass that picks the single most likely sequence of edges. Pinned to **`11.0`** (`69e50f6`).
> This is the ride-hailing chapter.

## 6.1 Why it matters

GPS lies. In an urban canyon a fix can land 30 metres off, on the wrong side of a divided road, or on a
parallel street. If you snap each point independently to its nearest edge, you get a path that teleports
across the median and doubles back — useless for computing the distance a driver drove, the fare, or where
they actually are. Map-matching solves the *sequence* problem: given the whole noisy trace and the road
network, what is the most probable continuous path?

For ride-hailing this is foundational plumbing. Reconstructing the driver's real route from their GPS
breadcrumbs is how you compute trip distance and fare, detect off-route detours, and correct an ETA. It's
the same math whether you call it "trip reconstruction" or "map-matching."

## 6.2 Mental model: a Hidden Markov Model over the road graph

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

Two probabilities. **Emission**: how likely is it that the true position is *this* candidate edge, given
the GPS point landed where it did? (Closer snap → higher probability, a normal distribution on the snap
distance.) **Transition**: how likely is it that the driver went from candidate `a` to candidate `b`
between two GPS points? (If the *road* distance between them is close to the straight-line GPS distance →
plausible; if the road forces a huge detour → unlikely, an exponential penalty on the difference.) The
**Viterbi** algorithm finds the highest-probability path through this trellis of candidates.

> ⚠️ **Reading note.** GraphHopper 11 does **not** depend on an external `hmm-lib` or a `ViterbiAlgorithm`
> class (older versions did). The HMM types are internalized into the `matching` package and the Viterbi
> decode is **hand-inlined** as a priority-queue label-setting inside `computeViterbiSequence`. So grep for
> `HmmProbabilities` and `computeViterbiSequence`, not `ViterbiAlgorithm`.

## 6.3 The pipeline: `MapMatching.match`

One method orchestrates the whole thing:

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
📌 `map-matching/src/main/java/com/graphhopper/matching/MapMatching.java:198`–`:226` (class at `:68`, the
transition tuning constant `transitionProbabilityBeta = 2.0` at `:73`). Five steps: emission, query graph,
trellis, Viterbi, result.

## 6.4 Emission — candidate snaps

For each GPS point, find several nearby edges to snap to (not just the closest — the closest is often
wrong), and sort them by how far the snap is:

```java
// findCandidateSnaps: collect snaps within a bounding box around the GPS point,
// create a Snap per candidate edge, sort by query distance
// ...sorted by Snap::getQueryDistance                                       // :320
```
📌 `MapMatching.java:294`–`:321`. Each candidate then becomes a **directed** `State` — a snap plus a
direction of travel — because a road can be traversed either way and the two directions are different
hypotheses:

```java
candidates.add(new State(observation, split, virtualEdges.get(0), virtualEdges.get(1)));   // :361
candidates.add(new State(observation, split, virtualEdges.get(1), virtualEdges.get(0)));   // :362
```
📌 `MapMatching.java:329`–`:373` (`State` = snap + incoming/outgoing virtual edge,
`matching/State.java:40`; `Observation` = a GPS point, `matching/Observation.java:24`).

## 6.5 & 6.6 Transition and the Viterbi decode

The Viterbi pass is a label-setting over the trellis: each trellis node holds its best cumulative
`minusLogProbability` (we minimize negative-log-probability = maximize probability) and a back-pointer.
It seeds the first column with **emission** cost, then for each step routes between candidates to score the
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
📌 `MapMatching.java:382`–`:456`. Note `router.calcPaths` at `:418` — the transition probability is computed
by *actually running a shortest-path query* (Chapter 3!) between each pair of candidates and comparing the
route length to the straight-line GPS distance. Map-matching is routing used as a probability oracle.

The two probabilities are the Newson–Krumm model, and they're refreshingly literal:

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
📌 `map-matching/src/main/java/com/graphhopper/matching/HmmProbabilities.java:24`,`:46`–`:63`. `sigma` is the
assumed GPS error (metres); `beta` tunes how harshly a road detour that doesn't match the GPS gap is
penalized. The Viterbi back-pointers reconstruct the winning chain, and `MatchResult` exposes the matched
edges, the matched length, and the merged path:

```java
public class MatchResult {
    public List<EdgeMatch> getEdgeMatches() { ... }   // :77
    public double getMatchLength() { ... }            // :91  ← the driver's real distance
    public Path getMergedPath() { ... }               // :102
```
📌 `map-matching/src/main/java/com/graphhopper/matching/MatchResult.java:30`–`:102`.

> 🧠 **Mental model:** independent nearest-edge snapping asks "where is each point?" in isolation and gets
> whipsawed by noise. The HMM asks "what *sequence* of positions best explains *all* the points, given that
> the driver had to travel a real road between them?" The transition term — road distance ≈ GPS distance —
> is what stops the answer from teleporting across a median.

## 6.7 Lab 6 — match a trace

> 🧪 **Lab 6.** Read-only. Goal: see the emission/transition split and match a synthetic trace. Record in
> [`labs/lab06-matching.md`](labs/lab06-matching.md).

```bash
cd ~/Documents/learning/graphhopper
# confirm the two probabilities and the pipeline steps resolve:
sed -n '46,63p' map-matching/src/main/java/com/graphhopper/matching/HmmProbabilities.java
sed -n '198,226p' map-matching/src/main/java/com/graphhopper/matching/MapMatching.java

# run the module's own map-matching test to watch it match a real trace:
mvn -q -pl map-matching -Dtest=MapMatchingTest test | tail -20
```

**Expected:** `HmmProbabilities.java:47` is the normal-distribution **emission**, `:62` the
exponential-distribution **transition** ("taken from Newson & Krumm"); `MapMatching.java:419` shows
`router.calcPaths(...)` inside the transition step (routing as a probability oracle); and the module's tests
pass, matching sample GPX traces onto the graph. Record the matched length vs the input trace length —
they should be close.

## 6.8 Checkpoint

1. Why is independent nearest-edge snapping wrong? Give the failure it produces on a divided road.
2. In the HMM, what does the **emission** probability score, and what distribution models it?
3. What does the **transition** probability score, and why does computing it require running a *shortest-path
   query*?
4. Each candidate becomes *two* `State`s. Why two?
5. The Viterbi pass minimizes `minusLogProbability`. Why negative log, and what does the back-pointer give
   you at the end?

> If #3 is shaky, re-read §6.5/§6.6. If #1 is shaky, re-read §6.2.

## 🔌 Connect to your past (reconstructing the driver's trip)

This is the ride-hailing chapter made literal. A driver's phone streams noisy GPS; `MapMatching.match` turns
that stream into `MatchResult.getMatchLength()` — the real kilometres driven, which is your **fare** and
your **trip distance**. The transition term catches a driver who took a longer detour (the road distance
won't match the GPS gap unless they really drove it), which is how you'd flag off-route trips. And because
the transition step *is* a Chapter 3 routing query, everything you learned about the shortest-path family
applies here too — map-matching is those algorithms wearing a probabilistic hat. When Uber/Lyft or GreenSM
shows "your trip: 8.4 km, 22 min," a computation shaped exactly like this produced the 8.4.

**Next:** we've computed routes, journeys, and matched traces. Now the last mile — how the engine turns an
edge sequence into turn-by-turn instructions and serves everything over its web API.
→ **[Chapter 07 — Navigation, Isochrones & the Web/Tiles Surface](07-navigation-isochrones-web.md)**
