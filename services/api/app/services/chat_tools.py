from __future__ import annotations

from typing import Any


FLAT_FIELD_DEFS: dict[str, tuple[str, str | None, str]] = {
    "name": ("text", None, "aircraft.name"),
    "aircraft_layout": ("text", None, "aircraft.layout"),
    "wing_span": ("numeric", "m", "wing.span"),
    "wing_root_chord": ("numeric", "m", "wing.root_chord"),
    "wing_tip_chord": ("numeric", "m", "wing.tip_chord"),
    "wing_sweep": ("numeric", "deg", "wing.sweep"),
    "wing_dihedral": ("numeric", "deg", "wing.dihedral"),
    "wing_airfoil": ("text", None, "wing.airfoil"),
    "wing_position": ("text", None, "wing.position"),
    "fuselage_length": ("numeric", "m", "fuselage.length"),
    "fuselage_diameter": ("numeric", "m", "fuselage.max_diameter"),
    "engine_count": ("integer", None, "engine.count"),
    "engine_position": ("text", None, "engine.position"),
    "engine_x_offset": ("numeric", "m", "engine.x_offset"),
    "engine_y_offset": ("numeric", "m", "engine.y_offset"),
    "engine_z_offset": ("numeric", "m", "engine.z_offset"),
    "tail_type": ("text", None, "tail.type"),
    "cruise_speed": ("numeric", "km/h", "mission.cruise_speed"),
    "payload": ("numeric", "kg", "mission.payload"),
    "priority": ("text", None, "mission.priority"),
}

FIELD_TO_SPEC_PATH: dict[str, str] = {
    "name": "aircraft.name",
    "aircraft_layout": "aircraft.layout",
    "wing_span": "wing.span.value",
    "wing_root_chord": "wing.root_chord.value",
    "wing_tip_chord": "wing.tip_chord.value",
    "wing_sweep": "wing.sweep.value",
    "wing_dihedral": "wing.dihedral.value",
    "wing_airfoil": "wing.airfoil.value",
    "wing_position": "wing.position.value",
    "fuselage_length": "fuselage.length.value",
    "fuselage_diameter": "fuselage.max_diameter.value",
    "engine_count": "engine.count.value",
    "engine_position": "engine.position.value",
    "engine_x_offset": "engine.x_offset.value",
    "engine_y_offset": "engine.y_offset.value",
    "engine_z_offset": "engine.z_offset.value",
    "tail_type": "tail.type.value",
    "cruise_speed": "mission.cruise_speed.value",
    "payload": "mission.payload.value",
    "priority": "mission.priority.value",
}

FIELD_DEFAULT_UNIT: dict[str, str | None] = {
    "aircraft_layout": None,
    "wing_span": "m",
    "wing_root_chord": "m",
    "wing_tip_chord": "m",
    "wing_sweep": "deg",
    "wing_dihedral": "deg",
    "fuselage_length": "m",
    "fuselage_diameter": "m",
    "engine_count": None,
    "engine_position": None,
    "engine_x_offset": "m",
    "engine_y_offset": "m",
    "engine_z_offset": "m",
    "cruise_speed": "km/h",
    "payload": "kg",
}

SUPPORTED_FIELD_VALUES: dict[str, set[str]] = {
    "tail_type": {"conventional", "t_tail", "v_tail", "inverted_v", "cruciform"},
    "engine_position": {"nose", "tail", "rear_fuselage", "under_wing", "wing_tip", "over_wing", "pusher", "push_pull"},
}

