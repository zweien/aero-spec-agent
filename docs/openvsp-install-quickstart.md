# OpenVSP Installation Quickstart

## Overview

OpenVSP (Open Vehicle Sketch Pad) is required for real CAD generation in aero-spec-agent. The fake backend (`CAD_BACKEND=fake`) works without it, but for actual `.vsp3`, `.step`, `.glb` output, OpenVSP must be installed.

## Installation Methods

### 1. Conda (Recommended)

```bash
conda create -n openvsp python=3.11
conda activate openvsp
conda install -c conda-forge openvsp
```

Verify:
```bash
python scripts/check_openvsp_env.py
```

### 2. Linux Pre-built Binary

Download from [OpenVSP releases](https://github.com/OpenVSP/OpenVSP/releases):

```bash
# Extract to /opt/openvsp
sudo tar -xzf OpenVSP-3.*-Linux.tar.gz -C /opt/openvsp

# Add to PATH and PYTHONPATH
export PATH="/opt/openvsp/bin:$PATH"
export PYTHONPATH="/opt/openvsp/lib/python3.11/site-packages:$PYTHONPATH"
```

Verify:
```bash
python scripts/check_openvsp_env.py
```

### 3. Build from Source (CMake)

```bash
git clone https://github.com/OpenVSP/OpenVSP.git
cd OpenVSP
mkdir build && cd build

cmake .. -DVSP_NO_GRAPHICS=ON -DCMAKE_INSTALL_PREFIX=/opt/openvsp
make -j$(nproc)
sudo make install
```

Set environment:
```bash
export PATH="/opt/openvsp/bin:$PATH"
export PYTHONPATH="/opt/openvsp/lib/python3.11/site-packages:$PYTHONPATH"
```

### 4. Windows

1. Download installer from [OpenVSP releases](https://github.com/OpenVSP/OpenVSP/releases)
2. Run installer, note install path (e.g. `C:\OpenVSP`)
3. Add to environment variables:
   - `PATH`: add `C:\OpenVSP\bin`
   - `PYTHONPATH`: add `C:\OpenVSP\Python`

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `CAD_BACKEND` | `fake` or `openvsp` | `fake` |
| `OPENVSP_EXE` | Path to openvsp executable | auto-detect |
| `OPENVSP_FAIL_STAGE` | Inject failure at stage (testing) | (none) |

## Verification

After installation, run the environment check:

```bash
# Human-readable
python scripts/check_openvsp_env.py

# JSON output
python scripts/check_openvsp_env.py --json
```

Expected output: all checks PASS, exit code 0.

If OpenVSP is unavailable, use `CAD_BACKEND=fake` for development and testing.
