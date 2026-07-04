# Chapter 00 — Environment & Java Refresher

> **Goal:** End this chapter with a *readable* copy of GraphHopper pinned to **`11.0`** (`69e50f6`), a
> Maven build that produces a runnable server, that server answering a real `/route` on a city-sized
> extract, and fluency in the four idioms the codebase assumes you already know: the **fluent
> `GraphHopper`/`GHRequest` API**, the **Maven multi-module** layout, **flat-array `DataAccess` storage**,
> and the **two-phase "import then query"** lifecycle. You won't read every module — you'll learn to *read*
> any of them.

## 0.1 Why it matters

If you open `core/src/main/java/com/graphhopper/routing/Dijkstra.java` cold, it will look deceptively
simple — a priority queue and a loop. The confusion isn't in the algorithm; it's in the *scaffolding*
around it: a `Weighting` you didn't define, an `EdgeExplorer` that iterates something that isn't a
collection, an integer `edgeId` where you expected an object, and a graph that lives in `byte[]` segments
instead of a `Map<Node, List<Edge>>`. None of that is hard once you know what *kind* of thing each is.
This chapter front-loads those idioms so the rest of the book is about *routing*, not plumbing.

The other reason: GraphHopper is built to answer a route in **under a millisecond** over a
continent-sized graph, on a server with a fixed memory budget. That performance discipline — pack the
graph into flat arrays, preprocess once, then do read-only queries — shapes every design decision you're
about to read. If you've ever cared about latency and memory on a backend that real users hit, this
framing will feel like home.

## 0.2 Get the source, pinned

We pin to a fixed release tag so every `file:line` in this book resolves. Clone shallow at the tag:

```bash
cd ~/Documents/learning   # or wherever you keep the book
git clone --depth 1 --branch 11.0 \
  https://github.com/graphhopper/graphhopper.git graphhopper
cd graphhopper
git rev-parse --short HEAD     # → 69e50f6
git describe --tags            # → 11.0
```

> 📁 Note the tag has **no `v` prefix** — it is `11.0`, not `v11.0`. `git describe --tags` prints exactly
> `11.0`. Use this ref and your line numbers will match this book.

There are no submodules to chase — GraphHopper vendors nothing heavy in git. The only large inputs are the
OSM extract and (in Chapter 5) a GTFS feed, which you download separately and which `.gitignore` keeps out.

## 0.3 The environment: Java 17 and Maven

GraphHopper is emphatic about its Java version. From the build metadata:

```xml
<maven.compiler.target>17</maven.compiler.target>
```
📌 `pom.xml:19` (and `<release>17</release>` in the compiler plugin at `pom.xml:187`; the README states
"≥ Java 17" at `README.md:106`). Java **17 or newer** — earlier JDKs will not compile it.

It is a **Maven multi-module** project. The root `pom.xml` lists the modules this book tours:

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
📌 `pom.xml:60`–`:71`. The parent artifact is `graphhopper-parent`, version `11.0-SNAPSHOT`, packaging
`pom` (`pom.xml:6`–`:10`).

> 🧠 **Mental model:** when you want to know where something lives, map the concern to a module first.
> *Algorithm?* `core`. *HTTP endpoint?* `web-bundle/.../resources/`. *The `GHRequest` you pass in?*
> `web-api`. *Transit?* `reader-gtfs`. You'll almost never grep the whole tree — you grep one module.

Build everything (this compiles the modules and produces the server jar):

```bash
mvn -q -DskipTests clean install       # first run downloads deps; a few minutes
```

Then run the server. The fastest path uses the bundled tiny country **Andorra**, which ships in the repo:

```bash
# config-example.yml is at the repo root; andorra.osm.pbf is bundled under core/files/
java -D"dw.graphhopper.datareader.file=core/files/andorra.osm.pbf" \
     -jar web/target/graphhopper-web-*.jar server config-example.yml
# → open http://localhost:8989/  (a Leaflet map you can click to route on)
```

The server entry point is a Dropwizard `Application`:

