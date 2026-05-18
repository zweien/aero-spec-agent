# Demo-Ready Report — 2026-05-18

**Commit:** cb60351
**Status:** API-verified, pending manual browser QA

---

## Verified (Automated)

| Category | Item | Result |
|----------|------|--------|
| Backend tests | pytest | 213 passed, 1 skipped |
| Frontend tests | node --test | 34 passed |
| Frontend build | npm run build | PASS |
| Backend health | GET /health | {"status":"ok"} |
| Frontend page | GET / | HTTP 200 |
| Generate | POST /api/designs/{id}/generate | queued → succeeded |
| Job polling | GET /api/jobs/{id} | status transitions correct |
| PATCH modify | PATCH /api/designs/{id}/spec | new version created |
| Version list | GET /api/designs/{id}/versions | only succeeded versions |
| Diagnostics | GET /api/jobs/{id}/diagnostics | all 5 fields present |
| 404 handling | GET /api/jobs/missing/diagnostics | 404, no 500 |
| duration_ms | job response field | float value, not null for completed |
| URL encoding | jobId in diagnostics fetch | encodeURIComponent applied |

## Pending Manual Verification

See docs/browser-qa-report.md § Manual Browser Verification.

| # | Item | Priority |
|---|------|----------|
| 1 | Chat SSE: send message → tool card spinner → done | P0 |
| 2 | CAD viewer: 3D model renders after generation | P0 |
| 3 | ParameterPanel: values populate, can modify + apply | P0 |
| 4 | Failed tool card: ✗ icon, red border, diagnostics panel | P1 |
| 5 | Diagnostics null state: "诊断信息暂不可用" | P1 |
| 6 | Selected-part click + modify via chat | P1 |
| 7 | Console: no uncaught exceptions | P1 |
| 8 | Network: polling stops after terminal status | P2 |
| 9 | Version history: switch between versions | P2 |

## Screenshots

Save screenshots to docs/screenshots/ with names matching demo-script.md sections:
- `01-generate-design.png`
- `02-modify-design.png`
- `03-selected-part.png`
- `04-failed-diagnostics.png`
- `05-version-history.png`

## Known Issues

None discovered during automated QA.

## Blocking Issues for Demo

None. All automated checks pass. Manual browser verification is the remaining gate.
