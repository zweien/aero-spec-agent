"use client";

import React, { type JSX, useState } from "react";

import { GraphExecutionPanel } from "./GraphExecutionPanel";
import { useDeepDesignStream } from "./useDeepDesignStream";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export type DeepDesignPanelProps = {
  apiBaseUrl: string;
  defaultSpec?: Record<string, unknown>;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DeepDesignPanel({ apiBaseUrl, defaultSpec }: DeepDesignPanelProps): JSX.Element {
  const [description, setDescription] = useState("");
  const [variantCount, setVariantCount] = useState(2);
  const [specJson, setSpecJson] = useState(
    defaultSpec ? JSON.stringify(defaultSpec, null, 2) : "",
  );

  const stream = useDeepDesignStream();

  const handleSubmit = () => {
    if (!description.trim()) return;

    let baseSpec: Record<string, unknown> = {};
    try {
      baseSpec = specJson.trim() ? JSON.parse(specJson) : {};
    } catch {
      baseSpec = {};
    }

    void stream.start(apiBaseUrl, {
      design_id: `dd-${Date.now()}`,
      description: description.trim(),
      base_spec: baseSpec,
      constraints: { variant_count: variantCount },
    });
  };

  const isRunning = stream.status === "running";

  return (
    <div className="flex flex-col gap-4">
      {/* Input form */}
      <div className="rounded-lg border bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold text-gray-700">
          Deep Design Exploration
        </h3>

        <div className="mb-3">
          <label className="mb-1 block text-xs font-medium text-gray-500">
            Description
          </label>
          <textarea
            className="w-full rounded border border-gray-300 p-2 text-sm"
            rows={2}
            placeholder="e.g. 设计一架 300km 航程的长航时无人机"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={isRunning}
          />
        </div>

        <div className="mb-3 flex gap-4">
          <div className="flex-1">
            <label className="mb-1 block text-xs font-medium text-gray-500">
              Variants
            </label>
            <input
              type="number"
              className="w-full rounded border border-gray-300 p-2 text-sm"
              min={1}
              max={5}
              value={variantCount}
              onChange={(e) => setVariantCount(Number(e.target.value) || 2)}
              disabled={isRunning}
            />
          </div>
        </div>

        <div className="mb-3">
          <label className="mb-1 block text-xs font-medium text-gray-500">
            Base Spec (JSON, optional)
          </label>
          <textarea
            className="w-full rounded border border-gray-300 p-2 font-mono text-xs"
            rows={4}
            placeholder="{}"
            value={specJson}
            onChange={(e) => setSpecJson(e.target.value)}
            disabled={isRunning}
          />
        </div>

        <div className="flex gap-2">
          <button
            className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:bg-gray-400"
            onClick={handleSubmit}
            disabled={isRunning || !description.trim()}
          >
            {isRunning ? "Running..." : "Start Exploration"}
          </button>
          {isRunning && (
            <button
              className="rounded bg-gray-200 px-4 py-2 text-sm text-gray-700 hover:bg-gray-300"
              onClick={stream.stop}
            >
              Cancel
            </button>
          )}
        </div>
      </div>

      {/* Execution panel */}
      {(stream.nodes.length > 0 || stream.variants.length > 0 || stream.events.length > 0) && (
        <GraphExecutionPanel
          nodes={stream.nodes}
          variants={stream.variants}
          events={stream.events}
        />
      )}

      {/* Report */}
      {stream.report && (
        <div className="rounded-lg border bg-white p-4 shadow-sm">
          <h3 className="mb-2 text-sm font-semibold text-gray-700">Report</h3>
          <div className="prose prose-sm max-w-none">
            <pre className="whitespace-pre-wrap text-xs text-gray-700">{stream.report}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
