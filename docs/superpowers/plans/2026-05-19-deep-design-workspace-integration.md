# Deep Design Workspace Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a right-side tabbed panel to the AeroSpec workbench with 参数编辑 / 深度设计 / 运行监控 tabs, integrating DeepDesignPanel with shared stream state.

**Architecture:** page.tsx hoists useDeepDesignStream hook and rightTab state. workspace area splits into CadViewer (left) + right panel (tabs). DeepDesignPanel becomes a controlled component receiving stream via props. Auto-switches to runtime tab on start, back to deep-design tab on completion.

**Tech Stack:** Next.js (React), CSS (globals.css), Node test runner (tsx)

---

## File Structure

| File | Responsibility |
|------|---------------|
| `apps/web/src/app/page.tsx` | Main layout — adds rightTab state, useDeepDesignStream, workspace restructure |
| `apps/web/src/components/graph/DeepDesignPanel.tsx` | Controlled component — receives stream/onComplete/onStart props |
| `apps/web/src/components/graph/DeepDesignPanel.test.tsx` | Updated tests for new props interface |
| `apps/web/src/app/globals.css` | workspace row layout, .right-panel styles, parameter-panel flow layout |

---

### Task 1: Add right-panel CSS styles

**Files:**
- Modify: `apps/web/src/app/globals.css`

- [ ] **Step 1: Change workspace to row flex and add right-panel styles**

In `globals.css`, change `.workspace` from `flex-direction: column` to `flex-direction: row`, then add new `.workspace-cad`, `.right-panel`, `.right-panel-tabs`, `.right-panel-tab`, and `.right-panel-content` rules.

Find the `.workspace` rule (around line 191):

```css
.workspace {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  padding-left: 4px;
}
```

Replace with:

```css
.workspace {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: row;
  gap: 0;
  height: 100%;
  padding-left: 4px;
}

.workspace-cad {
  flex: 1;
  min-width: 0;
  position: relative;
}

.right-panel {
  width: 360px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--border-default);
  background: var(--bg-panel);
  min-height: 0;
}

.right-panel-tabs {
  display: flex;
  border-bottom: 1px solid var(--border-default);
}

.right-panel-tab {
  flex: 1;
  border-radius: 0;
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
  padding: 10px 0;
  min-height: 38px;
  position: relative;
}

.right-panel-tab:hover:not(.active) {
  background: var(--bg-hover);
}

.right-panel-tab.active {
  color: var(--accent);
  background: transparent;
}

.right-panel-tab.active::after {
  content: "";
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--accent);
}

.right-panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  min-height: 0;
}
```

- [ ] **Step 2: Update parameter-panel to work in flow layout**

Find the `.parameter-panel` rule (around line 945) and change `max-height: 280px` to a larger value since it's now in a scrollable container instead of an overlay:

```css
.parameter-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
  max-height: none;
  flex-shrink: 0;
  scrollbar-width: thin;
  scrollbar-color: var(--border-strong) transparent;
  transition: max-height 0.2s;
}
```

- [ ] **Step 3: Verify build passes**

Run: `cd apps/web && npm run build`
Expected: Build succeeds with no errors.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/app/globals.css
git commit -m "style: workspace row layout and right-panel CSS"
```

---

### Task 2: Refactor DeepDesignPanel to controlled component

**Files:**
- Modify: `apps/web/src/components/graph/DeepDesignPanel.tsx`
- Modify: `apps/web/src/components/graph/DeepDesignPanel.test.tsx`

- [ ] **Step 1: Write failing tests for new props interface**

Replace the entire content of `apps/web/src/components/graph/DeepDesignPanel.test.tsx` with:

```tsx
import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToString } from "react-dom/server";

import { DeepDesignPanel } from "./DeepDesignPanel.tsx";
import type { DeepDesignStreamState } from "./useDeepDesignStream.ts";

const mockStream: DeepDesignStreamState & { start: () => Promise<void>; stop: () => void } = {
  nodes: [],
  variants: [],
  events: [],
  status: "idle",
  report: "",
  start: async () => {},
  stop: () => {},
};

test("DeepDesignPanel renders input form with stream prop", () => {
  const html = renderToString(
    <DeepDesignPanel apiBaseUrl="http://localhost:3800" stream={mockStream} />,
  );
  assert.ok(html.includes("Deep Design Exploration"));
  assert.ok(html.includes("Description"));
  assert.ok(html.includes("Start Exploration"));
});

