"use client";

import { type JSX, useCallback, useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { resolveGenerationJob } from "@/lib/generationFlow";
import { TaskRuntimeCard } from "@/components/runtime/TaskRuntimeCard";
import {
  useWorkflowRuntime,
  getStageLabel,
  type WorkflowRuntimeStage,
  type WorkflowStageEvent,
} from "@/hooks/useWorkflowRuntime";
import { createChatSseParser } from "./chatSse";
import {
  streamJobEvents,
  toJobPollResult,
  type WorkflowStage,
} from "./useJobEventStream";
import { AgentRunHeader } from "./AgentRunHeader";
import { AgentRunActions } from "./AgentRunActions";
import { AgentRunDetails } from "./AgentRunDetails";

export type GenerationCompleteData = {
  job_id?: string;
  id?: string;
  status?: string;
  version_no?: number;
  design_id?: string;
  files?: string[];
  message?: string;
};

type ChatRole = "user" | "assistant" | "system" | "error";

type TextPart = {
  type: "text";
  text: string;
};

type ToolPart = {
  type: "tool";
  toolCallId: string;
  toolName: string;
  args?: Record<string, unknown>;
  output?: Record<string, unknown>;
  state: "running" | "done";
  workflowStages?: WorkflowStage[];
  runtimeStages?: WorkflowRuntimeStage[];
  runtimeProgress?: number;
  runtimeElapsedTime?: number;
};

type ChatMessage = {
  id: string;
  role: ChatRole;
  parts: Array<TextPart | ToolPart>;
};

export type ToolActionHandle = {
  complete: (output: GenerationCompleteData) => void;
  fail: (errorMsg: string) => void;
};

type ChatPanelProps = {
  conversationId: string;
  apiBaseUrl: string;
  onGenerationComplete: (data: GenerationCompleteData) => void;
  onClearSelectedRefs?: () => void;
  registerSendMessage?: (fn: (text: string) => void) => void;
  registerSystemMessage?: (fn: (text: string) => void) => void;
  registerToolAction?: (fn: (toolName: string, args: Record<string, unknown>) => ToolActionHandle) => void;
  selectedRefs?: string[];
  onGenerationStage?: (stage: string | null, progress: number, isGenerating: boolean, extras?: { artifacts?: string[]; error?: string | null }) => void;
};

const PART_REF_LABELS: Record<string, string> = {
  "part:fuselage": "机身",
  "part:main_wing": "主翼",
  "part:tail": "尾翼",
  "part:left_engine": "左发动机",
  "part:right_engine": "右发动机",
};

const TOOL_LABELS: Record<string, string> = {
  generate_design: "生成设计",
  modify_design: "修改设计",
  modify_selected_part: "修改选中部件",
};

export function ChatPanel({
  conversationId,
  apiBaseUrl,
  onGenerationComplete,
  onClearSelectedRefs,
  registerSendMessage,
  registerSystemMessage,
  registerToolAction,
  selectedRefs = [],
  onGenerationStage,
}: ChatPanelProps) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<"idle" | "streaming">("idle");
  const scrollRef = useRef<HTMLDivElement>(null);
  const messageCounterRef = useRef(1);
  const toolCounterRef = useRef(1);
  const runtime = useWorkflowRuntime();

  const isStreaming = status === "streaming";

  const appendMessage = useCallback((role: ChatRole, text: string) => {
    setMessages((prev) => [
      ...prev,
      {
        id: `msg-${messageCounterRef.current++}`,
        role,
        parts: [{ type: "text", text }],
      },
    ]);
  }, []);

  const startToolAction = useCallback(
    (toolName: string, args: Record<string, unknown>): ToolActionHandle => {
      const messageId = `msg-${messageCounterRef.current++}`;
      setMessages((prev) => [
        ...prev,
        {
          id: messageId,
          role: "assistant" as ChatRole,
          parts: [
            { type: "text" as const, text: "" },
            {
              type: "tool" as const,
              toolCallId: `tool-${toolCounterRef.current++}`,
              toolName,
              args,
              state: "running" as const,
            },
          ],
        },
      ]);
      return {
        complete: (output: GenerationCompleteData) => {
          setMessages((prev) =>
            prev.map((msg) => {
              if (msg.id !== messageId) return msg;
              const parts = [...msg.parts];
              for (let i = parts.length - 1; i >= 0; i--) {
                const part = parts[i];
                if (part.type === "tool" && part.state === "running") {
                  parts[i] = { ...part, output, state: "done" };
                  break;
                }
              }
              return { ...msg, parts };
            }),
          );
          onGenerationComplete(output);
        },
        fail: (errorMsg: string) => {
          setMessages((prev) =>
            prev.map((msg) => {
              if (msg.id !== messageId) return msg;
              const parts = [...msg.parts];
              for (let i = parts.length - 1; i >= 0; i--) {
                const part = parts[i];
                if (part.type === "tool" && part.state === "running") {
                  parts[i] = { ...part, state: "done" };
                  break;
                }
              }
              return { ...msg, parts };
            }),
          );
          appendMessage("error", errorMsg);
        },
      };
    },
    [appendMessage, onGenerationComplete],
  );

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const appendAssistantText = useCallback((messageId: string, text: string) => {
    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== messageId) return msg;
        const parts = [...msg.parts];
        const last = parts[parts.length - 1];
        if (last?.type === "text") {
          parts[parts.length - 1] = { ...last, text: last.text + text };
        } else {
          parts.push({ type: "text", text });
        }
        return { ...msg, parts };
      }),
    );
  }, []);

  const appendToolCall = useCallback(
    (messageId: string, toolName: string, args: Record<string, unknown>) => {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId
            ? {
                ...msg,
                parts: [
                  ...msg.parts,
                  {
                    type: "tool",
                    toolCallId: `tool-${toolCounterRef.current++}`,
                    toolName,
                    args,
                    state: "running",
                  },
                ],
              }
            : msg,
        ),
      );
    },
    [],
  );

  const appendWorkflowStage = useCallback((messageId: string, stage: WorkflowStage) => {
    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== messageId) return msg;
        const parts = [...msg.parts];
        for (let i = parts.length - 1; i >= 0; i--) {
          const part = parts[i];
          if (part.type === "tool" && part.state === "running") {
            const stages = [...(part.workflowStages ?? []), stage];
            parts[i] = { ...part, workflowStages: stages };
            break;
          }
        }
        return { ...msg, parts };
      }),
    );
  }, []);

  const appendRuntimeStage = useCallback((messageId: string, stages: WorkflowRuntimeStage[], progress: number, elapsedTime: number) => {
    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== messageId) return msg;
        const parts = [...msg.parts];
        for (let i = parts.length - 1; i >= 0; i--) {
          const part = parts[i];
          if (part.type === "tool" && part.state === "running") {
            parts[i] = { ...part, runtimeStages: stages, runtimeProgress: progress, runtimeElapsedTime: elapsedTime };
            break;
          }
        }
        return { ...msg, parts };
      }),
    );
  }, []);

  const completeLatestTool = useCallback(
    (messageId: string, output: GenerationCompleteData) => {
      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.id !== messageId) return msg;
          const parts = [...msg.parts];
          for (let i = parts.length - 1; i >= 0; i--) {
            const part = parts[i];
            if (part.type === "tool" && part.state === "running") {
              parts[i] = { ...part, output, state: "done" };
              break;
            }
          }
          return { ...msg, parts };
        }),
      );
      onGenerationComplete(output);
    },
    [onGenerationComplete],
  );

  const failLatestTool = useCallback(
    (messageId: string, errorMsg: string, jobId?: string) => {
      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.id !== messageId) return msg;
          const parts = [...msg.parts];
          for (let i = parts.length - 1; i >= 0; i--) {
            const part = parts[i];
            if (part.type === "tool" && part.state === "running") {
              parts[i] = {
                ...part,
                state: "done",
                output: jobId ? { job_id: jobId, error: errorMsg } : undefined,
              };
              break;
            }
          }
          return { ...msg, parts };
        }),
      );
      appendMessage("error", errorMsg);
    },
    [appendMessage],
  );

  const sendChatMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || status === "streaming") return;

      const userId = `msg-${messageCounterRef.current++}`;
      const assistantId = `msg-${messageCounterRef.current++}`;
      setMessages((prev) => [
        ...prev,
        {
          id: userId,
          role: "user",
          parts: [{ type: "text", text: trimmed }],
        },
        {
          id: assistantId,
          role: "assistant",
          parts: [{ type: "text", text: "" }],
        },
      ]);
      setStatus("streaming");
      runtime.reset();
      runtime.applyPreliminaryStages(["understanding_requirements", "generating_spec"]);
      onGenerationStage?.(getStageLabel("understanding_requirements"), 0, true);

      const parser = createChatSseParser();
      try {
        const response = await fetch(`${apiBaseUrl}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            conversation_id: conversationId,
            message: trimmed,
            selected_refs: selectedRefs,
          }),
        });

        if (!response.ok || !response.body) {
          throw new Error(`Chat API failed with status ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          for (const event of parser.push(decoder.decode(value, { stream: true }))) {
            if (event.type === "message") {
              appendAssistantText(assistantId, String(event.data.content ?? ""));
            } else if (event.type === "tool_call") {
              let args: Record<string, unknown> = {};
              try {
                args = JSON.parse(String(event.data.arguments ?? "{}"));
              } catch {
                args = {};
              }
              appendToolCall(assistantId, String(event.data.name ?? ""), args);
            } else if (event.type === "generation_started") {
              const jobId = String(event.data.job_id ?? event.data.id ?? "");
              runtime.transitionToRealStages();
              onGenerationStage?.(getStageLabel(runtime.state.currentStage ?? "generating_cad"), runtime.state.progress, true, { artifacts: runtime.state.artifacts });
              if (jobId) {
                const ctrl = new AbortController();
                void streamJobEvents({
                  apiBaseUrl,
                  jobId,
                  signal: ctrl.signal,
                  onStage: (stage) => {
                    appendWorkflowStage(assistantId, stage);
                    const runtimeEvent: WorkflowStageEvent = {
                      stage: stage.stage ?? stage.step,
                      label: stage.label ?? getStageLabel(stage.stage ?? stage.step),
                      progress: stage.progress,
                      status: stage.status,
                      metadata: stage.metadata,
                      error_message: stage.error_message,
                    };
                    runtime.applyEvent(runtimeEvent);
                    appendRuntimeStage(assistantId, runtime.state.stages, runtime.state.progress, runtime.state.elapsedTime);
                    onGenerationStage?.(
                      getStageLabel(runtime.state.currentStage ?? stage.step),
                      runtime.state.progress,
                      true,
                      { artifacts: runtime.state.artifacts, error: runtime.state.error?.message },
                    );
                  },
                })
                  .then((result) => {
                    const jobResult = toJobPollResult(result, jobId);
                    if (result.finalStatus === "succeeded") {
                      runtime.markCompleted(jobResult.files);
                    }
                    const eventData = event.data as GenerationCompleteData;
                    completeLatestTool(assistantId, {
                      ...eventData,
                      ...jobResult,
                      // Preserve design_id from event.data if jobResult doesn't have it
                      design_id: jobResult.design_id || eventData.design_id,
                      job_id: jobId,
                    });
                    onGenerationStage?.(null, 0, false);
                  })
                  .catch(() => {
                    // Fallback to polling if SSE stream fails
                    void resolveGenerationJob({ apiBaseUrl, jobId })
                      .then((job) => {
                        const eventData = event.data as GenerationCompleteData;
                        completeLatestTool(assistantId, {
                          ...eventData,
                          ...job,
                          design_id: job.design_id || eventData.design_id,
                          job_id: job.id,
                        });
                        onGenerationStage?.(null, 0, false);
                      })
                      .catch((exc) => {
                        const message = exc instanceof Error ? exc.message : "生成任务失败";
                        failLatestTool(assistantId, message, jobId);
                        onGenerationStage?.(null, 0, false, { error: message });
                      });
                  });
              }
            } else if (event.type === "generation_complete") {
              const jobId = String(event.data.job_id ?? event.data.id ?? "");
              if (jobId && event.data.status !== "succeeded") {
                void resolveGenerationJob({ apiBaseUrl, jobId })
                  .then((job) => {
                    const eventData = event.data as GenerationCompleteData;
                    completeLatestTool(assistantId, {
                      ...eventData,
                      ...job,
                      design_id: job.design_id || eventData.design_id,
                      job_id: job.id,
                    });
                    onGenerationStage?.(null, 0, false);
                  })
                  .catch((exc) => {
                    const message = exc instanceof Error ? exc.message : "生成任务失败";
                    failLatestTool(assistantId, message, jobId);
                    onGenerationStage?.(null, 0, false, { error: message });
                  });
              } else {
                completeLatestTool(assistantId, event.data as GenerationCompleteData);
                onGenerationStage?.(null, 0, false);
              }
            } else if (event.type === "error") {
              appendMessage("error", String(event.data.content ?? "未知错误"));
            }
          }
        }
      } catch (exc) {
        const message = exc instanceof Error ? exc.message : "Chat 请求失败";
        appendMessage("error", message);
      } finally {
        setStatus("idle");
        onGenerationStage?.(null, 0, false);
      }
    },
    [
      apiBaseUrl,
      appendAssistantText,
      appendMessage,
      appendRuntimeStage,
      appendToolCall,
      appendWorkflowStage,
      completeLatestTool,
      failLatestTool,
      conversationId,
      onGenerationStage,
      runtime,
      selectedRefs,
      status,
    ],
  );

  useEffect(() => {
    registerSendMessage?.((text: string) => {
      void sendChatMessage(text);
    });
  }, [registerSendMessage, sendChatMessage]);

  useEffect(() => {
    registerSystemMessage?.((text: string) => {
      appendMessage("system", text);
    });
  }, [appendMessage, registerSystemMessage]);

  useEffect(() => {
    registerToolAction?.(startToolAction);
  }, [registerToolAction, startToolAction]);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;
    setInput("");
    void sendChatMessage(trimmed);
  }, [input, isStreaming, sendChatMessage]);

  return (
    <section className="panel chat-panel">
      <header>对话</header>
      <div className="chat-messages" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="chat-empty-icon">&#9992;</div>
            <p>
              描述你想要的飞机设计，例如「设计一架翼展 12
              米、双发、上单翼、常规尾翼的固定翼无人机」。
            </p>
          </div>
        )}
        {messages.map((msg) => {
          const hasToolPart = msg.parts.some((p) => p.type === "tool");
          const showPreliminaryTimeline = isStreaming && msg.role === "assistant" && !hasToolPart;

          return (
            <div
              key={msg.id}
              className={`chat-bubble chat-bubble-${msg.role}`}
            >
              <div className="chat-avatar">
                {msg.role === "user"
                  ? "你"
                  : msg.role === "system"
                    ? "系"
                    : msg.role === "error"
                      ? "!"
                      : "AI"}
              </div>
              <div className="chat-bubble-body">
                {/* --- Agent Run: Header (shows as soon as streaming starts) --- */}
                {msg.role === "assistant" && (() => {
                  const toolPart = msg.parts.find((p): p is ToolPart => p.type === "tool");
                  const isRunning = toolPart?.state === "running";
                  const result = toolPart?.output as GenerationCompleteData | undefined;
                  const isFailed = Boolean(toolPart && !isRunning && result?.job_id && !result?.version_no);
                  const isCompleted = Boolean(toolPart && !isRunning && !isFailed && result?.version_no);

                  // Show header for preliminary timeline (no toolPart yet) or when toolPart exists
                  const stages = toolPart?.runtimeStages ?? (showPreliminaryTimeline ? runtime.state.stages : []);
                  const progress = toolPart?.runtimeProgress ?? (showPreliminaryTimeline ? runtime.state.progress : 0);
                  const elapsedTime = toolPart?.runtimeElapsedTime ?? (showPreliminaryTimeline ? runtime.state.elapsedTime : 0);
                  const currentStageLabel = (() => {
                    const currentStage = runtime.state.currentStage;
                    return currentStage ? getStageLabel(currentStage) : undefined;
                  })();

                  if (stages.length === 0 && !isRunning && !isCompleted && !isFailed && !showPreliminaryTimeline) return null;
                  if (!toolPart && !showPreliminaryTimeline) return null;

                  const headerStatus = isRunning || showPreliminaryTimeline
                    ? "running" as const
                    : isFailed
                      ? "failed" as const
                      : isCompleted
                        ? "completed" as const
                        : "idle" as const;

                  if (headerStatus === "idle") return null;

                  return (
                    <AgentRunHeader
                      status={headerStatus}
                      currentStageLabel={currentStageLabel}
                      progress={progress}
                      elapsedTime={elapsedTime}
                    />
                  );
                })()}

                {/* --- TaskRuntimeCard: Timeline + Progress + Artifacts --- */}
                {showPreliminaryTimeline && runtime.state.stages.length > 0 && (
                  <TaskRuntimeCard
                    label="生成设计"
                    isRunning={true}
                    isFailed={false}
                    stages={runtime.state.stages}
                    progress={runtime.state.progress}
                    elapsedTime={runtime.state.elapsedTime}
                    artifacts={[]}
                  />
                )}
                {msg.role === "assistant" && hasToolPart && (() => {
                  const toolPart = msg.parts.find((p): p is ToolPart => p.type === "tool");
                  if (!toolPart) return null;
                  const isRunning = toolPart.state === "running";
                  const result = toolPart.output as GenerationCompleteData | undefined;
                  const isFailed = Boolean(!isRunning && result?.job_id && !result?.version_no);
                  const stages = toolPart.runtimeStages ?? [];
                  if (stages.length === 0 && !isRunning) return null;
                  const label = TOOL_LABELS[toolPart.toolName] ?? toolPart.toolName;
                  const failedRuntimeStage = stages.find((s) => s.status === "failed");
                  return (
                    <TaskRuntimeCard
                      label={label}
                      isRunning={isRunning}
                      isFailed={isFailed}
                      stages={stages}
                      progress={toolPart.runtimeProgress ?? 0}
                      elapsedTime={toolPart.runtimeElapsedTime ?? 0}
                      artifacts={(!isRunning && result?.files) ? result.files : []}
                      versionNo={result?.version_no}
                      failedStageLabel={failedRuntimeStage?.label}
                      errorMessage={isFailed ? (result?.message ?? "生成失败") : undefined}
                      apiBaseUrl={apiBaseUrl}
                      designId={result?.design_id}
                    />
                  );
                })()}

                {/* --- Markdown: Design explanation --- */}
                {(msg.parts ?? []).map((part, i) => {
                  if (part.type === "text") {
                    const isLastTextPart =
                      i ===
                      (msg.parts ?? []).findLastIndex(
                        (p) => p.type === "text",
                      );
                    return part.text ? (
                      <span key={i}>
                        <Markdown remarkPlugins={[remarkGfm]}>
                          {part.text}
                        </Markdown>
                        {isStreaming &&
                          msg.role === "assistant" &&
                          isLastTextPart &&
                          status === "streaming" && (
                            <span className="streaming-cursor" />
                        )}
                      </span>
                    ) : isStreaming && msg.role === "assistant" && isLastTextPart ? (
                      <span key={i} className="ai-thinking">
                        <span className="spinner" /> AI 思考中...
                      </span>
                    ) : null;
                  }
                  if (part.type === "tool") {
                    // ToolCard now only shows parameter toggle, runtime info handled by TaskRuntimeCard above
                    return (
                      <ToolCard
                        key={i}
                        part={part}
                        apiBaseUrl={apiBaseUrl}
                      />
                    );
                  }
                  return null;
                })}

                {/* --- Agent Run: Post-completion actions --- */}
                {msg.role === "assistant" && hasToolPart && (() => {
                  const toolPart = msg.parts.find((p): p is ToolPart => p.type === "tool");
                  if (!toolPart || toolPart.state === "running") return null;
                  const result = toolPart.output as GenerationCompleteData | undefined;
                  const isFailed = Boolean(result?.job_id && !result?.version_no);
                  const actionStatus = isFailed ? "failed" as const : "completed" as const;
                  return (
                    <AgentRunActions
                      status={actionStatus}
                      designId={result?.design_id}
                      versionNo={result?.version_no}
                    />
                  );
                })()}

                {/* --- Agent Run: Collapsible details --- */}
                {msg.role === "assistant" && hasToolPart && (() => {
                  const toolPart = msg.parts.find((p): p is ToolPart => p.type === "tool");
                  if (!toolPart) return null;
                  const result = toolPart.output as GenerationCompleteData | undefined;
                  const stages = toolPart.runtimeStages ?? [];
                  // Show details whenever toolPart exists (running or done)
                  return (
                    <AgentRunDetails
                      jobId={result?.job_id}
                      designId={result?.design_id}
                      versionNo={result?.version_no}
                      stages={stages}
                      artifacts={(!toolPart || toolPart.state === "done") && result?.files ? result.files : []}
                    />
                  );
                })()}
                {/* Preliminary timeline details */}
                {showPreliminaryTimeline && runtime.state.stages.length > 0 && (
                  <AgentRunDetails
                    stages={runtime.state.stages}
                    artifacts={[]}
                  />
                )}
              </div>
            </div>
          );
        })}
      </div>
      {selectedRefs.length > 0 && (
        <div className="selected-ref-bar" aria-label="当前选中对象">
          <span className="selected-ref-label">已选中：</span>
          {selectedRefs.map((ref) => (
            <span className="selected-ref-chip" key={ref}>
              {PART_REF_LABELS[ref] ?? ref}
              <span className="selected-ref-id">{ref}</span>
            </span>
          ))}
          <button
            type="button"
            className="selected-ref-clear"
            onClick={onClearSelectedRefs}
            aria-label="清除选中"
          >
            &times;
          </button>
        </div>
      )}
      <div className="chat-input-row">
        <textarea
          aria-label="设计需求"
          placeholder="描述飞机设计需求..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          disabled={isStreaming}
          rows={2}
        />
        <button
          type="button"
          className={isStreaming ? "btn-streaming" : ""}
          disabled={isStreaming || !input.trim()}
          onClick={handleSend}
        >
          {isStreaming ? (
            <>
              <span className="spinner" /> 生成中
            </>
          ) : (
            "发送"
          )}
        </button>
      </div>
    </section>
  );
}

