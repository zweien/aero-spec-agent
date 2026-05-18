# Design Controller Architecture

```mermaid
flowchart TD
    A[POST /api/design-controller/compare] --> B[DesignControllerService]
    B --> C[Deep copy base_spec per variant]
    C --> D[Apply variant changes via _set_nested]
    D --> E[Validate with AircraftSpec]
    E --> F[JobRunner.enqueue_generate per variant]
    F --> G[BackgroundTasks.run_queued_job]
    G --> H[Variant 1 Job]
    G --> I[Variant 2 Job]
    G --> J[Variant N Job]

    H --> K[ControllerJob persisted to storage/controller_jobs/]
    I --> K
    J --> K

    L[GET /api/design-controller/{id}] --> M[aggregate method]
    M --> N[Check each variant job status]
    N --> O{All terminal?}
    O -->|No| P[Return running status]
    O -->|Yes| Q[Collect results]
    Q --> R[Return completed + aggregated data]
```

## Data Flow

```
storage/
  controller_jobs/
    {id}.json              ← ControllerJob state
  designs/
    {design_id}/
      versions/
        {N}/                ← Each variant = normal version
          aircraft_spec.yaml
          validation_report.json
          ...
```

## Rendering

```bash
npx @mermaid-js/mermaid-cli -i docs/architecture/design-controller-architecture.md -o docs/architecture/design-controller-architecture.png
```
