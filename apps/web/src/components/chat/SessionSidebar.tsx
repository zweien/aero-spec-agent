"use client";

import {
  type JSX,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  filterSessions,
  groupSessions,
  sessionDisplayTitle,
} from "./sessionGroups";

export type SessionItem = {
  conversation_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  design_id: string;
};

type SessionSidebarProps = {
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  apiBaseUrl: string;
  collapsed: boolean;
  onToggleCollapse: () => void;
  refreshKey?: number;
};

function relativeTime(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diffMs = now - then;
  if (diffMs < 60_000) return "刚刚";
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 60) return `${diffMin}分钟前`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}小时前`;
  return new Date(iso).toLocaleDateString("zh-CN");
}

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) + "..." : text;
}

export function SessionSidebar({
  activeId,
  onSelect,
  onNew,
  apiBaseUrl,
  collapsed,
  onToggleCollapse,
  refreshKey,
}: SessionSidebarProps): JSX.Element {
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  // Rename state
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const renameInputRef = useRef<HTMLInputElement>(null);

  // Delete confirm state
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Delete error state (per-item)
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Search filter over session titles
  const [search, setSearch] = useState("");

  const visibleGroups = useMemo(
    () => groupSessions(filterSessions(sessions, search)),
    [sessions, search],
  );

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/api/conversations`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setSessions(data.conversations ?? []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl]);

  // Initial fetch
  useEffect(() => {
    void fetchSessions();
  }, [fetchSessions]);

  // Refresh when refreshKey changes (e.g. after generation completes)
  useEffect(() => {
    if (refreshKey == null || refreshKey === 0) return;
    void fetchSessions();
  }, [refreshKey, fetchSessions]);

  // Poll every 5 seconds when not collapsed to keep list fresh
  useEffect(() => {
    if (collapsed) return;
    const timer = setInterval(() => {
      void fetchSessions();
    }, 5000);
    return () => clearInterval(timer);
  }, [collapsed, fetchSessions]);

  // Focus rename input when renaming
  useEffect(() => {
    if (renamingId != null) {
      renameInputRef.current?.focus();
      renameInputRef.current?.select();
    }
  }, [renamingId]);

  const startRename = useCallback((item: SessionItem) => {
    setRenamingId(item.conversation_id);
    setRenameValue(item.title);
  }, []);

  const cancelRename = useCallback(() => {
    setRenamingId(null);
    setRenameValue("");
  }, []);

  const saveRename = useCallback(async () => {
    if (renamingId == null) return;
    const trimmed = renameValue.trim();
    if (!trimmed) {
      cancelRename();
      return;
    }
    try {
      const res = await fetch(`${apiBaseUrl}/api/conversations/${encodeURIComponent(renamingId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: trimmed }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSessions((prev) =>
        prev.map((s) =>
          s.conversation_id === renamingId ? { ...s, title: trimmed } : s,
        ),
      );
    } catch {
      // Silently fail — the title simply reverts
    } finally {
      cancelRename();
    }
  }, [apiBaseUrl, cancelRename, renameValue, renamingId]);

  const handleRenameKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        e.preventDefault();
        void saveRename();
      } else if (e.key === "Escape") {
        cancelRename();
      }
    },
    [cancelRename, saveRename],
  );

  const startDelete = useCallback((id: string) => {
    setDeletingId(id);
    setDeleteError(null);
  }, []);

  const cancelDelete = useCallback(() => {
    setDeletingId(null);
    setDeleteError(null);
  }, []);

  const confirmDelete = useCallback(async () => {
    if (deletingId == null) return;
    try {
      const res = await fetch(`${apiBaseUrl}/api/conversations/${encodeURIComponent(deletingId)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSessions((prev) => prev.filter((s) => s.conversation_id !== deletingId));
      // If deleting the active conversation, call onNew
      if (activeId === deletingId) {
        onNew();
      }
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "删除失败");
    } finally {
      if (deleteError == null) {
        setDeletingId(null);
      }
    }
  }, [activeId, apiBaseUrl, deletingId, deleteError, onNew]);

  if (collapsed) {
    return (
      <aside className="session-sidebar collapsed">
        <button
          type="button"
          className="session-sidebar-toggle"
          onClick={onToggleCollapse}
          title="展开会话列表"
        >
          &#9776;
        </button>
      </aside>
    );
  }

  return (
    <aside className="session-sidebar">
      <div className="session-sidebar-header">
        <span>会话</span>
        <div className="session-sidebar-header-actions">
          <button
            type="button"
            className="session-sidebar-new"
            onClick={onNew}
            title="新建会话"
          >
            +
          </button>
          <button
            type="button"
            className="session-sidebar-toggle"
            onClick={onToggleCollapse}
            title="收起会话列表"
          >
            &#9664;
          </button>
        </div>
      </div>

      <div className="session-sidebar-search">
        <input
          type="text"
          className="session-sidebar-search-input"
          placeholder="搜索会话…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="session-sidebar-items">
        {loading && (
          <div className="session-sidebar-status">加载中...</div>
        )}

        {error && (
          <div className="session-sidebar-error">
            {error}
            <button
              type="button"
              className="session-sidebar-retry"
              onClick={() => void fetchSessions()}
            >
              重试
            </button>
          </div>
        )}

        {!loading && !error && sessions.length === 0 && (
          <div className="session-sidebar-status">暂无会话</div>
        )}

        {!loading && !error && sessions.length > 0 && visibleGroups.length === 0 && (
          <div className="session-sidebar-status">无匹配「{search.trim()}」的会话</div>
        )}

        {visibleGroups.map((group) => (
          <div key={group.key} className="session-sidebar-group">
            <div className="session-sidebar-group-label">{group.label}</div>
            {group.items.map((item) => {
              const isActive = item.conversation_id === activeId;
              const isHovered = item.conversation_id === hoveredId;
              const isRenaming = item.conversation_id === renamingId;
              const isDeleting = item.conversation_id === deletingId;

              return (
                <div
                  key={item.conversation_id}
                  className={`session-sidebar-item${isActive ? " active" : ""}`}
                  onMouseEnter={() => setHoveredId(item.conversation_id)}
                  onMouseLeave={() => {
                    setHoveredId(null);
                    if (!isRenaming) cancelRename();
                  }}
                >
                  <button
                    type="button"
                    className="session-sidebar-item-main"
                    onClick={() => onSelect(item.conversation_id)}
                  >
                    <span className="session-sidebar-item-title">
                      {isRenaming ? (
                        <input
                          ref={renameInputRef}
                          className="session-sidebar-rename"
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onKeyDown={handleRenameKeyDown}
                          onBlur={() => void saveRename()}
                          onClick={(e) => e.stopPropagation()}
                        />
                      ) : (
                        truncate(sessionDisplayTitle(item), 30)
                      )}
                    </span>
                    <span className="session-sidebar-item-meta">
                      {item.message_count > 0 && `${item.message_count} 条`}
                      {" · "}
                      {relativeTime(item.updated_at)}
                    </span>
                  </button>

                  {isHovered && !isRenaming && !isDeleting && (
                    <div className="session-sidebar-item-actions">
                      <button
                        type="button"
                        className="session-sidebar-action"
                        onClick={(e) => {
                          e.stopPropagation();
                          startRename(item);
                        }}
                        aria-label="重命名"
                      >
                        ✏
                      </button>
                      <button
                        type="button"
                        className="session-sidebar-action danger"
                        onClick={(e) => {
                          e.stopPropagation();
                          startDelete(item.conversation_id);
                        }}
                        aria-label="删除"
                      >
                        ✕
                      </button>
                    </div>
                  )}

                  {isDeleting && (
                    <div className="session-sidebar-delete-confirm">
                      <span>确认删除？</span>
                      <button
                        type="button"
                        className="session-sidebar-action danger"
                        onClick={(e) => {
                          e.stopPropagation();
                          void confirmDelete();
                        }}
                      >
                        删除
                      </button>
                      <button
                        type="button"
                        className="session-sidebar-action"
                        onClick={(e) => {
                          e.stopPropagation();
                          cancelDelete();
                        }}
                      >
                        取消
                      </button>
                      {deleteError && (
                        <span className="session-sidebar-error">{deleteError}</span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </aside>
  );
}