function ToolCard({ part, apiBaseUrl }: { part: ToolPart; apiBaseUrl: string }) {
  const [expanded, setExpanded] = useState(false);
  const toolName = part.toolName;
  const label = TOOL_LABELS[toolName] ?? toolName;
  const isRunning = part.state === "running";
  const result = part.output as GenerationCompleteData | undefined;
  const isFailed = !isRunning && result?.job_id && !result?.version_no;

  return (
    <div
      className={`tool-card ${isRunning ? "tool-card-running" : isFailed ? "tool-card-failed" : "tool-card-done"}`}
    >
      <div className="tool-card-header">
        {isRunning ? (
          <span className="spinner" />
        ) : isFailed ? (
          <span className="tool-card-error-icon">&#10007;</span>
        ) : (
          <span className="tool-card-check">&#10003;</span>
        )}
        <span className="tool-card-name">{label}</span>
        {result?.version_no && (
          <span className="tool-card-version">v{result.version_no}</span>
        )}
      </div>

      {part.args && (
        <button
          type="button"
          className="tool-card-toggle"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? "▾ 收起参数" : "▸ 查看参数"}
        </button>
      )}
      {expanded && part.args && (
        <div className="tool-card-args">
          <SpecSummary args={part.args} toolName={toolName} />
        </div>
      )}

      {!isRunning && result?.message && (
        <div className="tool-card-message">{result.message}</div>
      )}

      {/* File download links are now rendered by TaskRuntimeCard — avoid duplication */}
    </div>
  );
}

