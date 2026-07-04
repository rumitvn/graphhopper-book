# Lab 6 — Match a GPS trace

Fill in during Chapter 6 §6.6.

## Synthetic trace → road path

Take a known route's geometry, jitter the points a little, feed them to `MapMatching`.

| Quantity | Value |
|----------|-------|
| # observations (input GPS points) | |
| # states considered (candidates) | |
| matched length (m) | |
| matched vs original distance error | _expect small_ |

## The HMM split

| Probability | What it scores | `file:line` |
|-------------|----------------|-------------|
| emission | how close a candidate snap is to the GPS point | |
| transition | how plausible the route between two candidates is | |

## Notes
_Why not just snap each point to the nearest edge independently? What breaks, and how does the Viterbi pass fix it? Map this to reconstructing a ride-hailing driver's actual path for distance/fare._