```java
public final class GraphHopperApplication extends Application<GraphHopperServerConfiguration> {
    public static void main(String[] args) throws Exception {
        new GraphHopperApplication().run(args);
    }
```
📌 `web/src/main/java/com/graphhopper/application/GraphHopperApplication.java:34`–`:38`. It listens on
`8989` and the config it reads (`config-example.yml`) declares `graph.location: graph-cache` (line 6), the
`profiles:` list (line 31 — the first is `car`), and the `profiles_ch:` block (line 86) that turns on
Contraction Hierarchies. We'll unpack all of those; for now, get a green `/route`.

> 💡 You can read and grep the entire codebase with **no build at all**. Only the labs that *run* a query
> need the server. Don't let a slow first `mvn install` block you from reading source.

## 0.4 Idiom 1 — the fluent façade: `GraphHopper`, `GHRequest`, `GHResponse`

The public API is a **builder**. You configure one `GraphHopper` object with chained setters, call
`importOrLoad()`, and then ask it for routes. The canonical example is the book's Rosetta stone:

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
Every setter returns nothing here for readability, but the API is fluent — `GraphHopper.setOSMFile`
(`GraphHopper.java:350`), `setGraphHopperLocation` (`:333`), `setEncodedValuesString` (`:144`),
`setProfiles` (`:273`) — and the `GraphHopper` façade class itself is `GraphHopper.java:85`.

A route is a request object in, a response object out:

```java
GHRequest req = new GHRequest(42.508552, 1.532936, 42.507508, 1.528773)
        .setProfile("car").setLocale(Locale.US);
GHResponse rsp = hopper.route(req);
ResponsePath path = rsp.getBest();
double distanceMeters = path.getDistance();   // :148
long timeMillis       = path.getTime();
```
📌 `RoutingExample.java:51`–`:73`. The three value objects you'll meet on every page live in `web-api`:

- **`GHRequest`** — points + profile + options. `GHRequest.java:38`; constructors at `:51/:62/:66/:81`;
  the fluent `addPoint` returns `this` (`:99`–`:104`), `setProfile` at `:168`.
- **`GHResponse`** — the best path plus alternatives: `GHResponse.java:32`; `getBest()` returns
  `responsePaths.get(0)` (`:48`–`:53`); `hasErrors()` at `:94`.
- **`ResponsePath`** — one route: `ResponsePath.java:34`; `getPoints()` (`:99`), `getDistance()` (`:148`).

> 🧠 **Mental model:** `GraphHopper` is a *façade*. It hides the graph, the location index, the CH graphs
> and the landmarks behind two verbs — `importOrLoad()` (build or open) and `route()` (ask). The whole web
> layer (Chapter 1) is just this API reached over HTTP.

## 0.5 Idiom 2 — the two-phase lifecycle: import once, query many

The single most important shape in GraphHopper is that **preprocessing and querying are different
phases**. `importOrLoad()` says it out loud:

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
📌 `GraphHopper.java:793`–`:801`. The first run parses the `.osm.pbf`, builds the graph, runs the heavy
Contraction-Hierarchies / Landmarks *preparation* (Chapter 3), and writes everything to the
`graph-cache/` directory. Every run after that just **loads** that directory — which is why a warm start
is instant and queries never touch OSM again.

> 💡 If you change a profile, an encoded value, or the OSM file, you must **delete `graph-cache/`** and
> re-import. A stale cache is the #1 "why didn't my change take effect?" gotcha. (Chapter 4 explains why
> a `CustomModel` edit is import-time, not query-time.)

## 0.6 Idiom 3 — the graph is flat arrays, not objects

Here is the idiom that surprises app developers most. GraphHopper does **not** store the road network as
`Node` and `Edge` objects. It stores it as **primitive arrays of bytes**, addressed by integer id, behind
a `DataAccess`:

```java
public interface DataAccess extends Closeable {
    void setInt(long bytePos, int value);   // :37
    int  getInt(long bytePos);              // :42
    boolean loadExisting();                 // :105
```
📌 `core/src/main/java/com/graphhopper/storage/DataAccess.java:28`. A node is an `int`; an edge is an
`int`; reading "the distance of edge 42" is an *offset computation into a byte array*, not a field access
on an object. There are two implementations, chosen by `DAType`:

