# adas-vdy

Vehicle dynamics estimator: consumes raw vehicle-signal data (`VehSig`) and
produces the estimated `VehDyn` every other component (`df`'s
`AebReqPorts::egoDyn`, ...) already consumes. See `plan.md` item 3
(superproject root) and `docs/vdy_skeleton_plan.md` for the full design.

## Build

```bash
build.bat base sil     vs2026 [clean]
build.bat base gtest   vs2026 [clean]
```

## Layout

- `src/component/common/` — shared framework (`vdy_common` lib, header-only): ports, `IVdyFunction`, `VdyParams`
- `src/component/` — `VdyFunction`, the single vehicle-dynamics-estimator capability (no per-function subfolder — vdy has exactly one job)
- `src/platform/vdy_sil/` — primary SIL artifact: `vdy_sil`, a host-agnostic C-API DLL
- `src/platform/standalone/` — inert placeholder
- `src/platform/autosar/` — production target (Adaptive AUTOSAR)
- `src/platform/tda4vm/`, `src/platform/orin/` — SoC placeholders
- `src/project/<name>/ego_params.yaml` — ego vehicle-wide physical parameters (vdy's own calibration input)

Current status: port + function skeleton — no real estimation math yet (staleness/validity gating only, publishes a neutral placeholder `VehDyn` every cycle).
