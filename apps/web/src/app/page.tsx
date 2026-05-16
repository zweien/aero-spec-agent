"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { CadViewer } from "@/components/cad-viewer/CadViewer";
import {
  selectCadPreviewSource,
  type CadPreviewSource,
} from "@/components/cad-viewer/cadPreviewSource";
import type { AircraftPreviewSpec } from "@/components/cad-viewer/previewGeometry";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { ParameterPanel } from "@/components/parameter-panel/ParameterPanel";
import type { AircraftSpecData } from "@/components/parameter-panel/ParameterPanel";
import { SettingsPanel } from "@/components/settings-panel/SettingsPanel";
import { VersionPanel } from "@/components/version-panel/VersionPanel";

type VersionResponse = {
  files: string[];
  validation_report?: {
    spec_echo?: Record<string, unknown>;
    design_rules?: {
      rules: DesignRuleEntry[];
      summary: Record<string, number>;
    };
    performance_estimate?: {
      estimates: PerformanceEstimateEntry[];
      summary: Record<string, number>;
    };
    vspaero_analysis?: VspaeroAnalysisEntry;
  };
};

export type DesignRuleEntry = {
  rule_id: string;
  label: string;
  status: "pass" | "warn" | "fail" | "skip";
  value: number | string;
  expected: string;
  message: string;
};

export type PerformanceEstimateEntry = {
  estimate_id: string;
  label: string;
  value: number;
  unit: string;
  confidence: "high" | "medium" | "low";
  method: string;
  status: "reasonable" | "warning" | "unusual";
  typical_range: string;
  message: string;
};

export type AeroSweepPoint = {
  alpha: number;
  cl: number;
  cd: number;
  cm: number;
};

export type VspaeroAnalysisEntry = {
  status: "success" | "skipped" | "failed";
  method: string;
  optimal_ld: number;
  optimal_cl: number;
  optimal_alpha: number;
  cl_alpha?: number;
  cd0_estimate?: number;
  alpha_sweep: AeroSweepPoint[];
  cruise_point?: AeroSweepPoint;
  error_message?: string;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8900";

export default function Home() {
  const [conversationId] = useState(() => crypto.randomUUID());
  const [previewSource, setPreviewSource] = useState<CadPreviewSource | null>(
    null,
  );
  const [previewSpec, setPreviewSpec] =
    useState<AircraftPreviewSpec | null>(null);
  const [specData, setSpecData] = useState<AircraftSpecData | null>(null);
  const [draftSpec, setDraftSpec] = useState<AircraftSpecData | null>(null);
  const [pendingChanges, setPendingChanges] = useState<Map<string, string | number>>(new Map());
  const [designRules, setDesignRules] = useState<DesignRuleEntry[] | null>(null);
  const [perfEstimates, setPerfEstimates] = useState<PerformanceEstimateEntry[] | null>(null);
  const [aeroAnalysis, setAeroAnalysis] = useState<VspaeroAnalysisEntry | null>(null);

  const chatSendMessageRef = useRef<((text: string) => void) | null>(null);
  const [chatWidth, setChatWidth] = useState(38);
  const mainRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current || !mainRef.current) return;
      const rect = mainRef.current.getBoundingClientRect();
      const pct = ((e.clientX - rect.left) / rect.width) * 100;
      setChatWidth(Math.max(28, Math.min(55, pct)));
    };
    const onUp = () => {
      dragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  const handleDragStart = useCallback(() => {
    dragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  useEffect(() => {
    setDraftSpec(specData);
    setPendingChanges(new Map());
  }, [specData]);

  const registerSendMessage = useCallback((fn: (text: string) => void) => {
    chatSendMessageRef.current = fn;
  }, []);

  const loadVersion = useCallback(
    async (designId: string, versionNo: number) => {
      const resp = await fetch(
        `${API_BASE_URL}/api/designs/${designId}/versions/${versionNo}`,
      );
      if (!resp.ok) return;

      const version = (await resp.json()) as VersionResponse;
      setPreviewSpec(
        (version.validation_report?.spec_echo ?? null) as AircraftPreviewSpec | null,
      );
      setSpecData(
        (version.validation_report?.spec_echo ?? null) as AircraftSpecData | null,
      );
      setDesignRules(
        version.validation_report?.design_rules?.rules ?? null,
      );
      setPerfEstimates(
        version.validation_report?.performance_estimate?.estimates ?? null,
      );
      setAeroAnalysis(
        version.validation_report?.vspaero_analysis ?? null,
      );

      const source = selectCadPreviewSource({
        apiBaseUrl: API_BASE_URL,
        designId,
        versionNo,
        files: version.files,
      });
      setPreviewSource(source);
    },
    [],
  );

  const handleGenerationComplete = useCallback(
    (data: { design_id?: string; version_no?: number; status?: string; files?: string[] }) => {
      const convId = data.design_id ?? conversationId;
      const vNo = data.version_no;
      if (!vNo) return;
      void loadVersion(convId, vNo).catch(() => {});
    },
    [conversationId, loadVersion],
  );

  const handleParameterChange = useCallback(
    (path: string, value: string | number) => {
      setDraftSpec((prev) => {
        if (!prev) return prev;
        const next = JSON.parse(JSON.stringify(prev));
        _setNested(next, path, value);
        return next;
      });
      setPendingChanges((prev) => new Map(prev).set(path, value));
    },
    [],
  );

  const handleApplyChanges = useCallback(() => {
    if (pendingChanges.size === 0) return;
    const parts = Array.from(pendingChanges.entries()).map(
      ([path, value]) => `${path} = ${value}`,
    );
    const msg = `修改参数：\n${parts.join("\n")}`;
    chatSendMessageRef.current?.(msg);
    setPendingChanges(new Map());
  }, [pendingChanges]);

  return (
    <main className="workbench">
      <nav className="topbar">
        <strong>AeroSpec</strong>
        <span className="topbar-sep" />
        <span className="topbar-sub">固定翼无人机概念设计</span>
        <div className="topbar-right">
          <SettingsPanel apiBaseUrl={API_BASE_URL} />
        </div>
      </nav>
      <div className="main-content" ref={mainRef}>
        <div className="chat-column" style={{ width: `${chatWidth}%` }}>
          <ChatPanel
            conversationId={conversationId}
            apiBaseUrl={API_BASE_URL}
            onGenerationComplete={handleGenerationComplete}
            registerSendMessage={registerSendMessage}
          />
        </div>
        <div
          className="resize-handle"
          onMouseDown={handleDragStart}
        />
        <div className="workspace">
          <CadViewer
            modelFormat={previewSource?.format}
            modelUrl={previewSource?.url}
            spec={previewSpec}
          />
          <ParameterPanel
            spec={draftSpec}
            onParameterChange={handleParameterChange}
            onApplyChanges={handleApplyChanges}
            pendingCount={pendingChanges.size}
          />
        </div>
      </div>
      <VersionPanel
        designRules={designRules}
        perfEstimates={perfEstimates}
        aeroAnalysis={aeroAnalysis}
      />
    </main>
  );
}

function _setNested(obj: Record<string, unknown>, path: string, value: unknown) {
  const keys = path.split(".");
  let current: Record<string, unknown> = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    const next = current[keys[i]];
    if (next == null || typeof next !== "object") return;
    current = next as Record<string, unknown>;
  }
  current[keys[keys.length - 1]] = value;
}