const SPEC_FIELD_LABELS: Record<string, string> = {
  name: "名称",
  wing_span: "翼展",
  wing_root_chord: "翼根弦长",
  wing_tip_chord: "翼尖弦长",
  wing_sweep: "后掠角",
  wing_dihedral: "上反角",
  wing_airfoil: "翼型",
  wing_position: "机翼位置",
  fuselage_length: "机长",
  fuselage_diameter: "机身直径",
  engine_count: "发动机",
  engine_position: "发动机位置",
  engine_x_offset: "发动机 X 偏移",
  engine_y_offset: "发动机 Y 偏移",
  engine_z_offset: "发动机 Z 偏移",
  tail_type: "尾翼类型",
  cruise_speed: "巡航速度",
  payload: "载荷",
  priority: "优先级",
};

const OPERATION_LABELS: Record<string, string> = {
  set_length: "设置长度",
  set_diameter: "设置直径",
  increase_length: "增加长度",
  decrease_length: "减少长度",
  increase_diameter: "增加直径",
  decrease_diameter: "减少直径",
  set_span: "设置翼展",
  set_root_chord: "设置翼根弦长",
  set_tip_chord: "设置翼尖弦长",
  set_sweep: "设置后掠角",
  set_dihedral: "设置上反角",
  increase_span: "增加翼展",
  decrease_span: "减少翼展",
  increase_root_chord: "增加翼根弦长",
  decrease_root_chord: "减少翼根弦长",
  increase_tip_chord: "增加翼尖弦长",
  decrease_tip_chord: "减少翼尖弦长",
  increase_sweep: "增加后掠角",
  decrease_sweep: "减少后掠角",
  increase_dihedral: "增加上反角",
  decrease_dihedral: "减少上反角",
  set_tail_type: "设置尾翼类型",
  move_outboard: "向外移动",
  move_inboard: "向内移动",
  move_forward: "向前移动",
  move_backward: "向后移动",
  move_up: "向上移动",
  move_down: "向下移动",
};

