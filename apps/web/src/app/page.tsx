"use client";

import { useCallback, useRef, useState } from "react";

import { CadViewer } from "@/components/cad-viewer/CadViewer";
import {
  selectCadPreviewSource,
  type CadPreviewSource,
} from "@/components/cad-viewer/cadPreviewSource";
import type { AircraftPreviewSpec } from "@/components/cad-viewer/previewGeometry";
import {
  ChatPanel,
  type ChatMessage,
} from "@/components/chat/ChatPanel";
import { ParameterPanel } from "@/components/parameter-panel/ParameterPanel";
import type { AircraftSpecData } from "@/components/parameter-panel/ParameterPanel";
import { VersionPanel } from "@/components/version-panel/VersionPanel";

type VersionResponse = {
  files: string[];
  validation_report?: {
    spec_echo?: Record<string, unknown>;
  };
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8900";

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [files, setFiles] = useState<string[]>([]);
  const [jobStatus, setJobStatus] = useState<string | undefined>();
  const [versionNo, setVersionNo] = useState<number | undefined>();
  const [previewSource, setPreviewSource] = useState<CadPreviewSource | null>(null);
  const [previewSpec, setPreviewSpec] = useState<AircraftPreviewSpec | null>(null);
  const [specData, setSpecData] = useState<AircraftSpecData | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleSend = useCallback(
    async (message: string) => {
      const convId = conversationId ?? crypto.randomUUID();
      if (!conversationId) setConversationId(convId);

      setMessages((prev) => [...prev, { role: "user", content: message }]);
      setIsGenerating(true);

      const assistantIndex = messages.length + 1;
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "" },
      ]);

      const abortController = new AbortController();
      abortRef.current = abortController;

      try {
        const response = await fetch(`${API_BASE_URL}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            conversation_id: convId,
            message,
          }),
          signal: abortController.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(`请求失败：HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          let eventType = "";
          for (const line of lines) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              const dataStr = line.slice(6);
              try {
                const data = JSON.parse(dataStr);
                handleSSEEvent(
                  eventType,
                  data,
                  assistantIndex,
                  convId,
                );
              } catch {
                // skip malformed data lines
              }
              eventType = "";
            }
          }
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setMessages((prev) => [
          ...prev,
          {
            role: "error",
            content: err instanceof Error ? err.message : "请求失败",
          },
        ]);
      } finally {
        setIsGenerating(false);
        abortRef.current = null;
      }
    },
    [conversationId, messages.length],
  );

  const handleSSEEvent = useCallback(
    (
      eventType: string,
      data: Record<string, unknown>,
      assistantIdx: number,
      convId: string,
    ) => {
      switch (eventType) {
        case "message":
          setMessages((prev) => {
            const updated = [...prev];
            if (updated[assistantIdx]) {
              updated[assistantIdx] = {
                ...updated[assistantIdx],
                content: updated[assistantIdx].content + String(data.content ?? ""),
              };
            }
            return updated;
          });
          break;

        case "tool_call":
          setMessages((prev) => [
            ...prev,
            {
              role: "generating",
              content: `正在${data.name === "generate_design" ? "生成设计" : "修改设计"}...`,
            },
          ]);
          break;

        case "generation_started":
          setJobStatus("running");
          break;

        case "generation_complete":
          setJobStatus("ready");
          if (data.version_no) setVersionNo(data.version_no as number);
          void refreshAfterGeneration(convId, data.version_no as number);
          break;

        case "error":
          setMessages((prev) => [
            ...prev,
            { role: "error", content: String(data.content ?? "发生错误") },
          ]);
          break;
      }
    },
    [],
  );

  const refreshAfterGeneration = useCallback(
    async (convId: string, vNo: number) => {
      try {
        const versionResp = await fetch(
          `${API_BASE_URL}/api/designs/${convId}/versions/${vNo}`,
        );
        if (!versionResp.ok) return;

        const version = (await versionResp.json()) as VersionResponse;
        setFiles(version.files);
        setPreviewSpec((version.validation_report?.spec_echo ?? null) as AircraftPreviewSpec | null);
        setSpecData((version.validation_report?.spec_echo ?? null) as AircraftSpecData | null);

        const source = selectCadPreviewSource({
          apiBaseUrl: API_BASE_URL,
          designId: convId,
          versionNo: vNo,
          files: version.files,
        });
        setPreviewSource(source);
      } catch {
        // non-critical — preview will stay in parameter mode
      }
    },
    [],
  );

  return (
    <main className="workbench">
      <nav className="topbar">
        <strong>AeroSpec Agent</strong>
        <span>固定翼无人机概念设计 MVP</span>
      </nav>
      <div className="main-grid">
        <ChatPanel
          messages={messages}
          isGenerating={isGenerating}
          onSend={handleSend}
        />
        <CadViewer
          modelFormat={previewSource?.format}
          modelUrl={previewSource?.url}
          spec={previewSpec}
        />
        <ParameterPanel spec={specData} />
      </div>
      <VersionPanel
        apiBaseUrl={API_BASE_URL}
        designId={conversationId ?? "demo"}
        files={files}
        jobStatus={jobStatus}
        versionNo={versionNo}
      />
    </main>
  );
}
