# Lab 5 — A public-transit query

Fill in during Chapter 5 §5.6.

## Import a GTFS feed

| Step | Result |
|------|--------|
| GTFS feed used (agency/city) | |
| import succeeded with a `pt` profile? | |
| # stops / # trips (from the feed) | |

## One `pt` journey

Query `/route?profile=pt&pt.earliest_departure_time=…` between two stops.

| Field | Value |
|-------|-------|
| total travel time | |
| # legs | |
| # transfers | _RAPTOR minimises this_ |
| walk time (access + egress) | |

## The multi-criteria shape

| Criterion tracked by `MultiCriteriaLabelSetting` | Seen in your result? |
|--------------------------------------------------|----------------------|
| arrival time | |
| number of transfers | |
| walking distance/time | |

## Notes
_Why is a transit graph "time-expanded"? What does a `Label` dominate another `Label` on? Map this to BusMap/VinBus._
