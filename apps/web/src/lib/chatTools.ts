import { tool } from "ai";
import { z } from "zod";

const FASTAPI_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8900";

// --- generate_design ---

const generateDesignSchema = z.object({
  name: z.string().describe("飞机名称，英文下划线命名"),
  fuselage_length: z.number().describe("机身长度 (m)"),
  fuselage_diameter: z.number().optional().describe("机身最大直径 (m)"),
  wing_position: z
    .enum(["high", "low", "mid"])
    .describe("机翼位置"),
  wing_span: z.number().describe("翼展 (m)"),
  wing_root_chord: z.number().describe("翼根弦长 (m)"),
  wing_tip_chord: z.number().describe("翼尖弦长 (m)"),
  wing_sweep: z.number().optional().describe("机翼后掠角 (deg)"),
  wing_dihedral: z.number().optional().describe("机翼上反角 (deg)"),
  wing_airfoil: z.string().optional().describe("翼型，如 NACA4412"),
  wing_planform: z
    .enum(["conventional", "delta", "ogee"])
    .optional()
    .describe("机翼平面形状"),
  aircraft_layout: z
    .enum([
      "conventional", "twin_boom", "flying_wing", "blended_wing_body",
      "canard", "three_surface", "tandem_wing", "biplane",
      "joined_wing", "box_wing", "multi_fuselage",
    ])
    .optional()
    .describe("气动布局类型"),
  tail_type: z
    .enum(["conventional", "t_tail", "v_tail", "inverted_v", "cruciform"])
    .describe("尾翼类型"),
  engine_count: z.number().int().describe("发动机数量"),
  engine_position: z
    .enum(["nose", "tail", "rear_fuselage", "under_wing", "wing_tip", "over_wing", "pusher", "push_pull"])
    .optional()
    .describe("发动机位置"),
  cruise_speed: z.number().optional().describe("巡航速度 (km/h)"),
  payload: z.number().optional().describe("有效载荷 (kg)"),
  priority: z
    .enum(["endurance", "speed", "payload", "range"])
    .optional()
    .describe("设计优先级"),
  canard_span: z.number().optional().describe("鸭翼翼展 (m)，canard/three_surface 布局使用"),
  canard_chord: z.number().optional().describe("鸭翼弦长 (m)"),
  canard_sweep: z.number().optional().describe("鸭翼后掠角 (deg)"),
  rear_wing_span: z.number().optional().describe("后翼翼展 (m)，tandem_wing/joined_wing 布局使用"),
  rear_wing_chord: z.number().optional().describe("后翼弦长 (m)"),
  second_wing_span: z.number().optional().describe("下翼翼展 (m)，biplane 布局使用"),
  second_wing_chord: z.number().optional().describe("下翼弦长 (m)"),
  second_wing_gap: z.number().optional().describe("上下翼间距 (m)"),
  multi_fuselage_spacing: z.number().optional().describe("双机身间距 (m)"),
  box_wing_gap: z.number().optional().describe("箱式翼上下翼间距 (m)"),
  inferred_fields: z
    .array(z.string())
    .optional()
    .describe("根据经验推断而非用户明确给出的字段名"),
});

// --- modify_design ---

const modifyDesignSchema = z.object({
  changes: z
    .array(
      z.object({
        field: z
          .enum([
            "name",
            "aircraft_layout",
            "wing_span",
            "wing_root_chord",
            "wing_tip_chord",
            "wing_sweep",
            "wing_dihedral",
            "wing_airfoil",
            "wing_position",
            "wing_planform",
            "fuselage_length",
            "fuselage_diameter",
            "engine_count",
            "engine_position",
            "engine_x_offset",
            "engine_y_offset",
            "engine_z_offset",
            "tail_type",
            "cruise_speed",
            "payload",
            "priority",
            "canard_span",
            "canard_chord",
            "canard_sweep",
            "rear_wing_span",
            "rear_wing_chord",
            "second_wing_span",
            "second_wing_chord",
            "second_wing_gap",
            "multi_fuselage_spacing",
            "box_wing_gap",
          ])
          .describe("要修改的参数名"),
        value: z.any().describe("新值"),
        reason: z.string().optional().describe("修改原因"),
      }),
    )
    .min(1)
    .describe("要修改的参数列表"),
});

// --- modify_selected_part ---

const modifySelectedPartSchema = z.object({
  part_ref: z
    .enum([
      "part:left_engine",
      "part:right_engine",
      "part:fuselage",
      "part:main_wing",
      "part:tail",
    ])
    .describe("要修改的部件引用"),
  operation: z
    .enum([
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
    ])
    .describe("操作类型"),
  value: z.any().describe(
    "set_* 操作为目标绝对值，increase/decrease/move 操作为增量",
  ),
  reason: z.string().optional().describe("修改原因"),
});

// --- Factory ---

export function createChatTools(conversationId: string) {
  async function executeTool(toolName: string, args: Record<string, unknown>) {
    const resp = await fetch(`${FASTAPI_BASE}/api/tools/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: conversationId,
        tool_name: toolName,
        args,
      }),
    });
    if (!resp.ok) {
      const detail = await resp.text();
      return { status: "failed", error: detail };
    }
    return resp.json();
  }

  return {
    generate_design: tool({
      description:
        "根据用户需求生成新的飞机设计。当用户描述全新的飞机需求时使用。",
      inputSchema: generateDesignSchema,
      execute: async (args) => executeTool("generate_design", args),
    }),
    modify_design: tool({
      description:
        "修改当前飞机设计的参数。使用语义化字段名指定要修改的参数。",
      inputSchema: modifyDesignSchema,
      execute: async (args) => executeTool("modify_design", args),
    }),
    modify_selected_part: tool({
      description: `修改选中的飞机部件参数。根据当前 selected_refs 确定部件类型。
支持的操作：
- 机身(part:fuselage): set_length, increase_length/decrease_length, set_diameter, increase_diameter/decrease_diameter
- 机翼(part:main_wing): set_span, set_root_chord, set_tip_chord, set_sweep, set_dihedral, increase_*/decrease_*
- 尾翼(part:tail): set_tail_type
- 发动机(part:left_engine/part:right_engine): move_outboard/inboard/forward/backward/up/down
set_* 操作 value 为目标绝对值；increase/decrease/move 操作 value 为增量。`,
      inputSchema: modifySelectedPartSchema,
      execute: async (args) => executeTool("modify_selected_part", args),
    }),
  };
}
