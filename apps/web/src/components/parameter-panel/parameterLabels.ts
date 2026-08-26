import type { Scalar } from "./parameterValueTypes";

export const PARAM_SECTION_LABELS: Record<string, string> = {
  mission: "任务需求",
  fuselage: "机身",
  wing: "机翼",
  horizontal_tail: "平尾",
  vertical_tail: "垂尾",
  tail: "尾翼",
  engine: "发动机",
};

export const PARAM_FIELD_LABELS: Record<string, string> = {
  cruise_speed: "巡航速度",
  cruise_altitude: "巡航高度",
  range: "航程",
  endurance: "续航",
  payload: "载荷",
  priority: "优先级",
  length: "长度",
  max_diameter: "最大直径",
  position: "位置",
  z_rel_location: "展向位置",
  span: "翼展",
  root_chord: "根弦长",
  tip_chord: "尖弦长",
  sweep: "后掠角",
  dihedral: "上反角",
  incidence: "安装角",
  airfoil: "翼型",
  planform: "翼平面形状",
  sections: "截面段数",
  type: "类型",
  count: "数量",
};

// Raw enum values stored in the spec shown as Chinese labels instead of
// developer identifiers like "rear_fuselage" / "v_tail".
export const PARAM_VALUE_LABELS: Record<string, string> = {
  // wing planform
  conventional: "常规",
  delta: "三角翼",
  tapered: "梯形翼",
  rectangular: "矩形翼",
  elliptical: "椭圆翼",
  // wing vertical position
  mid: "中单翼",
  high: "上单翼",
  low: "下单翼",
  parasol: "伞翼",
  // tail type
  v_tail: "V型尾",
  inverted_v_tail: "倒V型尾",
  twin_tail: "双垂尾",
  t_tail: "T型尾",
  cruciform: "十字尾",
  // fuselage / engine position
  rear_fuselage: "后机身",
  nose: "机头",
  wing_mounted: "翼挂",
  fuselage_mounted: "机身挂",
  pusher: "推进式",
  tractor: "拉进式",
  // mission priority
  endurance: "长航时",
  speed: "高速",
  range: "航程",
  payload_priority: "载荷",
  stealth: "隐身",
  cost: "成本",
  // layout
  twin_boom: "双尾撑",
  flying_wing: "飞翼",
  blended_wing_body: "翼身融合",
  canard: "鸭翼",
  three_surface: "三翼面",
  tandem_wing: "串列翼",
  biplane: "双翼机",
  joined_wing: "连接翼",
  box_wing: "箱式翼",
  multi_fuselage: "双机身",
  // airfoil family names stay as-is (NACA…), handled below
};

export function paramFieldLabel(key: string): string {
  return PARAM_FIELD_LABELS[key] ?? key;
}

export function paramValueLabel(value: string | number): string {
  if (typeof value === "number") return String(value);
  const trimmed = value.trim();
  // Airfoil designations (NACA2412, NLF-0416, CLARK-Y…) are kept verbatim.
  if (/^(naca|nlf|clark|eppler|epler|selig|sd)\d*-?\d*/i.test(trimmed)) {
    return value;
  }
  return PARAM_VALUE_LABELS[trimmed.toLowerCase()] ?? value;
}

export function paramDisplayValue(scalar: Scalar): string {
  return paramValueLabel(scalar.value);
}
