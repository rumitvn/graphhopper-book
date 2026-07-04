# Chapter 04 — Profiles, Weighting & Custom Models

> **Goal:** Learn how you *shape* a route. After this chapter you can explain how a `Profile` binds a name
> to a `Weighting`, how the `CustomModel` DSL turns `speed`/`priority`/`distance_influence` statements into
> a real per-edge cost, and how the `EncodedValue` system (`EncodingManager`) packs per-edge attributes —
> road class, max weight, access — into bits the weighting reads back edge by edge. Pinned to **`11.0`**
> (`69e50f6`).

## 4.1 Why it matters

Chapter 3 showed the algorithms but treated `Weighting.calcEdgeWeight` as a black box that returns "the
cost of this edge." This chapter opens the box. That cost is where *all* the domain knowledge lives: a car
is fast on a motorway and forbidden on a footpath; a bus may use a bus-only lane a car can't; a heavy
vehicle can't cross a 3.5-tonne bridge. None of that is in the algorithm — it's in the weighting, and
GraphHopper lets you write it as configuration, not code, via **custom models**.

For you this is the most directly reusable chapter. Every "our vehicles are special" rule — VinBus on
bus-only infrastructure, an EV avoiding a low-clearance underpass, a ride-hailing car preferring big roads
for driver comfort — is a custom-model statement over an encoded value. You'll leave able to write them.

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

The chain: a `Profile` names a `Weighting`; for the default `custom` weighting, a `CustomModel` (your
`speed`/`priority` statements) is **compiled** into a class whose `calcEdgeWeight` reads **encoded values**
off each edge. Encoded values are the bit-packed per-edge attributes the `EncodingManager` laid down at
import time.

## 4.3 The `Profile` — a name bound to a cost

```java
public class Profile {
    // fields: name, weighting (default "custom"), turnCostsConfig, hints
    public String getWeighting() { ... }          // :89
    public CustomModel getCustomModel() {          // :105  stored inside hints under CustomModel.KEY
```
📌 `core/src/main/java/com/graphhopper/config/Profile.java:41`–`:107`. A profile is *just configuration*: a
name (validated at `:47`), a weighting type (`"custom"`, `"fastest"`, `"shortest"`…), whether it uses turn
costs (`hasTurnCosts`, `:109`–`:111`), and — for custom weighting — a `CustomModel` tucked into its hints.
The `car` profile in `config-example.yml` (§0.3) is exactly this, with its model in `car.json`.

## 4.4 `CustomWeighting` — the cost formula

The default weighting's formula is small enough to hold in your head; the class Javadoc *is* the spec:

```text
        distance
weight = ─────────────────────────  +  distance · distance_influence
         base_speed · speed_factor · priority
```
📌 `core/src/main/java/com/graphhopper/routing/weighting/custom/CustomWeighting.java:63`–`:73`. Read it as:
time (distance over effective speed), divided by a `priority` that lets you make a road *feel* longer or
shorter without lying about its speed, plus a distance term that trades detours against time. Per edge:

```java
public double calcEdgeWeight(EdgeIteratorState edgeState, boolean reverse) {
    double priority = edgeToPriorityMapping.get(edgeState, reverse);   // :116
    double seconds  = calcSeconds(distance, edgeState, reverse);       // :120
    double distanceCosts = distance * distanceInfluence;               // :124
    return seconds / priority + distanceCosts;                         // :126
}
// calcSeconds → edgeToSpeedMapping.get(edgeState, reverse)            // :130
```
📌 `CustomWeighting.java:114`–`:137`. Notice `edgeToPriorityMapping.get(edgeState, …)` and
`edgeToSpeedMapping.get(edgeState, …)` — these are the compiled statements from your model, evaluated
against *this* edge's encoded values.

## 4.5 The `CustomModel` DSL and how it's compiled

A `CustomModel` is three lists: `speed` statements, `priority` statements, and a scalar
`distance_influence`:

```java
private Double distanceInfluence;                    // :35
private List<Statement> speedStatements;             // :39
private List<Statement> priorityStatements;          // :40
```
📌 `web-api/src/main/java/com/graphhopper/util/CustomModel.java:30`–`:41`. In YAML you write them as
`if`/`else_if`/`multiply_by`/`limit_to` rules over encoded values:

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

Those statements aren't interpreted per edge — that would be far too slow. They are **compiled to Java
bytecode** at import time via Janino. `CustomModelParser` builds a subclass of `CustomWeightingHelper` and
wires its `getSpeed`/`getPriority` as the method references `CustomWeighting` calls:

```java
clazz = createClazz(...);              // :97   compile + cache the generated class
CustomWeightingHelper prio = clazz.getDeclaredConstructor()....newInstance();   // :113
return new CustomWeighting.Parameters(prio::getSpeed, prio::calcMaxSpeed,
                                      prio::getPriority, prio::calcMaxPriority, ...);  // :115
```
📌 `core/src/main/java/com/graphhopper/routing/weighting/custom/CustomModelParser.java:91`–`:124` (the
generated subclass template is at `:473`–`:498`; the base with the overridable stubs is
`CustomWeightingHelper.java:37`–`:58`). The `calcMaxSpeed`/`calcMaxPriority` bounds
(`CustomWeightingHelper.java:64`–`:91`) matter for §3.4/§3.6 — they give A*/LM their admissible upper bound
on speed.