- **`RAMDataAccess`** — on-heap `byte[][] segments` (`RAMDataAccess.java:35`–`:36`). The default.
- **`MMapDataAccess`** — memory-mapped files, so a continent-sized graph never fully enters the heap:

```java
buf = raFile.getChannel().map(
        allowWrites ? FileChannel.MapMode.READ_WRITE : FileChannel.MapMode.READ_ONLY, offset, byteCount);
```
📌 `core/src/main/java/com/graphhopper/storage/MMapDataAccess.java:163`–`:164` (the class at `:49`,
`DAType.MMAP` at `DAType.java:49`). This is the same "operate on a mapped buffer, don't `memcpy` the world
into your address space" discipline you'd use for a large read-mostly dataset.

> 🧠 **Mental model:** every "graph" thing is an `int` id and a byte offset. When Chapter 2 shows an
> `EdgeIterator`, it isn't iterating a `List` — it's advancing a cursor over these flat arrays. Hold that
> and the storage layer stops being mysterious.

## 0.7 Idiom 4 — encoded values: per-edge attributes packed into bits

The last idiom: the properties a route cares about — is this road accessible to a car? what's its average
speed? its road class? — are stored per edge as **encoded values**, small bit-packed fields inside the
edge record. You configured two of them in §0.4 with
`setEncodedValuesString("car_access, car_average_speed")`. The `Weighting` (Chapter 3) reads them back
edge by edge to compute a cost. You don't need the encoder internals yet; just recognize the shape: an
`EncodedValue` is a named, bit-width-fixed accessor into the edge's flat storage, resolved through an
`EncodingManager`. Chapter 4 is where this becomes your main tool.

## 0.8 Lab 0 — build it and get a first route

> 🧪 **Lab 0.** Goal: confirm your clone is pinned, the build is green, and the server answers a real
> route. Record results in [`labs/lab00-build.md`](labs/lab00-build.md).

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

**Expected:** `git describe` prints `11.0`; the module count is `10`; the first server start logs an OSM
import and CH preparation, then "Started server" on port `8989`; and `query.py` prints one line with a
distance in kilometres, a time in minutes, and a handful of instructions. Write the import time and the
`graph-cache/` size into your lab note — you'll compare a warm (load-only) restart against it.

## 0.9 Checkpoint

1. Why does this book pin to a tag *and* a SHA instead of tracking `master`? What exact string does
   `git describe --tags` print?
2. You want to find the HTTP endpoint that handles `/route`. Which *module* do you look in, and which
   holds the `GHRequest` class you pass to it?
3. What are the two phases `importOrLoad()` chooses between, and what lives in `graph-cache/`?
4. A node and an edge are each just an `int`. What actually holds "the distance of edge 42", and what are
   the two `DataAccess` implementations that back it?
5. Which Java version is mandatory, and which two lines in `pom.xml` pin it?

> If #3 is shaky, re-read §0.5. If #4 is shaky, re-read §0.6.

## 🔌 Connect to your past (transit & ride-hailing backends)

Two bridges that recur through the whole book:

- **Transit apps (BusMap / VinBus).** A transit backend is exactly this shape: import a static feed once
  (there, GTFS instead of OSM), preprocess it into a fast query structure, then serve read-only journey
  queries. GraphHopper's import-then-query lifecycle (§0.5) *is* how you'd structure a stop-and-schedule
  service, and Chapter 5 shows GraphHopper doing precisely that with `reader-gtfs`.
- **Ride-hailing / navigation.** Every time this book says "`hopper.route(req)` returns a `ResponsePath`",
  read it as "the routing microservice answered the ETA/dispatch query your app made." The fluent
  `GHRequest` → `GHResponse` boundary is the same contract your app already has with whatever routing
  service it calls today — you're about to see the other side of it.

**Next:** with the idioms and a running server in hand, let's see the whole machine at once — the module
map, and one `/route` request's journey from HTTP to answer. → **[Chapter 01 — Mental Model & the Repo Map](01-mental-model-and-the-repo-map.md)**
