import { buildVersionFileUrl } from "@/components/cad-viewer/cadPreviewSource";

type VersionPanelProps = {
  apiBaseUrl: string;
  designId: string;
  jobStatus?: string;
  versionNo?: number;
  files: string[];
};

export function VersionPanel({
  apiBaseUrl,
  designId,
  jobStatus,
  versionNo,
  files,
}: VersionPanelProps) {
  const canLinkFiles = versionNo !== undefined;

  return (
    <section className="bottom-panel">
      <span>任务状态：{jobStatus ?? "idle"}</span>
      <span>版本：{versionNo ?? "-"}</span>
      <span className="file-list">
        文件：
        {files.length
          ? files.map((file, index) => (
              <span key={file}>
                {index > 0 ? ", " : ""}
                {canLinkFiles ? (
                  <a
                    href={buildVersionFileUrl(apiBaseUrl, designId, versionNo, file)}
                    rel="noreferrer"
                    target="_blank"
                  >
                    {file}
                  </a>
                ) : (
                  file
                )}
              </span>
            ))
          : "-"}
      </span>
    </section>
  );
}
