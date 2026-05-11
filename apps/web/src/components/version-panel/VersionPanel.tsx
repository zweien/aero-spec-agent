type VersionPanelProps = {
  jobStatus?: string;
  versionNo?: number;
  files: string[];
};

export function VersionPanel({ jobStatus, versionNo, files }: VersionPanelProps) {
  return (
    <section className="bottom-panel">
      <span>任务状态：{jobStatus ?? "idle"}</span>
      <span>版本：{versionNo ?? "-"}</span>
      <span>文件：{files.length ? files.join(", ") : "-"}</span>
    </section>
  );
}
