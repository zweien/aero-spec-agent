"use client";

import { useMemo, useState } from "react";

import { CadViewer } from "@/components/cad-viewer/CadViewer";
import type { AircraftPreviewSpec } from "@/components/cad-viewer/previewGeometry";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { ParameterPanel } from "@/components/parameter-panel/ParameterPanel";
import { VersionPanel } from "@/components/version-panel/VersionPanel";

type JobResponse = {
  id: string;
  status: string;
  version_no: number;
  files: Record<string, string>;
};

type VersionResponse = {
  files: string[];
  validation_report?: {
    spec_echo?: AircraftPreviewSpec;
  };
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8900";

const EXAMPLE_SPEC = `schema_version: "0.1"
aircraft:
  name: twin_engine_uav
  type: fixed_wing_uav
  layout: conventional
mission:
  cruise_speed:
    value: 120
    unit: km/h
    source: user
    confidence: 1.0
  payload:
    value: 30
    unit: kg
    source: user
    confidence: 1.0
fuselage:
  length:
    value: 7.0
    unit: m
    source: rule_default
    confidence: 0.7
wing:
  position:
    value: high
    source: user
    confidence: 1.0
  span:
    value: 12.0
    unit: m
    source: user
    confidence: 1.0
  root_chord:
    value: 1.2
    unit: m
    source: rule_default
    confidence: 0.75
  tip_chord:
    value: 0.6
    unit: m
    source: rule_default
    confidence: 0.75
tail:
  type:
    value: conventional
    source: user
    confidence: 1.0
engine:
  count:
    value: 2
    source: user
    confidence: 1.0
`;

export default function Home() {
  const [error, setError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [files, setFiles] = useState<string[]>([]);
  const [previewSpec, setPreviewSpec] = useState<AircraftPreviewSpec | null>(null);

  const parameters = useMemo(
    () => [
      { label: "翼展", scalar: { value: 12.0, unit: "m", source: "user", confidence: 1.0 } },
      { label: "发动机数量", scalar: { value: 2, source: "user", confidence: 1.0 } },
      { label: "机翼位置", scalar: { value: "high", source: "user", confidence: 1.0 } },
      { label: "尾翼", scalar: { value: "conventional", source: "user", confidence: 1.0 } },
    ],
    []
  );

  async function handleGenerate() {
    setError(null);
    setIsGenerating(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/designs/demo/generate`, {
        method: "POST",
        body: EXAMPLE_SPEC,
      });

      if (!response.ok) {
        throw new Error(`生成请求失败：HTTP ${response.status}`);
      }

      const nextJob = (await response.json()) as JobResponse;
      setJob(nextJob);

      const versionResponse = await fetch(
        `${API_BASE_URL}/api/designs/demo/versions/${nextJob.version_no}`
      );

      if (!versionResponse.ok) {
        throw new Error(`版本请求失败：HTTP ${versionResponse.status}`);
      }

      const version = (await versionResponse.json()) as VersionResponse;
      setFiles(version.files);
      setPreviewSpec(version.validation_report?.spec_echo ?? null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "生成失败");
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <main className="workbench">
      <nav className="topbar">
        <strong>AeroSpec Agent</strong>
        <span>固定翼无人机概念设计 MVP</span>
      </nav>
      <div className="main-grid">
        <ChatPanel error={error} isGenerating={isGenerating} onGenerate={handleGenerate} />
        <CadViewer glbPath={job?.files.glb} spec={previewSpec} />
        <ParameterPanel parameters={parameters} />
      </div>
      <VersionPanel jobStatus={job?.status} versionNo={job?.version_no} files={files} />
    </main>
  );
}
