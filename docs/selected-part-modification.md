# Selected Part Modification

## Purpose

Selected part modification lets the chat tool patch a specific aircraft part through `aircraft_spec` instead of editing CAD geometry directly. The selected part list is a safety boundary: if `selected_refs` is non-empty, the requested `part_ref` must be present in that list.

## Supported Part Refs

| Part ref | Meaning |
|----------|---------|
| `part:fuselage` | Fuselage scalar dimensions |
| `part:main_wing` | Main wing scalar dimensions |
| `part:tail` | Tail layout scalar |
| `part:left_engine` | Left engine offset controls |
| `part:right_engine` | Right engine offset controls |

## Operation Semantics

| Operation family | Meaning | Example |
|------------------|---------|---------|
| `set_*` | Absolute target value | `set_length value=9` writes fuselage length to 9 m. |
| `increase_*` | Positive delta from the current value | `increase_length value=2` changes 7 m to 9 m. |
| `decrease_*` | Negative delta from the current value | `decrease_span value=1` changes 12 m to 11 m. |
| `move_*` | Engine offset delta | `move_outboard value=0.5` adds 0.5 m to `engine.y_offset`. |

## Operation Matrix

| Part ref | Operations |
|----------|------------|
| `part:fuselage` | `set_length`, `increase_length`, `decrease_length`, `set_diameter`, `increase_diameter`, `decrease_diameter` |
| `part:main_wing` | `set_span`, `increase_span`, `decrease_span`, `set_root_chord`, `increase_root_chord`, `decrease_root_chord`, `set_tip_chord`, `increase_tip_chord`, `decrease_tip_chord`, `set_sweep`, `increase_sweep`, `decrease_sweep`, `set_dihedral`, `increase_dihedral`, `decrease_dihedral` |
| `part:tail` | `set_tail_type`; currently only `conventional` is accepted |
| `part:left_engine`, `part:right_engine` | `move_outboard`, `move_inboard`, `move_forward`, `move_backward`, `move_up`, `move_down` |

## Spec Patch Targets

| User-facing operation | Spec field |
|-----------------------|------------|
| Fuselage length | `fuselage.length.value` |
| Fuselage diameter | `fuselage.max_diameter.value` |
| Wing span | `wing.span.value` |
| Wing root chord | `wing.root_chord.value` |
| Wing tip chord | `wing.tip_chord.value` |
| Wing sweep | `wing.sweep.value` |
| Wing dihedral | `wing.dihedral.value` |
| Tail type | `tail.type.value` |
| Engine forward/backward | `engine.x_offset.value` |
| Engine outboard/inboard | `engine.y_offset.value` |
| Engine up/down | `engine.z_offset.value` |

All successful selected-part patches set `source="user"` and `confidence=1.0` on the patched scalar. Length, diameter, span, and chord fields must remain greater than zero.

## Validation Report

Engine offset edits are reflected in `validation_report.json`:

| Spec field | Validation key |
|------------|----------------|
| `engine.x_offset.value` | `engine.x_offset` |
| `engine.y_offset.value` | `engine.y_offset` |
| `engine.z_offset.value` | `engine.z_offset` |

For example, `move_outboard value=0.5` on `part:right_engine` should produce:

```json
{
  "engine.y_offset": {
    "expected": 0.5,
    "actual": 0.5,
    "status": "pass"
  }
}
```