const OPERATION_UNITS: Record<string, string> = {
  set_length: " m",
  set_diameter: " m",
  increase_length: " m",
  decrease_length: " m",
  increase_diameter: " m",
  decrease_diameter: " m",
  set_span: " m",
  set_root_chord: " m",
  set_tip_chord: " m",
  increase_span: " m",
  decrease_span: " m",
  increase_root_chord: " m",
  decrease_root_chord: " m",
  increase_tip_chord: " m",
  decrease_tip_chord: " m",
  set_sweep: "°",
  set_dihedral: "°",
  increase_sweep: "°",
  decrease_sweep: "°",
  increase_dihedral: "°",
  decrease_dihedral: "°",
  move_outboard: " m",
  move_inboard: " m",
  move_forward: " m",
  move_backward: " m",
  move_up: " m",
  move_down: " m",
};

const SPEC_FIELD_UNIT: Record<string, string> = {
  wing_span: " m",
  wing_root_chord: " m",
  wing_tip_chord: " m",
  wing_sweep: "°",
  wing_dihedral: "°",
  fuselage_length: " m",
  fuselage_diameter: " m",
  engine_count: "发",
  cruise_speed: " km/h",
  payload: " kg",
};

function SpecSummary({
  args,
  toolName,
}: {
  args: Record<string, unknown>;
  toolName: string;
}): JSX.Element {
  if (toolName === "generate_design") {
    const entries: Array<{ k: string; v: string }> = [];
    for (const [key, val] of Object.entries(args)) {
      const label = SPEC_FIELD_LABELS[key] ?? key;
      const unit = SPEC_FIELD_UNIT[key] ?? "";
      if (val != null) entries.push({ k: label, v: `${val}${unit}` });
    }
    return (
      <div className="spec-summary">
        {entries.map((e) => (
          <div key={e.k} className="spec-summary-row">
            <span className="spec-summary-key">{e.k}</span>
            <span className="spec-summary-val">{e.v}</span>
          </div>
        ))}
      </div>
    );
  }

  if (toolName === "modify_design" || toolName === "modify_selected_part") {
    if (toolName === "modify_selected_part") {
      const partRef = String(args.part_ref ?? "");
      const operation = String(args.operation ?? "");
      const val = args.value;
      const unit = OPERATION_UNITS[operation] ?? "";
      return (
        <div className="spec-summary">
          <div className="spec-summary-row">
            <span className="spec-summary-key">部件</span>
            <span className="spec-summary-val">{PART_REF_LABELS[partRef] ?? partRef}</span>
          </div>
          <div className="spec-summary-row">
            <span className="spec-summary-key">操作</span>
            <span className="spec-summary-val">
              {OPERATION_LABELS[operation] ?? operation}{" "}
              {val != null ? `${val}${unit}` : ""}
            </span>
          </div>
          {args.reason != null && (
            <div className="spec-summary-row">
              <span className="spec-summary-key">原因</span>
              <span className="spec-summary-val">{String(args.reason)}</span>
            </div>
          )}
        </div>
      );
    }

    const changes = (args.changes ?? []) as Array<{
      field?: string;
      path?: string;
      value: unknown;
      reason?: string;
    }>;
    return (
      <div className="spec-summary">
        {changes.map((c, i) => {
          const key = c.field ?? c.path ?? "unknown";
          const label = SPEC_FIELD_LABELS[key] ?? key;
          return (
            <div key={i} className="spec-summary-row">
              <span className="spec-summary-key">{label}</span>
              <span className="spec-summary-val">{JSON.stringify(c.value)}</span>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <pre className="spec-summary-raw">
      {JSON.stringify(args, null, 2)}
    </pre>
  );
}
