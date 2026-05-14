import type { CadPreviewFormat } from "./cadPreviewSource";

export type CadPreviewStatus =
  | { state: "parameter" }
  | { format: CadPreviewFormat; state: "fallback" | "loaded" | "loading" };

function formatLabel(format: CadPreviewFormat): string {
  return format.toUpperCase();
}

export function cadPreviewStatusLabel(status: CadPreviewStatus): string {
  if (status.state === "loaded") {
    return `已加载 OpenVSP ${formatLabel(status.format)}`;
  }
  if (status.state === "loading") {
    return `正在加载 OpenVSP ${formatLabel(status.format)}`;
  }
  return "参数化 3D 预览";
}
