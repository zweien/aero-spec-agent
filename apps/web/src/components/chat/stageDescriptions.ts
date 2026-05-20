const STAGE_DESCRIPTIONS: Record<string, string> = {
  understanding_requirements: "AI 正在理解你的设计目标和约束条件",
  generating_spec: "AI 正在生成结构化飞机参数",
  validating_parameters: "系统正在检查参数合理性",
  fuselage_created: "系统正在创建机身几何",
  wing_created: "系统正在创建机翼几何",
  tail_created: "系统正在创建尾翼几何",
  engine_created: "系统正在创建发动机几何",
  vsp_model_saved: "系统正在保存 OpenVSP 模型",
  step_exported: "系统正在导出 STEP 工程文件",
  glb_exported: "系统正在导出三维预览模型",
  preview_ready: "系统正在准备三维预览",
  generating_cad: "系统正在创建飞机 CAD 几何",
  completed: "设计任务已完成",
  failed: "设计任务失败",
};

export function getStageDescription(stage: string): string {
  return STAGE_DESCRIPTIONS[stage] ?? stage;
}