> ⚠️ **The security boundary.** Your model is user-supplied text that becomes executing code, so GraphHopper
> constrains it hard: expressions are parsed by `ValueExpressionVisitor`, which whitelists a tiny set of
> methods (literally `Set.of("sqrt")`), rejects anything with trailing tokens, and extracts exactly which
> encoded values an expression may touch. 📌
> `core/.../weighting/custom/ValueExpressionVisitor.java:38`–`:42`,`:135`–`:157`. If you ever expose custom
> models to end users, this is the code that keeps "priority: `System.exit(0)`" from compiling.

> 💡 A custom-model change is **import-time**, not query-time (it changes the compiled weighting), and it's
> why you can't run CH with a per-request custom model — CH's weighting is frozen (§3.5). Flexible custom
> models run on the LM or flexible path. This is the §0.5 "delete `graph-cache/` and re-import" gotcha in
> disguise.

## 4.6 Encoded values — per-edge attributes in bits

The statements above read things like `road_class` and `max_weight`. Those are **encoded values**: named,
fixed-bit-width fields packed into each edge's record. The `Weighting` reads them through a lookup:

```java
public interface EncodedValueLookup {
    BooleanEncodedValue getBooleanEncodedValue(String key);   // :28
    DecimalEncodedValue getDecimalEncodedValue(String key);   // :30
    EnumEncodedValue<?> getEnumEncodedValue(String key, ...); // :34
```
📌 `core/src/main/java/com/graphhopper/routing/ev/EncodedValueLookup.java:22`–`:39`. Each `EncodedValue`
claims a slice of bits when the graph is built:

```java
int init(InitializerConfig init);   // :37  — asks the allocator for `usedBits`, gets a shift + mask
```
📌 `core/src/main/java/com/graphhopper/routing/ev/EncodedValue.java:28`–`:82`. A decimal value (like speed)
is stored scaled into an integer field; reading it back is what your compiled `speed` statement bottoms out
in:

```java
double getDecimal(boolean reverse, int edgeId, EdgeIntAccess edgeIntAccess);   // :20
```
📌 `core/src/main/java/com/graphhopper/routing/ev/DecimalEncodedValue.java:11`–`:46`. The concrete values are
declared with a `KEY` and a `create()` that fixes their bit budget — a great illustration of the
space/precision trade:

```java
// MaxWeight: 9 bits, 0.1-tonne resolution
public static DecimalEncodedValue create() {
    return new DecimalEncodedValueImpl(KEY, 9, 0, 0.1, ...);   // MaxWeight.java:~31
}
```
📌 `core/src/main/java/com/graphhopper/routing/ev/MaxWeight.java:27`–`:37` (see also `RoadClass.java:26`–`:35`
as an enum value and `Roundabout.java:20`–`:25` as a boolean). The **`EncodingManager`** is the registry
that owns them all and hands out non-overlapping bit slices:

```java
public class EncodingManager implements EncodedValueLookup {
    // Builder.add(ev): ev.init(edgeConfig); encodedValueMap.put(ev.getName(), ev);   :137
```
📌 `core/src/main/java/com/graphhopper/routing/util/EncodingManager.java:44`–`:45`,`:126`–`:166` (lookups
that throw on a missing key at `:225`–`:257`). Recall §0.4:
`setEncodedValuesString("car_access, car_average_speed")` is you telling this manager which values to pack —
and a custom model can only reference values that were packed.

## 4.7 Lab 4 — shape a route

> 🧪 **Lab 4.** Read-only + one custom request. Goal: change a route with a custom model, and trace the
> encoded values it reads. Record in [`labs/lab04-profiles.md`](labs/lab04-profiles.md).

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

**Expected:** `CustomWeighting.java:126` reads `return seconds / priority + distanceCosts;`;
`ValueExpressionVisitor.java:38` shows the `sqrt`-only method whitelist; and the custom request returns a
*different* distance/time than the plain `car` route (it avoids primary roads). Record both. (Custom models
need the flexible or LM path — hence `ch.disable`.)

## 4.8 Checkpoint

1. What does a `Profile` actually contain, and where does its `CustomModel` live?
2. Write the `CustomWeighting` cost formula from memory. What does `priority` let you do that changing
   `speed` wouldn't?
3. A custom model is user text that becomes executing code. Two mechanisms keep that safe — name them and
   the file they live in.
4. Why does a custom-model change force a re-import, and why can't it run on CH?
5. `road_class == MOTORWAY` — what *is* `road_class` at the storage level, and who guaranteed there are
   enough bits for it and every other encoded value?

> If #2 is shaky, re-read §4.4. If #5 is shaky, re-read §4.6.

## 🔌 Connect to your past (your vehicles are the custom model)

This is where your fleet's quirks become code you can write. A **bus-only lane** VinBus may use but a car
may not is a `priority` statement gating on an access encoded value. A **height- or weight-limited**
underpass an EV or a larger vehicle must avoid is a `priority: 0` when `max_height`/`max_weight` is below
threshold — exactly the `MaxWeight` value from §4.6. A ride-hailing preference for **bigger, smoother
roads** (nicer for the rider, easier for the driver) is `multiply_by` on `road_class`. And crucially: you
now know *why* those rules can't ride the CH fast path (their weighting is per-request), so you'd serve
them on the Landmarks path from §3.6. The "our vehicles are special" conversation you've had a hundred times
is, in GraphHopper, a short block of YAML over the right encoded value.

**Next:** we've done road routing top to bottom. Now the other network your apps live on — **public
transit**, where time itself is part of the graph. → **[Chapter 05 — Public Transit: GTFS & RAPTOR](05-public-transit-gtfs-raptor.md)**
