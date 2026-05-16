import type { CadPreviewFormat } from "./cadPreviewSource";

export type CadPreviewStatus =
  | { state: "parameter" }
  | { format: CadPreviewFormat; state: "fallback" | "loaded" | "loading" };

function formatLabel(format: CadPreviewFormat): string {
  return format.toUpperCase();
}

export function cadPreviewStatusLabel(status: CadPreviewStatus): string {
  if (status.state === "loaded") {
    return `已加载 ${formatLabel(status.format)} 模型`;
  }
  if (status.state === "loading") {
    return `正在加载 ${formatLabel(status.format)} 模型`;
  }
  return "参数化 3D 预览";
}
