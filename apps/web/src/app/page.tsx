"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { CadViewer } from "@/components/cad-viewer/CadViewer";
import {
  selectCadPreviewSource,
  type CadPreviewSource,
} from "@/components/cad-viewer/cadPreviewSource";
import type { AircraftPreviewSpec } from "@/components/cad-viewer/previewGeometry";
import { ChatPanel, type GenerationCompleteData } from "@/components/chat/ChatPanel";
import { pollJobToCompletion } from "@/lib/generationFlow";
import { ParameterPanel } from "@/components/parameter-panel/ParameterPanel";
import type { AircraftSpecData } from "@/components/parameter-panel/ParameterPanel";
import { SettingsPanel } from "@/components/settings-panel/SettingsPanel";
import { VersionPanel } from "@/components/version-panel/VersionPanel";
import { DeepDesignPanel } from "@/components/graph/DeepDesignPanel";
import { useDeepDesignStream } from "@/components/graph/useDeepDesignStream";
import { CompareDrawer } from "@/components/compare/CompareDrawer";
import { useCompareItems, extractCompareMetrics } from "@/components/compare";
import type { CompareItem, CompareMetrics } from "@/components/compare/types";

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
    design_metrics?: {
      wingspan_m?: number;
      fuselage_length_m?: number;
      wing_area_m2?: number;
      aspect_ratio?: number;
      estimated_lift_to_drag?: number;
      estimated_range_km?: number;
      estimated_endurance_h?: number;
      wing_loading_kg_m2?: number;
      risk_level?: string;
      [key: string]: unknown;
    };
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
  const [designMetrics, setDesignMetrics] = useState<CompareMetrics | null>(null);
  const [versionList, setVersionList] = useState<number[]>([]);
  const [currentVersionNo, setCurrentVersionNo] = useState<number | undefined>(undefined);
  const [designId, setDesignId] = useState<string | null>(null);
  const [isApplyingChanges, setIsApplyingChanges] = useState(false);
  const [compareVersions, setCompareVersions] = useState<[number, number] | null>(null);
  const [compareData, setCompareData] = useState<[VersionResponse, VersionResponse] | null>(null);
  const [selectedRefs, setSelectedRefs] = useState<string[]>([]);
  const [rightTab, setRightTab] = useState<"parameters" | "deep-design">("parameters");
  const [generationStage, setGenerationStage] = useState<string | null>(null);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationArtifacts, setGenerationArtifacts] = useState<string[]>([]);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const deepDesignStream = useDeepDesignStream();
  const compareState = useCompareItems();
  const [compareDrawerOpen, setCompareDrawerOpen] = useState(false);
  const compareFull = compareState.items.length >= compareState.maxItems;

  const chatSystemMessageRef = useRef<((text: string) => void) | null>(null);
  const chatToolActionRef = useRef<((toolName: string, args: Record<string, unknown>) => import("@/components/chat/ChatPanel").ToolActionHandle) | null>(null);
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

  const registerSystemMessage = useCallback((fn: (text: string) => void) => {
    chatSystemMessageRef.current = fn;
  }, []);

  const registerToolAction = useCallback((fn: (toolName: string, args: Record<string, unknown>) => import("@/components/chat/ChatPanel").ToolActionHandle) => {
    chatToolActionRef.current = fn;
  }, []);

  const fetchVersionList = useCallback(async (id: string) => {
    const resp = await fetch(`${API_BASE_URL}/api/designs/${id}/versions`);
    if (!resp.ok) return;
    const versions = (await resp.json()) as Array<{ version_no: number }>;
    setVersionList(versions.map((v) => v.version_no));
  }, []);

  const loadVersion = useCallback(
    async (dId: string, versionNo: number) => {
      const resp = await fetch(
        `${API_BASE_URL}/api/designs/${dId}/versions/${versionNo}`,
      );
      if (!resp.ok) return;

      const version = (await resp.json()) as VersionResponse;
      setDesignId(dId);
      setCurrentVersionNo(versionNo);
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
      const dm = version.validation_report?.design_metrics;
      setDesignMetrics(
        dm
          ? {
              wingspan_m: dm.wingspan_m as number | undefined,
              fuselage_length_m: dm.fuselage_length_m as number | undefined,
              wing_area_m2: dm.wing_area_m2 as number | undefined,
              aspect_ratio: dm.aspect_ratio as number | undefined,
              estimated_lift_to_drag: dm.estimated_lift_to_drag as number | undefined,
              estimated_range_km: dm.estimated_range_km as number | undefined,
              estimated_endurance_h: dm.estimated_endurance_h as number | undefined,
              wing_loading_kg_m2: dm.wing_loading_kg_m2 as number | undefined,
              risk_level: (["low", "medium", "high", "unknown"].includes(dm.risk_level as string)
                ? (dm.risk_level as "low" | "medium" | "high" | "unknown")
                : undefined),
              metric_sources: Object.fromEntries(
                Object.entries(dm).filter(([_, v]) => v != null).map(([k]) => [k, "backend_design_metrics"]),
              ),
              confidence: "high",
              warnings: [],
            }
          : null,
      );

      const source = selectCadPreviewSource({
        apiBaseUrl: API_BASE_URL,
        designId: dId,
        versionNo,
        files: version.files,
      });
      setPreviewSource(source);
      setCompareVersions(null);
      setCompareData(null);
      void fetchVersionList(dId);
    },
    [fetchVersionList],
  );

  const handleGenerationComplete = useCallback(
    (data: { design_id?: string; version_no?: number; status?: string; files?: string[] }) => {
      const convId = data.design_id ?? conversationId;
      const vNo = data.version_no;
      if (!vNo) return;
      setDesignId(convId);
      void loadVersion(convId, vNo).then(() => fetchVersionList(convId)).catch(() => {});
    },
    [conversationId, loadVersion, fetchVersionList],
  );

  const handleViewModel = useCallback(
    (data: GenerationCompleteData) => {
      const activeDesignId = data.design_id ?? designId;
      if (activeDesignId && data.version_no) {
        void loadVersion(activeDesignId, data.version_no);
      }
      document.querySelector(".workspace-cad")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    },
    [designId, loadVersion],
  );

  const handleOpenDeepDesign = useCallback(
    (data: GenerationCompleteData) => {
      if (data.design_id) setDesignId(data.design_id);
      setRightTab("deep-design");
    },
    [],
  );

  const handleExportReport = useCallback(
    (data: GenerationCompleteData) => {
      const activeDesignId = data.design_id ?? designId;
      if (!activeDesignId || !data.version_no) return;
      const url = `${API_BASE_URL}/api/designs/${encodeURIComponent(activeDesignId)}/versions/${data.version_no}/files/validation_report.json`;
      window.open(url, "_blank", "noopener,noreferrer");
    },
    [designId],
  );

  const handleShowRunDetails = useCallback((_data: GenerationCompleteData) => {}, []);

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

  const handleApplyChanges = useCallback(async () => {
    if (pendingChanges.size === 0 || isApplyingChanges) return;
    const activeDesignId = designId ?? conversationId;
    const changes = Array.from(pendingChanges.entries()).map(
      ([path, value]) => ({ path, value }),
    );

    const args: Record<string, unknown> = { changes };
    const action = chatToolActionRef.current?.("modify_design", args);
    if (!action) return;

    setIsApplyingChanges(true);

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/designs/${activeDesignId}/spec`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ changes }),
        },
      );

      if (!response.ok) {
        action.fail("参数修改失败：后端未接受当前补丁。");
        return;
      }

      const job = (await response.json()) as {
        id?: string;
        job_id?: string;
        design_id?: string;
        error_message?: string;
        version_no?: number;
        status?: string;
        files?: Record<string, string>;
      };

      const jobId = job.job_id ?? job.id ?? "";
      const completedJob = await pollJobToCompletion({
        apiBaseUrl: API_BASE_URL,
        jobId,
        initialStatus: job.status,
        design_id: job.design_id,
        version_no: job.version_no,
        files: job.files,
      });

      if (
        completedJob.status !== "succeeded" ||
        !completedJob.version_no
      ) {
        action.fail(`参数修改失败：${completedJob.error_message ?? job.error_message ?? "生成任务未完成"}`);
        return;
      }

      const updatedDesignId = completedJob.design_id ?? activeDesignId;
      setDesignId(updatedDesignId);
      await loadVersion(updatedDesignId, completedJob.version_no);
      await fetchVersionList(updatedDesignId);

      action.complete({
        status: completedJob.status,
        design_id: updatedDesignId,
        version_no: completedJob.version_no,
        files: completedJob.files,
      });
      setPendingChanges(new Map());
    } catch (exc) {
      const message = exc instanceof Error ? exc.message : "请求失败";
      action.fail(`参数修改失败：${message}`);
    } finally {
      setIsApplyingChanges(false);
    }
  }, [
    conversationId,
    designId,
    fetchVersionList,
    isApplyingChanges,
    loadVersion,
    pendingChanges,
  ]);

  const handleSelectPart = useCallback((partRef: string | null) => {
    setSelectedRefs(partRef ? [partRef] : []);
  }, []);

  const handleClearSelectedRefs = useCallback(() => {
    setSelectedRefs([]);
  }, []);

  const handleDeepDesignComplete = useCallback(() => {
    setRightTab("deep-design");
    if (designId) void fetchVersionList(designId);
  }, [designId, fetchVersionList]);

  // Auto-switch back to deep-design tab when stream completes
  const prevDDStatusRef = useRef(deepDesignStream.status);
  useEffect(() => {
    if (prevDDStatusRef.current === "running" && deepDesignStream.status === "completed") {
      handleDeepDesignComplete();
    }
    prevDDStatusRef.current = deepDesignStream.status;
  }, [deepDesignStream.status, handleDeepDesignComplete]);

  const handleCompare = useCallback(
    async (v1: number, v2: number) => {
      if (!designId) return;
      const [r1, r2] = await Promise.all([
        fetch(`${API_BASE_URL}/api/designs/${designId}/versions/${v1}`).then((r) => r.json()),
        fetch(`${API_BASE_URL}/api/designs/${designId}/versions/${v2}`).then((r) => r.json()),
      ]);
      setCompareData([r1 as VersionResponse, r2 as VersionResponse]);
      setCompareVersions([v1, v2]);
    },
    [designId],
  );

  const handleCancelCompare = useCallback(() => {
    setCompareVersions(null);
    setCompareData(null);
  }, []);

  const handleSelectVersion = useCallback(
    (versionNo: number) => {
      if (!designId) return;
      void loadVersion(designId, versionNo);
    },
    [designId, loadVersion],
  );

  const handleAddToCompare = useCallback(
    async (item: CompareItem) => {
      // Fetch version data to enrich the compare item
      const dId = item.designId || designId;
      if (dId && item.versionNo) {
        try {
          const resp = await fetch(`${API_BASE_URL}/api/designs/${dId}/versions/${item.versionNo}`);
          if (resp.ok) {
            const data = (await resp.json()) as VersionResponse;
            const specEcho = data.validation_report?.spec_echo;
            const enriched: CompareItem = {
              ...item,
              designId: dId,
              spec: specEcho as Record<string, unknown> | undefined,
              artifacts: data.files,
              validationReport: data.validation_report as Record<string, unknown> | undefined,
              defaultedFields: (data.validation_report as Record<string, unknown>)?.defaulted_fields as CompareItem["defaultedFields"],
            };
            enriched.metrics = extractCompareMetrics(enriched);
            compareState.addCompareItem(enriched);
            return;
          }
        } catch { /* fall through */ }
      }
      compareState.addCompareItem({ ...item, metrics: extractCompareMetrics(item) });
    },
    [designId, compareState.addCompareItem],
  );

  const handleCompareViewModel = useCallback(
    (item: CompareItem) => {
      void loadVersion(item.designId, item.versionNo);
    },
    [loadVersion],
  );

  const handleCompareSetCurrent = useCallback(
    (item: CompareItem) => {
      void loadVersion(item.designId, item.versionNo);
    },
    [loadVersion],
  );

  return (
    <main className="workbench">
      <nav className="topbar">
        <strong>AeroSpec</strong>
        <span className="topbar-sep" />
        <span className="topbar-sub">固定翼无人机概念设计</span>
        <div className="topbar-right">
          <button
            onClick={() => setCompareDrawerOpen(true)}
            className={`topbar-compare${compareState.items.length > 0 ? " topbar-compare-active" : ""}`}
          >
            方案对比{compareState.items.length > 0 ? ` (${compareState.items.length})` : ""}
          </button>
          <SettingsPanel apiBaseUrl={API_BASE_URL} />
        </div>
      </nav>
      <div className="main-content" ref={mainRef}>
        <div className="chat-column" style={{ width: `${chatWidth}%` }}>
          <ChatPanel
            conversationId={conversationId}
            apiBaseUrl={API_BASE_URL}
            onGenerationComplete={handleGenerationComplete}
            onClearSelectedRefs={handleClearSelectedRefs}
            registerSystemMessage={registerSystemMessage}
            registerToolAction={registerToolAction}
	            selectedRefs={selectedRefs}
	            onViewModel={handleViewModel}
	            onDeepDesign={handleOpenDeepDesign}
	            onExportReport={handleExportReport}
	            onShowDetails={handleShowRunDetails}
	            onGenerationStage={(stage, progress, generating, extras) => {
              setGenerationStage(stage);
              setGenerationProgress(progress);
              setIsGenerating(generating);
              setGenerationArtifacts(extras?.artifacts ?? []);
              setGenerationError(extras?.error ?? null);
            }}
          />
        </div>
        <div
          className="resize-handle"
          onMouseDown={handleDragStart}
        />
        <div className="workspace">
          <div className="workspace-cad">
            <CadViewer
              modelFormat={previewSource?.format}
              modelUrl={previewSource?.url}
              spec={previewSpec}
              onSelectPart={handleSelectPart}
              runtimeStatus={{
                status: isGenerating ? "running" : (generationError ? "failed" : "idle"),
                currentStageLabel: generationStage ?? undefined,
                progress: generationProgress,
                artifacts: generationArtifacts,
                error: generationError,
              }}
            />
          </div>
          <div className="right-panel">
            <div className="right-panel-tabs">
              <button
                className={`right-panel-tab ${rightTab === "parameters" ? "active" : ""}`}
                onClick={() => setRightTab("parameters")}
              >
                参数编辑
              </button>
              <button
                className={`right-panel-tab ${rightTab === "deep-design" ? "active" : ""}`}
                onClick={() => setRightTab("deep-design")}
              >
                深度设计
              </button>
            </div>
            <div className="right-panel-content">
              {rightTab === "parameters" && (
                <ParameterPanel
                  spec={draftSpec}
                  onParameterChange={handleParameterChange}
                  onApplyChanges={handleApplyChanges}
                  pendingCount={pendingChanges.size}
                  isApplying={isApplyingChanges}
                />
              )}
              {rightTab === "deep-design" && (
                <DeepDesignPanel
                  apiBaseUrl={API_BASE_URL}
                  defaultSpec={specData ?? undefined}
                  stream={deepDesignStream}
                  onComplete={handleDeepDesignComplete}
                  designId={designId}
                  onLoadVersion={loadVersion}
                  onSwitchToParameters={() => setRightTab("parameters")}
                  isInCompare={compareState.isInCompare}
                  onAddToCompare={handleAddToCompare}
                  compareFull={compareFull}
                />
              )}
            </div>
          </div>
        </div>
      </div>
      <VersionPanel
        designRules={designRules}
        perfEstimates={perfEstimates}
        aeroAnalysis={aeroAnalysis}
        designMetrics={designMetrics}
        versionList={versionList}
        currentVersionNo={currentVersionNo}
        designId={designId}
        onCompare={handleCompare}
        onCancelCompare={handleCancelCompare}
        onSelectVersion={handleSelectVersion}
        compareVersions={compareVersions}
        compareData={compareData}
        isInGlobalCompare={compareState.isInCompare}
        onAddToGlobalCompare={handleAddToCompare}
        compareFull={compareFull}
      />
      <CompareDrawer
        open={compareDrawerOpen}
        items={compareState.items}
        onClose={() => setCompareDrawerOpen(false)}
        onRemove={compareState.removeCompareItem}
        onClear={compareState.clearCompareItems}
        onViewModel={handleCompareViewModel}
        onSetCurrent={handleCompareSetCurrent}
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
