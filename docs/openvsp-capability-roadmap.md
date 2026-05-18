# OpenVSP Capability Roadmap

## Current State

| Component | Capability | Status |
|-----------|-----------|--------|
| Fuselage | Length, max_diameter | Done |
| Wing | Span, root/tip chord, sweep, dihedral, position (high/mid/low) | Done |
| Tail | Conventional (H-tail + V-tail) only | Done |
| Engine | 1 (nose/tail) or 2 (under-wing symmetric) | Done |
| VSPAERO | Alpha sweep, L/D optimization, CD0 estimate | Done (wing-only) |
| Export | VSP3, STEP, OBJ, GLB | Done |

## Roadmap

### Tier 1: Tail Configuration Expansion

#### T-tail
- **Description:** Horizontal tail mounted on top of vertical tail
- **Schema change:** Add `tail.configuration: "t_tail"` to AircraftSpec
- **Builder change:** `create_tail.py` — position H-tail at V-tail tip
- **V-tail height increase:** ~20% taller to support H-tail moment arm
- **VSPAERO impact:** Full aircraft analysis needed (tail interference)

```python
# create_tail.py addition
if config == "t_tail":
    h_tail_z = fuselage_length * 0.9 + v_tail_span
    # H-tail at top of V-tail
```

#### V-tail
- **Description:** Two angled surfaces replacing separate H + V tails
- **Schema change:** Add `tail.configuration: "v_tail"`, `tail.v_tail_angle` (typical: 30-45°)
- **Builder change:** `create_tail.py` — two symmetric surfaces at dihedral angle
- **VSPAERO impact:** Combined yaw/roll stability analysis

#### H-tail (twin boom)
- **Description:** Dual horizontal stabilizers on twin booms
- **Schema change:** Add `tail.configuration: "h_tail"`, `tail.boom_spacing`
- **Builder change:** `create_tail.py` — two H-tail surfaces at boom positions

### Tier 2: Engine Placement Expansion

#### Rear Fuselage Engines
- **Description:** Engines mounted on rear fuselage sides (business jet style)
- **Schema change:** Add `engine.placement: "rear_fuselage"` with `y_offset`
- **Builder change:** `create_engine.py` — position at ~80% fuselage length, offset Y
- **VSPAERO impact:** Fuselage-engine interference drag

#### Wing Tip Engines
- **Description:** Engines at wing tips (reduces induced drag concept)
- **Schema change:** Add `engine.placement: "wing_tip"`
- **Builder change:** `create_engine.py` — position at wing tip span
- **VSPAERO impact:** Wing tip vortex reduction modeling

#### Over-Wing Engines
- **Description:** Engines above wing (HondaJet style)
- **Schema change:** Add `engine.placement: "over_wing"` with `x_offset`
- **Builder change:** `create_engine.py` — position above wing chord

#### Multi-Engine (3-4)
- **Description:** Tri-jet or quad-jet configurations
- **Schema change:** Extend `engine.count` to support 3-4
- **Builder change:** `create_engine.py` — symmetric + centerline placement logic

### Tier 3: VSPAERO Analysis Expansion

#### Full Aircraft Analysis
- **Current:** Wing-only mesh (Set_0)
- **Target:** All geometry in analysis mesh
- **Implementation:**
  - `openvsp_adapter.create_set("all_geometry")`
  - Add fuselage, tail, engine to analysis set
  - Re-run geometry computation before analysis

#### Multi-Point Analysis
- **Current:** Single Mach, single alpha sweep
- **Target:** Multiple Mach numbers, cruise + climb + approach
- **Schema change:** Add `performance.cruise_conditions` array
- **Implementation:** Nested sweep loop in `vspaero_analysis.py`

#### Beta Sweep (Side Slip)
- **Current:** Alpha-only
- **Target:** Add beta sweep for directional stability
- **Implementation:** Additional `VSPAEROSweep` with beta parameter

#### Results Comparison
- **Current:** Single version analysis
- **Target:** Compare VSPAERO results across versions
- **Implementation:** Store results per version, add comparison API endpoint
- **Frontend:** Version comparison panel with CL/CD/CM overlay plots

### Tier 4: Advanced Geometry

#### Control Surfaces
- Aileron, elevator, rudder definition
- OpenVSP `SET_FLAP` parameters
- VSPAERO control effectiveness analysis

#### Fuselage Shaping
- Non-circular cross sections
- Nose/tail cone profiles
- Cabin layout constraints

#### High-Lift Devices
- Flap and slat geometry
- Takeoff/landing performance estimation

## Implementation Priority

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| P0 | T-tail | 1 week | Common UAV config |
| P0 | Rear fuselage engines | 1 week | Business jet UAV |
| P1 | V-tail | 1 week | Stealth UAV |
| P1 | Full aircraft VSPAERO | 2 weeks | Analysis accuracy |
| P1 | VSPAERO results comparison | 1 week | Design iteration |
| P2 | Wing tip engines | 3 days | Niche config |
| P2 | Multi-engine (3-4) | 1 week | Large UAV |
| P2 | Multi-point analysis | 2 weeks | Performance envelope |
| P3 | Control surfaces | 2 weeks | Detailed design |
| P3 | Fuselage shaping | 3 weeks | Aerodynamic refinement |
| P3 | High-lift devices | 2 weeks | Low-speed performance |

## Schema Extension Pattern

Each new capability follows this pattern:

1. **Add to schema** (`services/api/app/schemas/aircraft_spec.py`)
   - New field with default value (backward compatible)
   - Validation constraints

2. **Extend builder** (`services/workers/cad_worker/openvsp_generator/create_*.py`)
   - New branch in existing function or new builder file
   - Parameter mapping from schema to OpenVSP API calls

3. **Update test fixtures** (`packages/aircraft-schema/examples/`)
   - New example YAML files for each configuration

4. **Add tests** (`tests/api/`)
   - Geometry builder unit tests with fake backend
   - Integration tests with real OpenVSP (gated by `RUN_OPENVSP_TESTS=1`)

5. **Update VSPAERO analysis** (if aerodynamic impact)
   - Extend mesh generation
   - Add new analysis parameters
