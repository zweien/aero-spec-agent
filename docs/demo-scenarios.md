# Demo Scenarios

## 概述

v0.1.0 提供 3 个中文演示场景，覆盖不同飞机设计需求。使用 `scripts/seed_demo_designs.py` 一键生成。

## 场景 1：长航时固定翼无人机

**设计需求**：长航时侦察无人机，需要 20+ 小时续航能力

**关键参数**：
- 翼展: 18m
- 机身长度: 8m
- 巡航速度: 120 km/h
- 载荷: 10 kg
- 发动机: 单发推进式螺旋桨

**特点**：大展弦比（~18）、低翼载荷、高升阻比估算

**Demo ID**: `demo-long-endurance-uav`

## 场景 2：高速小型侦察无人机

**设计需求**：高速突防侦察，要求巡航速度 250 km/h 以上

**关键参数**：
- 翼展: 4m
- 机身长度: 2.5m
- 巡航速度: 250 km/h
- 载荷: 3 kg
- 发动机: 单发涡扇

**特点**：小展弦比、后掠翼、紧凑布局

**Demo ID**: `demo-high-speed-recon`

## 场景 3：大载荷低速巡航无人机

**设计需求**：物资运输无人机，载荷 50 kg，低速巡航

**关键参数**：
- 翼展: 22m
- 机身长度: 10m
- 巡航速度: 80 km/h
- 载荷: 50 kg
- 发动机: 双发螺旋桨

**特点**：超大翼面积、极低翼载荷、双发布局

**Demo ID**: `demo-heavy-lift-uav`

## 使用方法

```bash
# 生成所有 demo 数据（默认 Fake CAD）
python scripts/seed_demo_designs.py

# 使用 OpenVSP 生成（需要安装）
CAD_BACKEND=openvsp python scripts/seed_demo_designs.py
```

## 数据隔离

所有 Demo 数据使用 `demo-` 前缀的 design_id，不会与正式设计数据混淆。storage 目录结构：

```
storage/designs/
  demo-long-endurance-uav/versions/1/
  demo-high-speed-recon/versions/1/
  demo-heavy-lift-uav/versions/1/
```