test("DeepDesignPanel renders with default spec", () => {
  const html = renderToString(
    <DeepDesignPanel
      apiBaseUrl="http://localhost:3800"
      stream={mockStream}
      defaultSpec={{ aircraft: { name: "test" } }}
    />,
  );
  assert.ok(html.includes("test"));
});

test("DeepDesignPanel shows no-spec notice when defaultSpec is undefined", () => {
  const html = renderToString(
    <DeepDesignPanel apiBaseUrl="http://localhost:3800" stream={mockStream} />,
  );
  assert.ok(html.includes("请先生成或加载一个基础设计"));
});

test("DeepDesignPanel shows cancel button only while running", () => {
  const runningStream = { ...mockStream, status: "running" as const };
  const html = renderToString(
    <DeepDesignPanel apiBaseUrl="http://localhost:3800" stream={runningStream} />,
  );
  assert.ok(html.includes("Cancel"));
});

test("DeepDesignPanel shows report when stream has report", () => {
  const completedStream = { ...mockStream, report: "# Test Report", status: "completed" as const };
  const html = renderToString(
    <DeepDesignPanel apiBaseUrl="http://localhost:3800" stream={completedStream} />,
  );
  assert.ok(html.includes("Test Report"));
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/web && npx tsx --test src/components/graph/DeepDesignPanel.test.tsx`
Expected: Tests fail because DeepDesignPanel doesn't accept `stream` prop yet.

- [ ] **Step 3: Refactor DeepDesignPanel to accept stream prop**

Replace the entire content of `apps/web/src/components/graph/DeepDesignPanel.tsx` with:

```tsx
"use client";

import React, { type JSX, useEffect, useState } from "react";

import { GraphExecutionPanel } from "./GraphExecutionPanel";
import type { useDeepDesignStream } from "./useDeepDesignStream";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export type DeepDesignPanelProps = {
  apiBaseUrl: string;
  defaultSpec?: Record<string, unknown>;
  stream: ReturnType<typeof useDeepDesignStream>;
  onComplete?: () => void;
  onStart?: () => void;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DeepDesignPanel({
  apiBaseUrl,
  defaultSpec,
  stream,
  onComplete,
  onStart,
}: DeepDesignPanelProps): JSX.Element {
  const [description, setDescription] = useState("");
  const [variantCount, setVariantCount] = useState(3);
  const [specJson, setSpecJson] = useState(
    defaultSpec ? JSON.stringify(defaultSpec, null, 2) : "",
  );

  // Sync defaultSpec changes into textarea
  useEffect(() => {
    if (defaultSpec) {
      setSpecJson(JSON.stringify(defaultSpec, null, 2));
    }
  }, [defaultSpec]);

  // Fire onComplete when stream transitions to completed
  const prevStatusRef = React.useRef(stream.status);
  useEffect(() => {
    if (prevStatusRef.current === "running" && stream.status === "completed") {
      onComplete?.();
    }
    prevStatusRef.current = stream.status;
  }, [stream.status, onComplete]);

  const handleSubmit = () => {
    if (!description.trim()) return;

    let baseSpec: Record<string, unknown> = {};
    try {
      baseSpec = specJson.trim() ? JSON.parse(specJson) : {};
    } catch {
      baseSpec = {};
    }

    onStart?.();
    void stream.start(apiBaseUrl, {
      design_id: `dd-${Date.now()}`,
      description: description.trim(),
      base_spec: baseSpec,
      constraints: { variant_count: variantCount },
    });
  };

  const isRunning = stream.status === "running";
  const hasNoSpec = !defaultSpec && !specJson.trim();

  return (
    <div className="flex flex-col gap-3">
      {/* No spec notice */}
      {hasNoSpec && (
        <div style={{
          padding: "12px",
          background: "var(--warning-bg)",
          border: "1px solid var(--warning)",
          borderRadius: "var(--radius-sm)",
          color: "var(--warning)",
          fontSize: "12px",
        }}>
          请先通过对话生成或加载一个基础设计，或手动输入 JSON。
        </div>
      )}

      {/* Input form */}
      <div style={{
        padding: "12px",
        background: "var(--bg-elevated)",
        borderRadius: "var(--radius)",
        border: "1px solid var(--border-default)",
      }}>
        <div style={{ marginBottom: "10px" }}>
          <label style={{ display: "block", fontSize: "12px", fontWeight: 500, color: "var(--text-dim)", marginBottom: "4px" }}>
            设计需求描述
          </label>
          <textarea
            style={{
              width: "100%",
              padding: "8px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border-strong)",
              background: "var(--bg-base)",
              color: "var(--text)",
              fontSize: "13px",
              resize: "vertical",
            }}
            rows={2}
            placeholder="e.g. 设计一架 300km 航程的长航时无人机"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={isRunning}
          />
        </div>

        <div style={{ display: "flex", gap: "12px", marginBottom: "10px" }}>
          <div style={{ flex: 1 }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 500, color: "var(--text-dim)", marginBottom: "4px" }}>
              变体数量
            </label>
            <input
              type="number"
              style={{
                width: "100%",
                padding: "8px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-strong)",
                background: "var(--bg-base)",
                color: "var(--text)",
                fontSize: "13px",
              }}
              min={1}
              max={5}
              value={variantCount}
              onChange={(e) => setVariantCount(Number(e.target.value) || 3)}
              disabled={isRunning}
            />
          </div>
        </div>

        <div style={{ marginBottom: "10px" }}>
          <label style={{ display: "block", fontSize: "12px", fontWeight: 500, color: "var(--text-dim)", marginBottom: "4px" }}>
            Base Spec (JSON)
          </label>
          <textarea
            style={{
              width: "100%",
              padding: "8px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border-strong)",
              background: "var(--bg-base)",
              color: "var(--text)",
              fontFamily: "var(--font-mono)",
              fontSize: "11px",
              resize: "vertical",
            }}
            rows={4}
            placeholder="{}"
            value={specJson}
            onChange={(e) => setSpecJson(e.target.value)}
            disabled={isRunning}
          />
        </div>

        <div style={{ display: "flex", gap: "8px" }}>
          <button
            onClick={handleSubmit}
            disabled={isRunning || !description.trim()}
          >
            {isRunning ? "运行中..." : "开始探索"}
          </button>
          {isRunning && (
            <button
              style={{ background: "var(--bg-surface)", color: "var(--text-dim)" }}
              onClick={stream.stop}
            >
              取消
            </button>
          )}
        </div>
      </div>

      {/* Report */}
      {stream.report && (
        <div style={{
          padding: "12px",
          background: "var(--bg-elevated)",
          borderRadius: "var(--radius)",
          border: "1px solid var(--border-default)",
        }}>
          <h4 style={{ fontSize: "12px", fontWeight: 600, color: "var(--text)", marginBottom: "8px" }}>
            设计探索报告
          </h4>
          <pre style={{
            whiteSpace: "pre-wrap",
            fontSize: "11px",
            color: "var(--text-dim)",
            margin: 0,
            lineHeight: 1.6,
          }}>
            {stream.report}
          </pre>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/web && npx tsx --test src/components/graph/DeepDesignPanel.test.tsx`
Expected: All 5 tests pass.

- [ ] **Step 5: Run build to verify no type errors**

Run: `cd apps/web && npm run build`
Expected: Build succeeds.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/components/graph/DeepDesignPanel.tsx apps/web/src/components/graph/DeepDesignPanel.test.tsx
git commit -m "refactor: DeepDesignPanel to controlled component with stream prop"
```

---

### Task 3: Restructure page.tsx — add right panel with tabs

**Files:**
- Modify: `apps/web/src/app/page.tsx`

- [ ] **Step 1: Add imports and state to page.tsx**

At the top of `page.tsx`, add these imports after the existing ones (after the `VersionPanel` import line):

```ts
import { DeepDesignPanel } from "@/components/graph/DeepDesignPanel";
import { GraphExecutionPanel } from "@/components/graph/GraphExecutionPanel";
import { useDeepDesignStream } from "@/components/graph/useDeepDesignStream";
```

Inside `Home()`, after the `selectedRefs` state declaration (around line 97), add:

```ts
const [rightTab, setRightTab] = useState<"parameters" | "deep-design" | "runtime">("parameters");
const deepDesignStream = useDeepDesignStream();
```

Add the auto-switch callback after `handleClearSelectedRefs` (around line 300):

```ts
const handleDeepDesignStart = useCallback(() => {
  setRightTab("runtime");
}, []);

const handleDeepDesignComplete = useCallback(() => {
  setRightTab("deep-design");
  if (designId) void fetchVersionList(designId);
}, [designId, fetchVersionList]);
```

- [ ] **Step 2: Restructure the workspace JSX**

In the return statement, find the `.workspace` div (around line 356). Replace the entire workspace section:

```tsx
        <div className="workspace">
          <CadViewer
            modelFormat={previewSource?.format}
            modelUrl={previewSource?.url}
            spec={previewSpec}
            onSelectPart={handleSelectPart}
          />
          <ParameterPanel
            spec={draftSpec}
            onParameterChange={handleParameterChange}
            onApplyChanges={handleApplyChanges}
            pendingCount={pendingChanges.size}
            isApplying={isApplyingChanges}
          />
        </div>
```

Replace with:

```tsx
        <div className="workspace">
          <div className="workspace-cad">
            <CadViewer
              modelFormat={previewSource?.format}
              modelUrl={previewSource?.url}
              spec={previewSpec}
              onSelectPart={handleSelectPart}
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
                {deepDesignStream.status === "running" && (
                  <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", background: "var(--accent)", marginLeft: 4, verticalAlign: "middle", animation: "pulse 1.5s infinite" }} />
                )}
              </button>
              <button
                className={`right-panel-tab ${rightTab === "runtime" ? "active" : ""}`}
                onClick={() => setRightTab("runtime")}
              >
                运行监控
                {deepDesignStream.status === "running" && (
                  <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", background: "var(--accent)", marginLeft: 4, verticalAlign: "middle", animation: "pulse 1.5s infinite" }} />
                )}
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
                  onStart={handleDeepDesignStart}
                  onComplete={handleDeepDesignComplete}
                />
              )}
              {rightTab === "runtime" && (
                <GraphExecutionPanel
                  nodes={deepDesignStream.nodes}
                  variants={deepDesignStream.variants}
                  events={deepDesignStream.events}
                />
              )}
            </div>
          </div>
        </div>
```

- [ ] **Step 3: Add pulse animation to globals.css**

Add at the end of `globals.css`, before the media queries:

```css
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
```

- [ ] **Step 4: Run build to verify**

Run: `cd apps/web && npm run build`
Expected: Build succeeds.

- [ ] **Step 5: Run all frontend tests**

Run: `cd apps/web && npx tsx --test src/components/graph/DeepDesignPanel.test.tsx src/components/graph/useDeepDesignStream.test.ts src/components/graph/GraphExecutionPanel.test.tsx`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/app/page.tsx apps/web/src/app/globals.css
git commit -m "feat: right-side tabbed panel with parameters, deep-design, runtime tabs"
```

---

### Task 4: Visual QA and final verification

**Files:**
- No new files

- [ ] **Step 1: Start dev servers and verify layout**

Run: `cd apps/web && npm run dev`

Open browser to `http://localhost:3900`. Verify:
1. Three-column layout renders: ChatPanel | CadViewer | Right panel
2. Right panel shows three tab buttons: 参数编辑 / 深度设计 / 运行监控
3. "参数编辑" tab (default) shows ParameterPanel with parameter editing
4. "深度设计" tab shows DeepDesignPanel input form
5. "运行监控" tab shows empty GraphExecutionPanel

- [ ] **Step 2: Verify existing flows still work**

1. Send a chat message to generate a design → CadViewer shows preview, ParameterPanel shows spec
2. Edit a parameter and click "应用" → generation triggers correctly
3. Version panel shows versions, clicking loads them

- [ ] **Step 3: Run full test suite**

Run: `cd /home/z/codebase/aero-spec-agent && CAD_BACKEND=fake .venv/bin/python -m pytest tests/ -q`
Expected: All tests pass.

Run: `cd apps/web && npx tsx --test src/components/graph/DeepDesignPanel.test.tsx src/components/graph/useDeepDesignStream.test.ts src/components/graph/GraphExecutionPanel.test.tsx`
Expected: All 16 tests pass.

- [ ] **Step 4: Commit any fixes if needed, otherwise done**

If QA found issues, fix and commit. Otherwise, the feature is complete.
