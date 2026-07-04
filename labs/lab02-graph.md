# Lab 2 — Read the graph

Fill in during Chapter 2 §2.6.

## The graph, sized

| Quantity | Value |
|----------|-------|
| `graph.getNodes()` | |
| `graph.getEdges()` | |
| avg edges per node (edges·2 / nodes) | _expect ~2–3 for road networks_ |

## Sweep one node

Pick a node id; walk its edges with an `EdgeExplorer`.

| Edge | `getEdge()` | adjNode | distance (m) | is a shortcut? |
|------|-------------|---------|--------------|----------------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

## Storage

| Check | Value | Expected |
|-------|-------|----------|
| `DataAccess` type used (RAM vs MMAP) | | RAM by default |
| bytes-per-edge in `BaseGraph` header | | (record it) |

## Notes
_Why is the graph flat arrays and not `Node`/`Edge` objects? What does an `EdgeIteratorState` actually hold?_
