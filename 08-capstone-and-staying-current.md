# Chapter 08 — Capstone & Staying Current

> **Goal:** Become self-sufficient in this codebase. After this chapter you'll have shipped three small
> capstones (a custom profile, an isochrone, a real-city transit query), read a merged GraphHopper PR
> without hand-holding, and learned the exact procedure to re-sync this book when you re-pin to a newer
> tag. Pinned to **`11.0`** (`69e50f6`).

## 8.1 Why it matters

A book you can only follow with the author narrating isn't understanding — it's tourism. This chapter
removes the narrator. The capstones force you to *combine* chapters (a custom model from Chapter 4 shaping
an algorithm from Chapter 3, served over an endpoint from Chapter 7); reading a PR forces you to navigate
the code cold; and re-pinning teaches you that the book is a *method*, not a snapshot — the line numbers
drift, but the map you built of the engine doesn't.

## 8.2 Three capstones

Do them in order; each leans on the last.

**Capstone 1 — a custom profile end to end (Chapters 2–4, 7).** Add a profile that a real fleet would want:
an EV or bus that avoids a road class and respects a weight limit. In your `config-example.yml`, add a
profile with a `custom_model`, delete `graph-cache/`, re-import, and query it both ways:

```yaml
profiles:
  - name: bus
    custom_model:
      priority:
        - if: road_class == MOTORWAY
          multiply_by: 0.0        # buses off the motorway
        - if: max_weight < 7.5    # avoid bridges under 7.5t
          multiply_by: 0.0
      speed:
        - if: true
          limit_to: 60
```

Route the same A→B with `profile=car` and `profile=bus`; confirm the paths differ and that the difference
matches your rules. **Success:** you can point at the `road_class`/`max_weight` encoded values (§4.6) your
rules read and explain why this profile can't ride CH (§3.5).

**Capstone 2 — build and render an isochrone (Chapters 3, 7).** Call `/isochrone` for 5, 10, and 15 minutes
from one point; overlay the three polygons on a map (the built-in web UI at `http://localhost:8989/` or any
GeoJSON viewer). **Success:** you can explain why an isochrone is a shortest-path *tree* (`ShortestPathTree`,
§7.5), not a set of independent routes, and why the 15-min polygon contains the 5-min one.

**Capstone 3 — a real city's transit (Chapter 5).** Download a real GTFS feed (your own city if it
publishes one — a great BusMap/VinBus tie-in), import it with a `pt` profile, and plan a journey with a
transfer. **Success:** you can read the returned legs, count the transfers, and name the `Label` criteria
(§5.5) the search traded off to choose that itinerary.

## 8.3 Read a merged PR unaided

Pick a recently merged GraphHopper PR that touches routing, transit, or map-matching (the GitHub repo's
"Closed / Merged" PR list). Before reading the description, answer from the diff alone:

1. Which **module(s)** does it change? (Map it to Chapter 1's module table.)
2. What is the **one core `file:line`** where the behaviour actually changes — the load-bearing hunk, not
   the test or the changelog?
3. Which **test** proves the new behaviour, and what input would have failed before?

Then read the description and compare. If your three answers match the author's intent, you can read this
codebase. If not, the *gap* is your next reading target — usually a chapter you skimmed.

> 💡 A good first PR to practice on is anything touching `CustomWeighting`, `MultiCriteriaLabelSetting`, or a
> new `EncodedValue` — all three are chapters you've read, so you're checking comprehension, not learning
> cold.

## 8.4 Re-pinning: re-sync this book to a newer tag

When you want to move to a newer release, the book's citations will drift. Here's the exact re-sync:

```bash
cd ~/Documents/learning/graphhopper
git fetch --tags
git checkout <new-tag>                 # e.g. 12.0 when it ships
git rev-parse --short HEAD             # record the new short SHA
```

Then re-verify the **Key files** index in [`reference/glossary.md`](reference/glossary.md) first — it's the
spine. For each row, confirm the symbol still lives at the cited line:

```bash
# spot-check a few load-bearing citations against the new checkout:
sed -n '460,469p' core/src/main/java/com/graphhopper/util/GHUtility.java        # calcEdgeWeight choke
sed -n '295p'     core/src/main/java/com/graphhopper/routing/AbstractBidirCHAlgo.java  # CH upward rule
sed -n '225,244p' reader-gtfs/src/main/java/com/graphhopper/gtfs/MultiCriteriaLabelSetting.java  # dominates
```

If a symbol moved, update its `file:line` in the glossary and in the chapter that cites it, and update the
`PINNED` tag + inline short SHA in `site_src/build_site.py` and every chapter's Goal callout. Then rebuild:

```bash
cd ~/Documents/learning/graphhopper-book
python3 site_src/build_site.py         # → 11 pages + handbook.html
```

> 🧠 **Mental model:** the *structure* of GraphHopper — import/store/query/shape, the algorithm family, the
> custom-model + encoded-value system, the transit label-setting, the HMM matcher — is remarkably stable
> across releases. Re-pinning almost never invalidates a *concept*; it just nudges line numbers. That's the
> whole point of learning the engine from the source: the map survives the version bump.

## 8.5 Lab 8 — the capstone log

> 🧪 **Lab 8.** Goal: record the three capstones, one PR read, and one re-verify pass. Record in
> [`labs/lab08-pr.md`](labs/lab08-pr.md).

```bash
# after the three capstones, re-verify against a fresh checkout (or the current pin):
cd ~/Documents/learning/graphhopper
git describe --tags && git rev-parse --short HEAD
# then work through the PR-reading questions in §8.3 against a real merged PR.
```

**Expected:** three capstones done (custom `bus` profile re-routes; three nested isochrones render; a
real-GTFS journey with a transfer returns); one merged PR read with your three answers matching intent; and
a re-verify pass confirming (or correcting) a handful of glossary citations.

## 8.6 Checkpoint

1. Your `bus` profile avoids motorways and light bridges. Which two encoded values does it read, and why
   must it run off the CH fast path?
2. Why is an isochrone a shortest-path *tree*, and why does the 15-minute polygon contain the 5-minute one?
3. Reading a PR cold, what three questions do you answer from the *diff* before reading the description?
4. After re-pinning to a new tag, which single file in this book do you re-verify *first*, and why?
5. What survives a version bump unchanged — the line numbers, or the mental model? What does that tell you
   about how to study a codebase?

> If any capstone is shaky, re-read the chapter it draws on (1→§4, 2→§7.5, 3→§5.5).

## 🔌 Connect to your past (you can now read your own routing stack)

You started this book to get a stronger baseline in map technology and route-finding for BusMap, VinBus, and
ride-hailing. You now have more than a baseline: you can trace a route request from HTTP to algorithm and
back (Ch 1), explain the graph the map becomes (Ch 2), pick the right shortest-path algorithm for a
latency/flexibility trade-off (Ch 3), shape routes with custom models for your fleet (Ch 4), read a transit
journey planner as production code (Ch 5), reconstruct a driver's real trip from GPS (Ch 6), and name the
exact object and endpoint your apps consume (Ch 7). The next time a routing decision comes up at work —
"why is this ETA wrong?", "can we make buses avoid this street?", "how do we compute trip distance from GPS?"
— you won't reach for intuition. You'll reach for the file and line. That's the whole point of reading from
the source.

*A RumitX publication · [rumitx.com](https://rumitx.com) · maps, routing & human-centric mobility.*
