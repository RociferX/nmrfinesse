# Batch processing

Batch import and groups support 1D, 2D and 3D. Browse a top-level folder, then filter all dimensions, one dimension or any pair. Grouping creates separate groups by dimensionality. Manual creation and adding members require homogeneous dimensions.

The **All** row checks or unchecks the paths visible after dimensionality filtering. **Remove checked** removes those paths. **Batch import** uses all paths still shown.

Select a group in the project tree, choose automatic or reference-script processing and a stopping step in the centre panel. Automatic 2D groups run in parallel, defaulting to five simultaneous data sets; Settings permits 1–10. 1D/3D and reference-script groups run sequentially. 1D skips peak picking. Deleted members are excluded.

Automatic processing skips completed steps whose inputs and products remain valid. Each member retains separate status, logs and reports. One failure does not abort other members; stopping cancels pending work. Reference scripts support per-member direct-axis ranges and phases, including automatic phase search after FID conversion. See the [GUI guide](gui.md).

```python
from workflow.batch import run_batch

result = run_batch(manager, "exp_001", "G1", ["fid", "spectrum"], backend, max_workers=5)
```

The programmatic `max_workers` default is 1 and maximum is 10, used only for automatic 2D processing. Each member uses a separate backend copy and work directory.

Batch processing varies the data set; API parameter sweeps vary processing parameters for one data set. Existing API 3D NUS sweep limits remain unchanged; see the [API support matrix](external-api/09-limitations-and-roadmap.md).
