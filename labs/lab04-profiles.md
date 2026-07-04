# Lab 4 — Shape a route with a custom model

Fill in during Chapter 4 §4.6.

## Baseline vs custom

Route a fixed A→B with the stock `car` profile, then with a `custom_model` that avoids
a road class (e.g. down-weight `primary`) or caps speed.

| Run | distance (km) | time (min) | notably different segment? |
|-----|---------------|------------|----------------------------|
| stock `car` | | | — |
| custom model | | | |

## The custom-model statements you wrote

```yaml
# paste your priority / speed statements here
```

## Encoded values in play

| EncodedValue | Where read (`file:line`) | Used by your model? |
|--------------|--------------------------|---------------------|
| `RoadClass` | | |
| `MaxWeight` / access | | |
| `RoadAccess` | | |

## Notes
_How does a `Profile` connect a name to a `Weighting`? Why must a custom-model change re-import (or block CH)?_
