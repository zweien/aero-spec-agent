export type AgentRunActionStatus = "completed" | "failed";

export type AgentRunActionHandler = () => void;

export type AgentRunAction = {
  key: "view-model" | "deep-design" | "export-report" | "show-details" | "retry" | "view-logs";
  label: string;
  disabled: boolean;
  disabledReason?: string;
  onClick?: AgentRunActionHandler;
};

export type BuildAgentRunActionsOptions = {
  status: AgentRunActionStatus;
  onViewModel?: AgentRunActionHandler;
  onDeepDesign?: AgentRunActionHandler;
  onExportReport?: AgentRunActionHandler;
  onShowDetails?: AgentRunActionHandler;
  onRetry?: AgentRunActionHandler;
  onViewLogs?: AgentRunActionHandler;
};

function action(
  key: AgentRunAction["key"],
  label: string,
  handler: AgentRunActionHandler | undefined,
  disabledReason: string,
): AgentRunAction {
  return {
    key,
    label,
    disabled: !handler,
    disabledReason: handler ? undefined : disabledReason,
    onClick: handler,
  };
}

export function buildAgentRunActions(opts: BuildAgentRunActionsOptions): AgentRunAction[] {
  if (opts.status === "failed") {
    return [
      action("view-logs", "查看日志", opts.onViewLogs ?? opts.onShowDetails, "失败日志加载后可用"),
      action("retry", "重试", opts.onRetry, "失败任务可重试时可用"),
    ];
  }

  return [
    action("view-model", "查看模型", opts.onViewModel, "模型生成后可用"),
    action("deep-design", "深度设计探索", opts.onDeepDesign, "当前设计加载后可用"),
    action("export-report", "导出报告", opts.onExportReport, "报告生成后可用"),
    action("show-details", "查看运行细节", opts.onShowDetails, "运行详情加载后可用"),
  ];
}
