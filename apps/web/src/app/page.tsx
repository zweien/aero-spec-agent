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
import { VersionPanel } from "@/components/version-panel/VersionPanel";

type VersionResponse = {
  files: string[];
  validation_report?: {
    spec_echo?: Record<string, unknown>;
  };
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8900";

export default function Home() {
  const [conversationId] = useState(() => crypto.randomUUID());
  const [files, setFiles] = useState<string[]>([]);
  const [jobStatus, setJobStatus] = useState<string | undefined>();
  const [versionNo, setVersionNo] = useState<number | undefined>();
  const [previewSource, setPreviewSource] = useState<CadPreviewSource | null>(
    null,
  );
  const [previewSpec, setPreviewSpec] =
    useState<AircraftPreviewSpec | null>(null);
  const [specData, setSpecData] = useState<AircraftSpecData | null>(null);

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

  const handleGenerationComplete = useCallback(
    (data: { design_id?: string; version_no?: number; status?: string; files?: string[] }) => {
      setJobStatus(data.status);
      if (data.version_no) setVersionNo(data.version_no);

      const convId = data.design_id ?? conversationId;
      const vNo = data.version_no;
      if (!vNo) return;

      void (async () => {
        try {
          const resp = await fetch(
            `${API_BASE_URL}/api/designs/${convId}/versions/${vNo}`,
          );
          if (!resp.ok) return;

          const version = (await resp.json()) as VersionResponse;
          setFiles(version.files);
          setPreviewSpec(
            (version.validation_report?.spec_echo ?? null) as AircraftPreviewSpec | null,
          );
          setSpecData(
            (version.validation_report?.spec_echo ?? null) as AircraftSpecData | null,
          );

          const source = selectCadPreviewSource({
            apiBaseUrl: API_BASE_URL,
            designId: convId,
            versionNo: vNo,
            files: version.files,
          });
          setPreviewSource(source);
        } catch {
          // non-critical
        }
      })();
    },
    [conversationId],
  );

  return (
    <main className="workbench">
      <nav className="topbar">
        <strong>AeroSpec</strong>
        <span className="topbar-sep" />
        <span className="topbar-sub">固定翼无人机概念设计</span>
      </nav>
      <div className="main-content" ref={mainRef}>
        <div className="chat-column" style={{ width: `${chatWidth}%` }}>
          <ChatPanel
            conversationId={conversationId}
            onGenerationComplete={handleGenerationComplete}
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
          <ParameterPanel spec={specData} />
        </div>
      </div>
      <VersionPanel
        apiBaseUrl={API_BASE_URL}
        designId={conversationId}
        files={files}
        jobStatus={jobStatus}
        versionNo={versionNo}
      />
    </main>
  );
}
