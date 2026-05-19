# Issue Triage Rules

## Severity Levels

### P0 — Block User Testing

用户测试被完全阻断，无法继续任何核心流程。

**Examples:**

- System won't start (API or frontend fails to launch)
- Deep Design can't run (SSE connection fails or worker crashes)
- CAD Viewer crash (Three.js scene fails to render, page becomes unresponsive)
- Set Current Variant (设为当前变体) button doesn't work or has no effect
- Data loss (design, version, or variant data disappears after action)

**Response Time:** Fix within **4 hours**. If unable to fix, provide a workaround or rollback plan immediately.

---

### P1 — Impact Quality, Fix Before Wider Release

核心功能可用但结果不可靠或体验明显受损。

**Examples:**

- AI recommendation clearly wrong (recommended variant is not the best by its own metrics)
- Variant metrics obviously unreliable (e.g., range values are negative or orders of magnitude off)
- Report unreadable (formatting broken, missing sections, encoding errors)
- OpenVSP generation failure rate > 50% (when using real backend)
- SSE disconnect unrecoverable (stream breaks and frontend cannot reconnect or resume)

**Response Time:** Fix within **24 hours**. Assess impact scope and notify affected testers.

---

### P2 — Usability, Fix in Next Iteration

功能可用且结果基本正确，但使用体验不够流畅。

**Examples:**

- UI crowded (too many elements in limited space, hard to scan)
- Unclear labels (button text, section titles, or tooltips ambiguous)
- Awkward workflow (unnecessary clicks, missing keyboard shortcuts, confusing navigation)
- Export filename not ideal (non-descriptive or inconsistent naming)

**Response Time:** Fix within **1 sprint** (1-2 weeks). Prioritize based on user feedback frequency.

---

### P3 — Polish

细节优化，不影响功能使用。

**Examples:**

- Visual details (spacing, font size, color consistency)
- Animation details (transition timing, hover effects)
- Non-core optimization suggestions (minor UX improvements, accessibility enhancements)

**Response Time:** Fix as **time permits**. Backlog grooming, include in regular iteration planning.

---

## Triage Process

1. **Receive issue** — from user feedback form, tester report, or automated detection
2. **Classify severity** — match against criteria above; when in doubt, assign higher severity
3. **Assign owner** — based on component (frontend / backend / CAD worker)
4. **Communicate** — notify the team and affected testers of expected resolution timeline
5. **Resolve** — fix, verify, and close; update feedback form if applicable

## Escalation

- If a P0 issue cannot be resolved within the expected response time, escalate to project lead immediately.
- If a P1 issue affects > 50% of testers, treat as P0 for triage purposes.
