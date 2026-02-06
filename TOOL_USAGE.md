# Tool Usage Guide

Detailed instructions for using the OVC (Overlap Violation Checker) toolbox in ArcGIS Pro.

## Adding the Toolbox to ArcGIS Pro

### Method 1: Add to Current Project

1. Open your ArcGIS Pro project
2. In the **Catalog** pane, expand **Toolboxes**
3. Right-click **Toolboxes** → **Add Toolbox**
4. Navigate to `OVCToolbox.pyt` and click **OK**
5. The toolbox appears under "Overlap Violation Checker (OVC)"

### Method 2: Add to Favorites (Persistent)

1. In the **Catalog** pane, navigate to the folder containing `OVCToolbox.pyt`
2. Right-click the `.pyt` file → **Add To Favorites**
3. The toolbox will be available in all future projects

### Method 3: Connect Folder

1. In the **Catalog** pane, right-click **Folders** → **Add Folder Connection**
2. Navigate to the repository folder
3. The toolbox will be accessible from the connected folder

---

## Building Overlap Checker

Detects overlapping polygons and classifies them by severity.

### Input Requirements

| Parameter | Type | Description |
|-----------|------|-------------|
| Input Features | Polygon Feature Layer | Building footprints or similar polygons |
| Minimum Overlap Area | Double | Threshold in square meters (default: 1.0) |
| Process Selected Only | Boolean | Check only selected features (optional) |
| Duplicate Threshold | Double | Overlap ratio for duplicate classification (default: 0.90) |
| Partial Threshold | Double | Overlap ratio for partial classification (default: 0.50) |
| Output Feature Class | Feature Class | Location for output results |

### Supported Projections

- **Projected Coordinate Systems** – Uses native units (meters recommended)
- **Geographic Coordinate Systems** – Automatically projected to appropriate UTM zone

### Output Schema

| Field | Type | Description |
|-------|------|-------------|
| OBJECTID | Long | System-generated ID |
| Shape | Polygon | Overlap geometry |
| SOURCE_FID_A | Long | First overlapping feature ID |
| SOURCE_FID_B | Long | Second overlapping feature ID |
| OVERLAP_AREA_M2 | Double | Overlap area in square meters |
| OVERLAP_RATIO | Double | Ratio of overlap to smaller feature |
| OVERLAP_TYPE | Text | DUPLICATE, PARTIAL, or SLIVER |
| CHECK_TIME | Text | Timestamp of analysis |

### Classification Criteria

| Type | Condition | Meaning |
|------|-----------|---------|
| DUPLICATE | Overlap ratio ≥ 90% | Near-complete overlap, likely duplicate features |
| PARTIAL | Overlap ratio ≥ 50% | Significant overlap, possible digitization error |
| SLIVER | Overlap ratio < 50% | Minor overlap, may be acceptable |

### Example Workflow

```
1. Add building layer to map
2. Open Building Overlap Checker tool
3. Set Input Features = Buildings
4. Set Minimum Overlap Area = 1.0 (ignore tiny slivers)
5. Set Output = Scratch.gdb\building_overlaps
6. Click Run
7. Review results in attribute table
8. Use OVERLAP_TYPE to prioritize corrections
```

---

## Building-Road Conflict Checker

Detects buildings that overlap with buffered road geometries.

### Input Requirements

| Parameter | Type | Description |
|-----------|------|-------------|
| Building Features | Polygon Feature Layer | Building footprints |
| Road Features | Polyline Feature Layer | Road centerlines |
| Road Buffer Distance | Double | Buffer in meters (default: 5.0) |
| Minimum Conflict Area | Double | Threshold in square meters (default: 0.5) |
| Output Feature Class | Feature Class | Location for output results |

### Supported Projections

- **Projected Coordinate Systems** – Buffer distance in native units
- **Geographic Coordinate Systems** – Auto-projected to UTM; buffer in meters

### Output Schema

| Field | Type | Description |
|-------|------|-------------|
| OBJECTID | Long | System-generated ID |
| Shape | Polygon | Conflict geometry |
| BUILDING_FID | Long | Building feature ID |
| ROAD_FID | Long | Road feature ID |
| CONFLICT_AREA_M2 | Double | Conflict area in square meters |
| BUFFER_DIST_M | Double | Buffer distance used |
| CHECK_TIME | Text | Timestamp of analysis |

### Buffer Distance Guidelines

| Road Type | Suggested Buffer |
|-----------|-----------------|
| Local roads | 3–5 m |
| Collector roads | 5–10 m |
| Arterial roads | 10–15 m |
| Highways | 15–30 m |

### Example Workflow

```
1. Add building and road layers to map
2. Open Building-Road Conflict Checker tool
3. Set Building Features = Buildings
4. Set Road Features = Roads
5. Set Buffer Distance = 5.0
6. Set Output = Scratch.gdb\road_conflicts
7. Click Run
8. Review results - buildings shown are within buffer zone
```

---

## Performance Considerations

### Large Datasets

For datasets exceeding 50,000 features:

1. **Use selections** – Process subsets using the "Process Selected Only" option
2. **Increase minimum area** – Filter out small overlaps to reduce output volume
3. **Expect longer runtimes** – Spatial indexing helps, but geometry operations are intensive

### Memory Usage

- The tool loads all geometries into memory
- For very large datasets (500k+), consider processing in tiles
- Close unnecessary applications to free memory

### Background Processing

Both tools support background processing:
- Enable in tool properties if needed
- Allows continued work while tool runs
- Progress shown in Geoprocessing History

---

## Troubleshooting

### "Module not found" error

**Cause:** ArcGIS Pro cached old module versions

**Solution:** Completely restart ArcGIS Pro (not just the project)

### Zero results with expected overlaps

**Cause:** Minimum area threshold too high, or data in wrong units

**Solution:**
1. Lower the minimum overlap area threshold
2. Verify data is in a projected coordinate system
3. Check that features actually overlap (zoom in to inspect)

### Slow performance

**Cause:** Large dataset without spatial indexing, or geographic coordinates

**Solution:**
1. Project data to a local coordinate system before processing
2. Use selections to process subsets
3. Increase step size in progress reporting

### Output not appearing in map

**Cause:** Output location issue

**Solution:**
1. Verify output path is valid
2. Check Geoprocessing History for errors
3. Manually add output to map if needed

---

## Best Practices

1. **Project your data** – While auto-projection works, manually projecting to a local coordinate system ensures best accuracy

2. **Start with defaults** – Run with default thresholds first, then adjust based on results

3. **Review systematically** – Use OVERLAP_TYPE or CONFLICT_AREA to prioritize which violations to fix first

4. **Document your thresholds** – Record what parameters you used for reproducibility

5. **Validate corrections** – Re-run the tool after making corrections to verify issues are resolved

---

*For technical details about the tool architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).*
