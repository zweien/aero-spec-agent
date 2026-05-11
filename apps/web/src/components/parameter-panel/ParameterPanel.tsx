type Scalar = {
  value: string | number;
  unit?: string;
  source: string;
  confidence: number;
};

type ParameterPanelProps = {
  parameters: Array<{ label: string; scalar: Scalar }>;
};

export function ParameterPanel({ parameters }: ParameterPanelProps) {
  return (
    <section className="panel parameter-panel">
      <header>参数</header>
      {parameters.map((item) => (
        <div className="parameter-row" key={item.label}>
          <span>{item.label}</span>
          <strong>
            {item.scalar.value}
            {item.scalar.unit ? ` ${item.scalar.unit}` : ""}
          </strong>
          <small>
            {item.scalar.source} / {Math.round(item.scalar.confidence * 100)}%
          </small>
        </div>
      ))}
    </section>
  );
}
