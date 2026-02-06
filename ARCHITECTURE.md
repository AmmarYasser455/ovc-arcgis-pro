# Architecture Overview

Technical documentation for the OVC (Overlap Violation Checker) ArcGIS Pro Python Toolbox.

## Design Philosophy

OVC is designed with three core principles:

1. **Native Integration** – Runs entirely within ArcGIS Pro using only ArcPy
2. **Maintainability** – Separation between tool interface and processing logic
3. **Performance** – Spatial indexing and efficient geometry operations

---

## Why a Python Toolbox (.pyt)?

A Python Toolbox was chosen over other options for several reasons:

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Python Toolbox (.pyt) | Single file distribution, native ArcGIS integration, full Python control | Requires Python knowledge to modify | ✅ Selected |
| Script Tool (.tbx) | GUI-based parameter editing | Limited customization, binary format | ❌ |
| ArcPy Script | Simple to run | No tool interface, no validation | ❌ |
| Add-in | Rich UI possibilities | Complex deployment, version-specific | ❌ |

**Key advantages of .pyt:**
- All code in a single distributable file (with supporting modules)
- Full control over parameter validation and tool behavior
- Native background processing support
- Integrates with Geoprocessing History and ModelBuilder

---

## Module Architecture

```
OVCToolbox.pyt          ← Tool definitions, parameters, execution flow
    │
    ├── core/           ← Reusable spatial processing logic
    │   ├── config.py       Configuration dataclasses
    │   ├── geometry.py     Geometry utilities (area, intersection, validation)
    │   └── spatial_ops.py  Spatial index and extent operations
    │
    ├── checks/         ← QC check implementations
    │   ├── building_overlap.py      Overlap detection algorithm
    │   └── building_road_conflict.py Buffer conflict detection
    │
    └── utils/          ← Helper utilities
        ├── cursor_helpers.py   Data access wrappers
        └── messaging.py        Progress tracking and logging
```

### Layer Responsibilities

| Layer | Purpose | Dependencies |
|-------|---------|--------------|
| `OVCToolbox.pyt` | Tool UI, parameter handling, execution entry point | All modules |
| `checks/` | Business logic for each QC check | `core/`, `utils/` |
| `core/` | Geometry processing, spatial operations | Only `arcpy` |
| `utils/` | Data access, messaging | Only `arcpy` |

---

## Spatial Operations

### Geometry Handling

All geometry operations use ArcPy's native geometry objects:

```python
# Example: Intersection detection
intersection = geom_a.intersect(geom_b, 4)  # 4 = polygon output
area = intersection.area
```

The `geometry.py` module provides wrapper functions that handle:
- Null geometry detection
- Type validation (polygon vs polyline)
- Error handling for invalid geometries

### Spatial Indexing

For performance with large datasets, a grid-based spatial index is used:

```
┌───────┬───────┬───────┐
│ (0,2) │ (1,2) │ (2,2) │
├───────┼───────┼───────┤
│ (0,1) │ (1,1) │ (2,1) │   ← Features indexed by grid cell
├───────┼───────┼───────┤
│ (0,0) │ (1,0) │ (2,0) │
└───────┴───────┴───────┘
```

**How it works:**
1. Each feature's extent is mapped to grid cells
2. When querying, only features in overlapping cells are checked
3. Reduces comparisons from O(n²) to O(n × k) where k << n

**Cell size:** Default 100 meters, balancing memory usage and query efficiency.

---

## Coordinate System Handling

### The Problem

Area calculations require projected coordinate systems. Geographic coordinates (lat/lon) produce incorrect area values.

### The Solution

OVC automatically detects geographic coordinate systems and projects data to an appropriate UTM zone:

```python
if not spatial_ref.type == "Projected":
    # Calculate UTM zone from data center
    utm_zone = int((center_lon + 180) / 6) + 1
    epsg = 32600 + utm_zone  # Northern hemisphere
    
    # Project to temporary feature class
    arcpy.management.Project(input, temp_output, utm_sr)
```

