"use client";

export function CadViewer({ glbPath }: { glbPath?: string }) {
  return (
    <section className="panel viewer-panel">
      <header>CAD 预览</header>
      <div className="viewer-surface">
        {glbPath ? <span>GLB: {glbPath}</span> : <span>等待生成模型</span>}
      </div>
    </section>
  );
}
