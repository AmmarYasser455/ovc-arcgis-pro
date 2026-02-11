# Changelog

## [3.0.0] – 2026-02-11

### Performance
- **Road Dangle Checker rewritten with O(n) spatial hashing** — replaces the
  O(n²) nested-loop algorithm.  Same Giza dataset (8,981 roads, 17,962
  endpoints) drops from **48 minutes → ~3 seconds** (~1,000× faster).

### Bug Fixes
- **Fixed dangle output coordinates** — projected UTM coordinates were being
  written into a geographic CRS output feature class, causing dangle points
  to appear at completely wrong locations (or off-map).  Now correctly maps
  back to original CRS.

### New Tools
- **Road Disconnected Segment Checker** — finds road segments where BOTH
  endpoints are dangles (completely isolated from the network).  Output is
  polyline features for easy map visualization.
- **Road Self-Intersection Checker** — finds roads that cross themselves
  (a common digitization error).  Output is point features at the
  crossing locations.

### Improvements
- Shared `_auto_project_roads()` helper eliminates duplicated projection
  code across all road tools.
- Shared `_add_to_map()` helper for consistent postExecute behavior.
- Road QC engine (`checks/road_qc/engine.py`) is pure Python with no
  arcpy dependency — maximum performance and testability.
- Version bumped to 3.0.0 to match OVC Python library.
- Cross-repo parity with OVC v3.0.0 (local-data-only, same checks).

---

## [1.1.0] – 2025-01-XX

### Performance
- **Adaptive spatial index cell sizing** – `SpatialIndex` now exposes
  `compute_optimal_cell_size()` class method; building overlap checker and
  road-conflict checker auto-tune cells to ~2-3× the average feature extent
  instead of using a hard-coded 100 m cell size.
- **Batch road buffering** – `BuildingRoadConflictChecker._find_conflicts()`
  pre-buffers all roads in a single pass before querying the spatial index,
  avoiding repeated per-road buffer calls during the intersection loop.

### New Tools
- **Road Dangle Checker** – Fully implemented `RoadDangleChecker` tool that
  detects dangling endpoints in road networks (endpoints not snapped to any
  other road within a configurable tolerance). Auto-projects to UTM when
  input is in geographic coordinates.

### Improvements
- `SpatialIndex` class docstring expanded with usage guidance.
- `OVCToolbox.pyt` version bumped to 1.1.0.
- `RoadDangleChecker` registered in the toolbox tools list.

---

## [1.0.0] – 2024-XX-XX

### Initial Release
- Building Overlap Checker with duplicate/partial/sliver classification.
- Building-Road Conflict Checker with configurable buffer distance.
- Auto-projection to UTM for geographic inputs.
- Grid-based spatial indexing (`SpatialIndex`).
- ArcGIS Pro UI integration: progress bars, auto-add to map, derived outputs.
