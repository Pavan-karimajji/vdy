# vdy

Vehicle dynamics — produces the ego-vehicle dynamics interface.

## Role

Produces `VehDyn` (member `egoDyn`) — the ego kinematic/dynamic state consumed
by `df` and others. Skeleton has landed; builds via the standard machinery.

## Local constraints

- **Ego-state signals are frozen** (R-COORD-2): `vx`/`ax`/`yaw_rate`/`ay` are
  real; **`ay` is a passthrough** (not `vx*yaw_rate`); **there is no `vy` — use
  `side_slip_angle`.** Do not "fix" toward the reference on these.
- **Ego-fixed frame**, origin rear-axle center, +x forward, +y left (R-COORD-1).
- Naming `VehDyn`/`egoDyn` (never "vehicle state", R-NAME-1). Header
  `COMPONENT: VDY`.

## AI operational layer — root-canonical

Part of `1v-superproject`. Cross-cutting rules/skills/templates/workflows live
once at the superproject root `.claude/` (spec:
`docs/ai_operational_layer_spec.md`). Load `../../.claude/rules/*` + the matching
`skills/*`; do not duplicate them here. This file holds only what is local to `vdy`.
