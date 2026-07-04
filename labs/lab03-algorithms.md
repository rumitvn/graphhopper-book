# Lab 3 — Dijkstra vs A* vs CH

Fill in during Chapter 3 §3.7.

## Same route, three algorithms

Route a fixed A→B and record how much of the graph each search touches.

| Algorithm | nodes visited (`getVisitedNodes()`) | time (ms) | same distance? |
|-----------|--------------------------------------|-----------|----------------|
| Dijkstra (bidirectional) | | | — |
| A* (bidirectional) | | | _expect yes_ |
| CH (`DijkstraBidirectionCH`) | | | _expect yes_ |

_Expected shape: A* visits fewer nodes than Dijkstra; CH visits **far** fewer — often 100–1000× — for the **same** optimal distance._

## Contraction Hierarchies preparation

| Quantity | Value |
|----------|-------|
| base edges (`graph.getEdges()`) | |
| shortcuts added by `PrepareContractionHierarchies` | |
| shortcut ratio (shortcuts / base edges) | _often ~0.5–1.5×_ |

## Notes
_Where is `Weighting.calcEdgeWeight` called in each algorithm? What does CH trade away to get its speed?_
