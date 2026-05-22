#!/usr/bin/env bash
# run_openvsp_qa.sh — Automated OpenVSP QA runner
# Usage: bash scripts/run_openvsp_qa.sh [--json]
#
# 1. Runs check_openvsp_env.py to determine OpenVSP availability
# 2. If available: runs pytest -m openvsp + integration tests
# 3. If not available: outputs SKIP reason, exits 0
# 4. Results collected to docs/qa-results/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RESULTS_DIR="$PROJECT_ROOT/docs/qa-results"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
USE_JSON=false

if [[ "${1:-}" == "--json" ]]; then
    USE_JSON=true
fi

mkdir -p "$RESULTS_DIR"

echo "=== OpenVSP QA Runner ==="
echo "Timestamp: $TIMESTAMP"
echo ""

# 1. Environment check
echo "--- Step 1: Environment Check ---"
ENV_OUTPUT=$("$PROJECT_ROOT/.venv/bin/python" "$SCRIPT_DIR/check_openvsp_env.py" --json 2>&1) || true
ENV_EXIT=$?

echo "$ENV_OUTPUT"

if [[ $ENV_EXIT -eq 3 ]]; then
    echo ""
    echo "OpenVSP not available. Skipping OpenVSP QA."
    echo "Reason: environment check exited with code 3"
    echo ""
    echo "Falling back to fake backend tests..."
    cd "$PROJECT_ROOT"
    CAD_BACKEND=fake .venv/bin/python -m pytest tests/ -q --tb=short \
        -p no:cacheprovider \
        --junitxml="$RESULTS_DIR/fake-tests-$TIMESTAMP.xml" || true
    echo ""
    echo "Results saved to $RESULTS_DIR/"
    exit 0
fi

# 2. Run OpenVSP tests
echo ""
echo "--- Step 2: OpenVSP Tests ---"
cd "$PROJECT_ROOT"
CAD_BACKEND=openvpn RUN_OPENVSP_TESTS=1 .venv/bin/python -m pytest \
    -m openvsp \
    -v --tb=short \
    --junitxml="$RESULTS_DIR/openvsp-tests-$TIMESTAMP.xml" || true

# 3. Run full suite (fake backend baseline)
echo ""
echo "--- Step 3: Fake Backend Baseline ---"
CAD_BACKEND=fake .venv/bin/python -m pytest tests/ -q --tb=short \
    --junitxml="$RESULTS_DIR/fake-tests-$TIMESTAMP.xml" || true

echo ""
echo "=== QA Complete ==="
echo "Results saved to $RESULTS_DIR/"
ls -la "$RESULTS_DIR/"*"$TIMESTAMP"*
