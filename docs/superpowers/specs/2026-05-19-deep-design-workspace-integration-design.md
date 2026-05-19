# Deep Design Workspace Integration Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate DeepDesignPanel and GraphExecutionPanel into the existing AeroSpec workbench as a right-side tabbed panel, without breaking current functionality.

**Architecture:** Three-column layout (ChatPanel | CadViewer | Right Tab Panel). Stream state is hoisted to page.tsx via useDeepDesignStream hook and shared across "Deep Design" and "Runtime Monitor" tabs. ParameterPanel moves from absolute-positioned overlay into the right panel's "Parameters" tab.

**Tech Stack:** Next.js, React hooks, Tailwind/CSS modules, SSE (fetch + ReadableStream)

---

## Layout

### Current

```
┌──────────────────────────────────────────────────────┐
│  topbar: AeroSpec | 固定翼无人机概念设计 | Settings   │
├────────────┬─────────────────────────────────────────┤
│            │  CadViewer (full width)                  │
│ ChatPanel  │  ┌─────────────────────────┐            │
│            │  │ ParameterPanel (overlay) │            │
│            │  └─────────────────────────┘            │
├────────────┴─────────────────────────────────────────┤
│  VersionPanel                                         │
└──────────────────────────────────────────────────────┘
```

### New

```
┌──────────────────────────────────────────────────────────────────┐
│  topbar: AeroSpec | 固定翼无人机概念设计 | SettingsPanel          │
├────────────┬──────────────────────┬──────────────────────────────┤
│            │                      │ [参数编辑] [深度设计] [运行监控]│
│ ChatPanel  │     CadViewer        │──────────────────────────────│
│            │                      │  Tab content:                │
│            │                      │   - 参数编辑: ParameterPanel │
│            │                      │   - 深度设计: DeepDesignPanel│
│            │                      │   - 运行监控: GraphExecPanel │
├────────────┴──────────────────────┴──────────────────────────────┤
│  VersionPanel                                                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## State Management

### page.tsx additions

```ts
const [rightTab, setRightTab] = useState<"parameters" | "deep-design" | "runtime">("parameters");

// Shared stream state — hoisted from DeepDesignPanel
const deepDesignStream = useDeepDesignStream();

// Called when deep-design run completes
const handleDeepDesignComplete = useCallback(() => {
  if (designId) void fetchVersionList(designId);
}, [designId, fetchVersionList]);
```

### Auto-switch behavior

- User clicks "Start Exploration" in deep-design tab → `deepDesignStream.start(...)` → auto `setRightTab("runtime")` to show live progress
- Run completes (status becomes "completed") → auto `setRightTab("deep-design")` to show report
- Run fails → stay on current tab, show error inline

### No spec guard

When `specData === null`, DeepDesignPanel shows a notice: "请先通过对话生成或加载一个基础设计". The base_spec textarea remains visible for manual JSON input.

---

## Component Changes

### DeepDesignPanel (refactored to controlled)

**New props:**

```ts
export type DeepDesignPanelProps = {
  apiBaseUrl: string;
  defaultSpec?: Record<string, unknown>;
  stream: ReturnType<typeof useDeepDesignStream>;
  onComplete?: () => void;
  onStart?: () => void;  // called when stream starts, for auto-tab-switch
};
```

**Removed:** Internal `useDeepDesignStream()` call. The component now receives `stream` from page.tsx.

**Behavior:**
- Description + variant count + base_spec textarea form
- "Start Exploration" calls `stream.start(apiBaseUrl, {...})` then calls `onStart?.()`
- "Cancel" calls `stream.stop()`
- Renders GraphExecutionPanel inline (inside deep-design tab) with `stream.nodes/variants/events`
- Renders report section when `stream.report` is non-empty
- When `stream.status` transitions to "completed", calls `onComplete?.()`

### GraphExecutionPanel (unchanged)

Used directly by page.tsx in the "runtime" tab:

```tsx
<GraphExecutionPanel
  nodes={deepDesignStream.nodes}
  variants={deepDesignStream.variants}
  events={deepDesignStream.events}
/>
```

### ParameterPanel (layout only)

Moves from absolute-positioned overlay on CadViewer to a normal flow element inside the "parameters" tab. Remove `position: absolute` and related positioning styles.

---

## CSS Changes

### workspace (modified)

```css
.workspace {
  flex: 1;
  display: flex;
  flex-direction: row;   /* was column */
  gap: 12px;
  height: 100%;
  padding-left: 4px;
}
```

### workspace-cad (new)

```css
.workspace-cad {
  flex: 1;
  min-width: 0;
  position: relative;
}
```

### right-panel (new)

```css
.right-panel {
  width: 360px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--border-default);
  background: var(--bg-panel);
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
}

.right-panel-tab.active {
  color: var(--accent);
  border-bottom: 2px solid var(--accent);
}

.right-panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}
```

### parameter-panel (modified)

Remove `position: absolute`, `bottom`, `left`, `right` positioning. Change to normal flow layout within the tab container.

### Runtime tab active indicator

When `deepDesignStream.status === "running"`, show a pulsing blue dot next to the "运行监控" tab label.

---

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `apps/web/src/app/page.tsx` | Modify | Add rightTab state, useDeepDesignStream hook, restructure workspace JSX |
| `apps/web/src/components/graph/DeepDesignPanel.tsx` | Modify | Refactor to controlled component, accept stream/onComplete/onStart props |
| `apps/web/src/components/graph/DeepDesignPanel.test.tsx` | Modify | Update tests for new props interface |
| `apps/web/src/app/globals.css` | Modify | workspace row layout, right-panel styles, parameter-panel repositioning |

### Files NOT changed

- ChatPanel, CadViewer, VersionPanel (no internal changes)
- GraphExecutionPanel component itself (just used in new location)
- useDeepDesignStream hook (behavior unchanged)
- All backend code

---

## Edge Cases

1. **No specData:** DeepDesignPanel shows notice, still allows manual JSON input
2. **Deep design running, user switches to parameters:** No lock — both independent
3. **Deep design completes:** Auto-switch to deep-design tab, refresh version list
4. **Deep design fails:** Stay on current tab, show error inline
5. **Multiple runs:** Stream state resets on each `start()` call
6. **ParameterPanel in tab:** Must work without absolute positioning — verify scrolling, parameter editing, apply button

---

## Acceptance Criteria

- [ ] Existing chat + CAD generation flow unchanged
- [ ] Right panel shows three tabs
- [ ] "参数编辑" tab contains ParameterPanel with full functionality
- [ ] "深度设计" tab shows DeepDesignPanel with defaultSpec from current specData
- [ ] "运行监控" tab shows GraphExecutionPanel with live stream data
- [ ] Clicking "Start Exploration" auto-switches to runtime tab
- [ ] Run completion auto-switches to deep-design tab with report
- [ ] Version list refreshes after deep design completes
- [ ] No specData shows notice in deep-design tab
- [ ] All existing tests pass
- [ ] New layout renders correctly at 1440px+ width
