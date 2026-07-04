# Lab 0 — Build it & get a first route

Fill in during Chapter 0 §0.6.

## Pinned clone

| Check | Value | Expected |
|-------|-------|----------|
| `git describe --tags` | | `11.0` |
| `git rev-parse --short HEAD` | | `69e50f6` |
| Java version (`java -version`) | | 17+ |
| Maven modules (count in root `pom.xml`) | | (record it) |

## Build & run

| Step | Result |
|------|--------|
| `mvn -q -DskipTests clean install` succeeded? | |
| Import time for the extract you chose | |
| Server up on `http://localhost:8989`? | |
| `graph-cache/` size after import | |

## First route

| Field (from `query_route/query.py A B`) | Value |
|-----------------------------------------|-------|
| distance (km) | |
| time (min) | |
| # instructions | |

## Notes
_Which module holds the routing algorithms? Which holds the web server? Where did the graph get written to disk?_