GENERATE_DESIGN_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "generate_design",
        "description": "根据用户需求生成新的飞机设计。当用户描述全新的飞机需求时使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "飞机名称，英文下划线命名"},
                "fuselage_length": {"type": "number", "description": "机身长度 (m)"},
                "fuselage_diameter": {"type": "number", "description": "机身最大直径 (m)"},
                "wing_position": {
                    "type": "string",
                    "enum": ["high", "low", "mid"],
                    "description": "机翼位置",
                },
                "wing_span": {"type": "number", "description": "翼展 (m)"},
                "wing_root_chord": {"type": "number", "description": "翼根弦长 (m)"},
                "wing_tip_chord": {"type": "number", "description": "翼尖弦长 (m)"},
                "wing_sweep": {"type": "number", "description": "机翼后掠角 (deg)"},
                "wing_dihedral": {"type": "number", "description": "机翼上反角 (deg)"},
                "wing_airfoil": {"type": "string", "description": "翼型，如 NACA4412"},
                "aircraft_layout": {
                    "type": "string",
                    "enum": [
                        "conventional", "twin_boom", "flying_wing", "blended_wing_body",
                        "canard", "three_surface", "tandem_wing", "biplane",
                        "joined_wing", "box_wing", "multi_fuselage",
                    ],
                    "description": "气动布局类型",
                },
                "tail_type": {
                    "type": "string",
                    "enum": ["conventional", "t_tail", "v_tail", "inverted_v", "cruciform"],
                    "description": "尾翼类型",
                },
                "engine_count": {"type": "integer", "description": "发动机数量"},
                "engine_position": {
                    "type": "string",
                    "enum": ["nose", "tail", "rear_fuselage", "under_wing", "wing_tip", "over_wing", "pusher", "push_pull"],
                    "description": "发动机位置",
                },
                "cruise_speed": {"type": "number", "description": "巡航速度 (km/h)"},
                "payload": {"type": "number", "description": "有效载荷 (kg)"},
                "priority": {
                    "type": "string",
                    "enum": ["endurance", "speed", "payload", "range"],
                    "description": "设计优先级",
                },
                "inferred_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "哪些参数是你根据经验推断，而不是用户明确给出",
                },
            },
            "required": [
                "name",
                "fuselage_length",
                "wing_position",
                "wing_span",
                "wing_root_chord",
                "wing_tip_chord",
                "tail_type",
                "engine_count",
            ],
        },
    },
}

MODIFY_DESIGN_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "modify_design",
        "description": "修改当前飞机设计的参数。使用语义化字段名指定要修改的参数。",
        "parameters": {
            "type": "object",
            "properties": {
                "changes": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {
                                "type": "string",
                                "enum": list(FIELD_TO_SPEC_PATH.keys()),
                                "description": "要修改的参数名",
                            },
                            "value": {"description": "新值"},
                            "reason": {"type": "string", "description": "修改原因"},
                        },
                        "required": ["field", "value"],
                    },
                }
            },
            "required": ["changes"],
        },
    },
}

MODIFY_SELECTED_PART_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "modify_selected_part",
        "description": (
            "修改选中的飞机部件参数。根据当前 selected_refs 确定部件类型。\n"
            "支持的操作：\n"
            "- 机身(part:fuselage): set_length(设置长度/m), increase_length/decrease_length(长度增量/m), "
            "set_diameter(设置直径/m), increase_diameter/decrease_diameter(直径增量/m)\n"
            "- 机翼(part:main_wing): set_span(设置翼展/m), set_root_chord(设置翼根弦长/m), "
            "set_tip_chord(设置翼尖弦长/m), set_sweep(设置后掠角/deg), set_dihedral(设置上反角/deg), "
            "increase_*/decrease_* 对应参数增量\n"
            "- 尾翼(part:tail): set_tail_type(设置尾翼类型；当前仅 conventional)\n"
            "- 发动机(part:left_engine/part:right_engine): move_outboard/inboard/forward/backward/up/down(移动/m，增量)\n"
            "set_* 操作 value 为目标绝对值；increase_*/decrease_* 和 move_* 操作 value 为增量。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "part_ref": {
                    "type": "string",
                    "enum": [
                        "part:left_engine",
                        "part:right_engine",
                        "part:fuselage",
                        "part:main_wing",
                        "part:tail",
                    ],
                    "description": "要修改的部件引用，通常来自当前 selected_refs",
                },
                "operation": {
                    "type": "string",
                    "enum": [
                        "set_length",
                        "set_diameter",
                        "increase_length",
                        "decrease_length",
                        "increase_diameter",
                        "decrease_diameter",
                        "set_span",
                        "set_root_chord",
                        "set_tip_chord",
                        "set_sweep",
                        "set_dihedral",
                        "increase_span",
                        "decrease_span",
                        "increase_root_chord",
                        "decrease_root_chord",
                        "increase_tip_chord",
                        "decrease_tip_chord",
                        "increase_sweep",
                        "decrease_sweep",
                        "increase_dihedral",
                        "decrease_dihedral",
                        "set_tail_type",
                        "move_outboard",
                        "move_inboard",
                        "move_forward",
                        "move_backward",
                        "move_up",
                        "move_down",
                    ],
                    "description": "操作类型。set_* 用绝对值，increase/decrease/move 用增量。",
                },
                "value": {
                    "description": "set_* 操作为目标绝对值，increase/decrease/move 操作为增量",
                },
                "reason": {
                    "type": "string",
                    "description": "修改原因",
                },
            },
            "required": ["part_ref", "operation", "value"],
        },
    },
}
