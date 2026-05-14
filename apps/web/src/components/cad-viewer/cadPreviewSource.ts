export type CadPreviewFormat = "glb" | "obj";

export type CadPreviewSource = {
  filename: string;
  format: CadPreviewFormat;
  url: string;
};

type SelectCadPreviewSourceArgs = {
  apiBaseUrl: string;
  designId: string;
  versionNo: number;
  files: string[];
};

const PREVIEW_CANDIDATES: Array<{ filename: string; format: CadPreviewFormat }> = [
  { filename: "aircraft.glb", format: "glb" },
  { filename: "aircraft.obj", format: "obj" },
];

export function buildVersionFileUrl(
  apiBaseUrl: string,
  designId: string,
  versionNo: number,
  filename: string,
): string {
  return `${apiBaseUrl}/api/designs/${designId}/versions/${versionNo}/files/${encodeURIComponent(filename)}`;
}

export function selectCadPreviewSource({
  apiBaseUrl,
  designId,
  versionNo,
  files,
}: SelectCadPreviewSourceArgs): CadPreviewSource | null {
  const candidate = PREVIEW_CANDIDATES.find(({ filename }) => files.includes(filename));
  if (!candidate) {
    return null;
  }
  return {
    ...candidate,
    url: buildVersionFileUrl(apiBaseUrl, designId, versionNo, candidate.filename),
  };
}