### Why UTM?

- UTM zones provide meter-based units globally
- Auto-calculation ensures correct zone selection
- Results are reprojected back to original CRS for output

---

## Why No Data Downloading?

The original OVC concept included OSM data downloading. This implementation deliberately excludes it:

| Reason | Explanation |
|--------|-------------|
| Enterprise focus | Organizations have their own authoritative data |
| Network constraints | Many GIS workstations have limited internet access |
| Data currency | Downloaded data may be outdated |
| Simplicity | Fewer dependencies, fewer failure points |
| User control | Users decide what data to analyze |

**Design decision:** OVC operates only on user-provided feature layers.

---

## Performance Optimizations

### 1. Spatial Index

Grid-based index reduces candidate comparisons from checking every feature to only checking nearby features.

### 2. Extent Pre-filtering

Before expensive geometry intersection, bounding box extents are compared:

```python
if not extents_intersect(extent_a, extent_b):
    continue  # Skip expensive intersection check
```

### 3. Lazy Processing

Features are read into memory once, then processed iteratively. Results are written in a single cursor operation.

### 4. Background Processing

Tools support `canRunInBackground = True`, allowing ArcGIS Pro to remain responsive during long operations.

---

## Error Handling Strategy

### Validation Layer

Parameters are validated before execution:

1. **Input validation** – Feature class exists, correct geometry type
2. **Threshold validation** – Values within acceptable ranges
3. **Output validation** – Path is writable

### Processing Layer

During processing, errors are handled gracefully:

- Invalid geometries are skipped (not process-stopping)
- Failed projections fall back to original geometry
- Cursor errors are caught and reported

### Reporting Layer

All operations report through the `ToolMessenger` class:
- Info messages for progress
- Warnings for recoverable issues
- Errors for fatal problems

---

## Extending the Toolbox

### Adding a New Tool

1. **Create check module** in `checks/`:
   ```python
   class NewChecker:
       def check(self, input, output):
           # Implementation
   ```

2. **Add tool class** to `OVCToolbox.pyt`:
   ```python
   class NewTool(object):
       def __init__(self):
           self.label = "New Tool"
       def getParameterInfo(self):
           # Define parameters
       def execute(self, parameters, messages):
           # Call check module
   ```

3. **Register tool** in `Toolbox.__init__`:
   ```python
   self.tools = [..., NewTool]
   ```

### Adding Configuration Options

Add new dataclass to `core/config.py`:

```python
@dataclass(frozen=True)
class NewCheckConfig:
    threshold_a: float = 1.0
    threshold_b: float = 0.5
```

---

## Testing Approach

### Manual Testing

1. Create test datasets with known violations
2. Run tools and verify expected results
3. Compare output attributes to expected values

### Recommended Test Cases

| Test | Purpose |
|------|---------|
| Overlapping squares | Verify overlap detection |
| Identical features | Verify duplicate classification |
| Non-overlapping | Verify zero results |
| Geographic CRS | Verify auto-projection |
| Empty input | Verify graceful handling |
| Large dataset | Verify performance |

---

## Dependencies

| Dependency | Source | Purpose |
|------------|--------|---------|
| arcpy | ArcGIS Pro | All spatial operations |
| os | Python stdlib | File path operations |
| dataclasses | Python stdlib | Configuration classes |
| typing | Python stdlib | Type hints |

**No external packages required.** The toolbox uses only ArcGIS Pro's bundled Python environment.

---

## Version Compatibility

| ArcGIS Pro Version | Status |
|--------------------|--------|
| 2.x | Not tested |
| 3.0 | ✅ Compatible |
| 3.1 | ✅ Compatible |
| 3.2+ | ✅ Compatible |

The toolbox uses stable ArcPy APIs that have remained consistent across ArcGIS Pro 3.x releases.

---

*For usage instructions, see [TOOL_USAGE.md](TOOL_USAGE.md). For installation, see [README.md](README.md).*
