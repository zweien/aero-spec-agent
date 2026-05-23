import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createServer } from "node:net";
import { setTimeout as delay } from "node:timers/promises";

const APP_PORT = Number(process.env.TASK6_QA_PORT ?? 3910);
const APP_URL = process.env.TASK6_QA_URL ?? `http://127.0.0.1:${APP_PORT}`;
const css = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function command(name) {
  const result = spawnSync("sh", ["-lc", `command -v ${name}`], { encoding: "utf8" });
  return result.status === 0 ? result.stdout.trim() : "";
}

async function waitForHttp(url, timeoutMs) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {}
    await delay(250);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function waitForJson(url, timeoutMs) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) return response.json();
    } catch {}
    await delay(250);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

function isPortAvailable(port) {
  return new Promise((resolve) => {
    const server = createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => {
      server.close(() => resolve(true));
    });
    server.listen(port, "127.0.0.1");
  });
}

function getFreePort() {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.once("error", reject);
    server.once("listening", () => {
      const address = server.address();
      server.close(() => {
        if (address && typeof address === "object") resolve(address.port);
        else reject(new Error("Failed to allocate a Chrome debugging port"));
      });
    });
    server.listen(0, "127.0.0.1");
  });
}

function startNextDev() {
  if (process.env.TASK6_QA_URL) return null;

  const child = spawn("npm", ["run", "dev"], {
    cwd: new URL("..", import.meta.url),
    env: { ...process.env, WEB_PORT: String(APP_PORT) },
    stdio: ["ignore", "pipe", "pipe"],
    detached: true,
  });

  child.stdout.on("data", (chunk) => process.stdout.write(chunk));
  child.stderr.on("data", (chunk) => process.stderr.write(chunk));
  return child;
}

function startChrome({ port, userDataDir }) {
  const chrome = command("google-chrome") || command("chromium") || command("chromium-browser");
  assert(chrome, "Chrome or Chromium is required for Task 6 browser QA");

  return spawn(chrome, [
    "--headless=new",
    "--no-sandbox",
    "--disable-gpu",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDataDir}`,
    "about:blank",
  ], {
    stdio: ["ignore", "pipe", "pipe"],
    detached: true,
  });
}

function stopProcessGroup(child) {
  if (!child?.pid) return;
  try {
    process.kill(-child.pid, "SIGTERM");
  } catch {
    try {
      child.kill("SIGTERM");
    } catch {}
  }
}

async function removeDirectoryWithRetry(path) {
  for (let attempt = 0; attempt < 10; attempt++) {
    try {
      rmSync(path, { recursive: true, force: true });
      return;
    } catch (error) {
      if (attempt === 9) throw error;
      await delay(100);
    }
  }
}

class CdpPage {
  constructor(ws) {
    this.ws = ws;
    this.nextId = 1;
    this.pending = new Map();
    this.consoleMessages = [];
    this.failedRequests = [];

    ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const { resolve, reject, timer } = this.pending.get(message.id);
        clearTimeout(timer);
        this.pending.delete(message.id);
        if (message.error) {
          reject(new Error(`${message.error.message}: ${message.error.data ?? ""}`));
        } else {
          resolve(message.result);
        }
        return;
      }

      if (message.method === "Runtime.consoleAPICalled") {
        this.consoleMessages.push({
          type: message.params.type,
          args: message.params.args.map((arg) => arg.value ?? arg.description),
        });
      }
      if (message.method === "Runtime.exceptionThrown") {
        this.consoleMessages.push({
          type: "exception",
          args: [message.params.exceptionDetails.text],
        });
      }
      if (message.method === "Network.loadingFailed") {
        this.failedRequests.push(message.params);
      }
    });
  }

  send(method, params = {}, timeoutMs = 10000) {
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`CDP timeout: ${method}`));
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
    });
  }

  async evaluate(fn) {
    const result = await this.send("Runtime.evaluate", {
      expression: `(${fn})()`,
      awaitPromise: true,
      returnByValue: true,
    });
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.text);
    }
    return result.result.value;
  }

  close() {
    this.ws.close();
  }
}

async function openCdpPage(url, port) {
  const target = await fetch(
    `http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`,
    { method: "PUT" },
  ).then((response) => response.json());
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve) => ws.addEventListener("open", resolve, { once: true }));
  const page = new CdpPage(ws);
  await page.send("Page.enable");
  await page.send("Runtime.enable");
  await page.send("Network.enable");
  await page.send("Log.enable");
  return { page, targetId: target.id };
}

async function closeTarget(page, targetId) {
  try {
    await page.send("Target.closeTarget", { targetId });
  } catch {}
  page.close();
}

async function qaRealApp(page) {
  await page.send("Emulation.setDeviceMetricsOverride", {
    width: 1440,
    height: 1000,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await page.send("Page.navigate", { url: APP_URL });
  await delay(2500);

  const emptyWorkspace = await page.evaluate(() => {
    const rect = (selector) => {
      const element = document.querySelector(selector);
      if (!element) return null;
      const box = element.getBoundingClientRect();
      return {
        width: Math.round(box.width),
        height: Math.round(box.height),
        scrollWidth: element.scrollWidth,
        clientWidth: element.clientWidth,
      };
    };
    return {
      workbench: !!document.querySelector(".workbench"),
      chatComposer: !!document.querySelector(".chat-input, textarea"),
      viewer: !!document.querySelector(".viewer-panel"),
      parametersTab: document.querySelector(".right-panel-tab.active")?.textContent?.trim(),
      settingsButton: !!document.querySelector(".settings-toggle"),
      rightPanel: rect(".right-panel"),
      horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 2,
    };
  });
  assert(emptyWorkspace.workbench, "real app workbench is not visible");
  assert(emptyWorkspace.chatComposer, "real app chat composer is not visible");
  assert(emptyWorkspace.viewer, "real app CAD viewer is not visible");
  assert(emptyWorkspace.parametersTab === "参数编辑", "real app parameter tab is not active");
  assert(emptyWorkspace.settingsButton, "real app Settings button is not visible");
  assert(!emptyWorkspace.horizontalOverflow, "real app desktop has horizontal overflow");

  await page.evaluate(() => {
    document.querySelector(".settings-toggle")?.click();
    return true;
  });
  await delay(250);
  const settings = await page.evaluate(() => {
    const dropdown = document.querySelector(".settings-dropdown");
    if (!dropdown) return { open: false };
    const box = dropdown.getBoundingClientRect();
    return {
      open: true,
      hasBackend: dropdown.textContent.includes("CAD 后端"),
      hasLlm: dropdown.textContent.includes("LLM 配置"),
      withinViewport: box.left >= 0 && box.right <= window.innerWidth && box.top >= 0,
    };
  });
  assert(settings.open, "Settings dropdown did not open");
  assert(settings.hasBackend && settings.hasLlm, "Settings dropdown missing expected controls");
  assert(settings.withinViewport, "Settings dropdown escapes desktop viewport");

  await page.evaluate(() => {
    document.querySelector(".settings-toggle")?.click();
    document.querySelector(".topbar-compare")?.click();
    return true;
  });
  await delay(250);
  const compareEmpty = await page.evaluate(() => {
    const drawer = document.querySelector(".compare-drawer");
    return {
      open: !!drawer,
      role: drawer?.getAttribute("role"),
      modal: drawer?.getAttribute("aria-modal"),
      empty: !!document.querySelector(".compare-empty-state"),
      title: document.querySelector(".compare-empty-title")?.textContent?.trim(),
    };
  });
  assert(compareEmpty.open, "Compare empty drawer did not open");
  assert(compareEmpty.role === "dialog" && compareEmpty.modal === "true", "Compare drawer dialog semantics missing");
  assert(compareEmpty.empty && compareEmpty.title === "还没有加入对比的方案", "Compare empty state missing");

  await page.send("Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "Escape",
    code: "Escape",
    windowsVirtualKeyCode: 27,
  });
  await page.send("Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "Escape",
    code: "Escape",
    windowsVirtualKeyCode: 27,
  });
  await delay(250);
  await page.evaluate(() => {
    [...document.querySelectorAll(".right-panel-tab")]
      .find((element) => element.textContent?.includes("深度设计"))
      ?.click();
    return true;
  });
  await delay(250);
  const deepDesignForm = await page.evaluate(() => {
    const form = document.querySelector(".deep-design-form");
    const prompt = document.querySelector(".deep-design-prompt");
    const primaryAction = [...document.querySelectorAll(".deep-design-actions .button-primary")]
      .find((element) => element.textContent?.includes("开始探索"));
    const visible = (element) => {
      if (!element) return false;
      const box = element.getBoundingClientRect();
      return box.width > 0 && box.height > 0;
    };
    const overflowingControls = [...document.querySelectorAll(
      ".deep-design-form button, .deep-design-form label, .deep-design-form textarea",
    )].filter((element) => element.scrollWidth > element.clientWidth + 2);
    return {
      activeTab: document.querySelector(".right-panel-tab.active")?.textContent?.trim(),
      formVisible: visible(form),
      promptVisible: visible(prompt),
      promptPlaceholder: prompt?.getAttribute("placeholder") ?? "",
      strategies: document.querySelectorAll(".deep-design-strategy input[type='checkbox']").length,
      depths: document.querySelectorAll(".deep-design-depth input[type='radio']").length,
      checkedDepth: document.querySelector(".deep-design-depth input[type='radio']:checked")
        ?.closest(".deep-design-depth")
        ?.textContent
        ?.trim(),
      primaryActionVisible: visible(primaryAction),
      primaryActionDisabled: primaryAction?.disabled ?? null,
      overflowingControls: overflowingControls.map((element) => element.textContent?.trim()),
      horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 2,
    };
  });
  assert(deepDesignForm.activeTab === "深度设计", "Deep Design tab is not active on desktop");
  assert(deepDesignForm.formVisible, "Deep Design form is not visible");
  assert(deepDesignForm.promptVisible, "Deep Design prompt textarea is not visible");
  assert(deepDesignForm.promptPlaceholder.includes("无人机"), "Deep Design prompt placeholder is missing");
  assert(deepDesignForm.strategies === 4, "Deep Design strategy controls missing");
  assert(deepDesignForm.depths === 3, "Deep Design depth controls missing");
  assert(deepDesignForm.checkedDepth?.includes("标准探索"), "Deep Design default depth is not selected");
  assert(deepDesignForm.primaryActionVisible, "Deep Design primary action is not visible");
  assert(deepDesignForm.primaryActionDisabled === true, "Deep Design primary action should be disabled with empty prompt");
  assert(deepDesignForm.overflowingControls.length === 0, `Deep Design form controls overflow: ${JSON.stringify(deepDesignForm.overflowingControls)}`);
  assert(!deepDesignForm.horizontalOverflow, "Deep Design form creates desktop horizontal overflow");

  await page.send("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 844,
    deviceScaleFactor: 2,
    mobile: true,
  });
  await page.send("Page.navigate", { url: APP_URL });
  await delay(1200);
  const mobileRightPanelInitial = await page.evaluate(() => {
    const visible = (element) => {
      if (!element) return false;
      const box = element.getBoundingClientRect();
      return box.width > 0 && box.height > 0 && box.bottom >= 0 && box.top <= window.innerHeight;
    };
    const tabs = [...document.querySelectorAll(".right-panel-tab")];
    return {
      tabsVisible: visible(document.querySelector(".right-panel-tabs")),
      labels: tabs.map((tab) => tab.textContent?.trim()),
      visibleTabs: tabs.filter(visible).length,
      active: document.querySelector(".right-panel-tab.active")?.textContent?.trim(),
      overflowingTabs: tabs
        .filter((tab) => tab.scrollWidth > tab.clientWidth + 2)
        .map((tab) => tab.textContent?.trim()),
      horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 2,
    };
  });
  assert(mobileRightPanelInitial.tabsVisible, "right-panel tabs are not visible at 390px");
  assert(mobileRightPanelInitial.visibleTabs === 2, "both right-panel tabs are not visible at 390px");
  assert(mobileRightPanelInitial.labels.includes("参数编辑") && mobileRightPanelInitial.labels.includes("深度设计"), "right-panel tab labels missing at 390px");
  assert(mobileRightPanelInitial.active === "参数编辑", "parameters tab is not active by default at 390px");
  assert(mobileRightPanelInitial.overflowingTabs.length === 0, `right-panel tab text overflows at 390px: ${JSON.stringify(mobileRightPanelInitial.overflowingTabs)}`);
  assert(!mobileRightPanelInitial.horizontalOverflow, "real app has page-level horizontal overflow at 390px");

  await page.evaluate(() => {
    [...document.querySelectorAll(".right-panel-tab")]
      .find((element) => element.textContent?.includes("深度设计"))
      ?.click();
    return true;
  });
  await delay(250);
  const mobileRightPanelDeepDesign = await page.evaluate(() => ({
    active: document.querySelector(".right-panel-tab.active")?.textContent?.trim(),
    formVisible: !!document.querySelector(".deep-design-form"),
    horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 2,
  }));
  assert(mobileRightPanelDeepDesign.active === "深度设计", "Deep Design tab does not become active at 390px");
  assert(mobileRightPanelDeepDesign.formVisible, "Deep Design form is not visible after mobile tab switch");
  assert(!mobileRightPanelDeepDesign.horizontalOverflow, "Deep Design mobile tab creates horizontal overflow");

  await page.evaluate(() => {
    [...document.querySelectorAll(".right-panel-tab")]
      .find((element) => element.textContent?.includes("参数编辑"))
      ?.click();
    return true;
  });
  await delay(250);
  const mobileRightPanelParameters = await page.evaluate(() => ({
    active: document.querySelector(".right-panel-tab.active")?.textContent?.trim(),
    contentVisible: !!document.querySelector(".right-panel-content"),
    overflowingButtons: [...document.querySelectorAll(".right-panel button")]
      .filter((button) => button.scrollWidth > button.clientWidth + 2)
      .map((button) => button.textContent?.trim()),
    horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 2,
  }));
  assert(mobileRightPanelParameters.active === "参数编辑", "Parameters tab does not become active again at 390px");
  assert(mobileRightPanelParameters.contentVisible, "right-panel content is not visible after mobile tab switch");
  assert(mobileRightPanelParameters.overflowingButtons.length === 0, `right-panel button text overflows at 390px: ${JSON.stringify(mobileRightPanelParameters.overflowingButtons)}`);
  assert(!mobileRightPanelParameters.horizontalOverflow, "Parameters mobile tab creates horizontal overflow");

  return {
    emptyWorkspace,
    settings,
    compareEmpty,
    deepDesignForm,
    mobileRightPanelInitial,
    mobileRightPanelDeepDesign,
    mobileRightPanelParameters,
  };
}

function fixtureHtml() {
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Task 6 UI QA Fixture</title>
  <style>${css}</style>
  <style>
    body { min-height: 100vh; overflow-x: hidden; }
    .qa-fixture { display: grid; gap: 24px; padding: 24px; }
    .qa-section { display: grid; gap: 12px; min-width: 0; }
    .qa-frame { position: relative; min-height: 520px; border: 1px solid var(--border-default); overflow: hidden; }
    .qa-frame .compare-drawer-scrim { position: absolute; }
    .qa-frame .compare-drawer { width: min(720px, 100%); }
    .qa-frame .compare-drawer-table { min-width: 980px; }
    .qa-cad-frame { position: relative; min-height: 260px; border: 1px solid var(--border-default); background: var(--bg-panel); }
  </style>
</head>
<body>
  <main class="qa-fixture">
    <section class="qa-section" id="compare-one">
      <div class="qa-frame">
        <div class="compare-drawer-scrim">
          <div class="compare-drawer" role="dialog" aria-modal="true" aria-labelledby="compare-one-title">
            <div class="compare-drawer-header">
              <div class="compare-drawer-title-row">
                <span id="compare-one-title" class="compare-drawer-title">方案对比</span>
                <span class="pill pill-neutral">1 个方案</span>
              </div>
              <div class="compare-drawer-actions">
                <button class="toolbar-button" disabled>导出对比报告</button>
                <button class="toolbar-button compare-clear-button">清空对比</button>
                <button class="icon-button" aria-label="关闭对比">&times;</button>
              </div>
            </div>
            <div class="compare-drawer-body">
              <div class="compare-empty-state">
                <span class="compare-empty-title">请至少加入 2 个方案进行对比</span>
                <span class="compare-empty-subtitle">在版本历史或 Deep Design 方案中点击「加入对比」</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="qa-section" id="compare-three">
      <div class="qa-frame">
        <div class="compare-drawer-scrim">
          <div class="compare-drawer" role="dialog" aria-modal="true" aria-labelledby="compare-three-title">
            <div class="compare-drawer-header">
              <div class="compare-drawer-title-row">
                <span id="compare-three-title" class="compare-drawer-title">方案对比</span>
                <span class="pill pill-neutral">3 个方案</span>
              </div>
              <div class="compare-drawer-actions">
                <button class="toolbar-button">导出对比报告</button>
                <button class="toolbar-button compare-clear-button">清空对比</button>
                <button class="icon-button" aria-label="关闭对比">&times;</button>
              </div>
            </div>
            <div class="compare-drawer-body">
              <div class="notice notice-info">当前指标为概念设计阶段估算，用于方案初筛，不代表高保真气动或结构分析结果。</div>
              <div class="notice notice-warning">部分方案包含较多系统默认补全参数，默认补全越多说明由系统假设的内容越多。</div>
              <div class="compare-item-row">
                ${["长航时方案", "高速方案", "载荷方案"].map((name, index) => `
                <div class="compare-item-slot">
                  <div class="compare-item-card">
                    <div class="compare-item-card-header">
                      <span class="compare-item-name">${name}</span>
                      <span class="compare-source-pill compare-source-${index === 1 ? "recommended" : "deep-design-variant"}">${index === 1 ? "推荐方案" : "Deep Design"}</span>
                      <span class="compare-item-version">v${index + 1}</span>
                    </div>
                    <div class="compare-defaulted-hint${index === 2 ? " compare-defaulted-warning" : ""}">${index === 2 ? "默认补全较多 4 项" : "默认补全 1 项"}</div>
                    <div class="compare-risk-row"><span class="compare-risk-badge risk-level risk-level-${index === 2 ? "high" : "low"}">${index === 2 ? "风险：高" : "风险：低"}</span></div>
                    <div class="compare-item-actions">
                      <button class="toolbar-button compare-item-button">查看模型</button>
                      <button class="toolbar-button compare-item-button">设为当前</button>
                      <button class="toolbar-button compare-item-button">移除</button>
                    </div>
                  </div>
                </div>`).join("")}
              </div>
              <div class="compare-table-scroll">
                <table class="compare-table compare-drawer-table">
                  <thead>
                    <tr>
                      <th class="compare-metric-heading">指标</th>
                      <th class="compare-item-heading">长航时方案</th>
                      <th class="compare-item-heading">高速方案</th>
                      <th class="compare-item-heading">载荷方案</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${["翼展", "翼面积", "展弦比", "估算升阻比", "估算航程", "估算续航", "翼载荷", "风险等级"].map((label, index) => `
                    <tr>
                      <th scope="row" class="compare-metric-label">${label}</th>
                      <td class="compare-metric-value"><span class="compare-metric-cell${index === 4 ? " compare-metric-best" : ""}">${index + 12}.${index}</span></td>
                      <td class="compare-metric-value"><span class="compare-metric-cell">${index + 10}.${index}</span></td>
                      <td class="compare-metric-value"><span class="compare-metric-cell compare-metric-warning">需确认</span></td>
                    </tr>`).join("")}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="qa-section deep-design-panel" id="deep-design-running">
      <div class="deep-design-section graph-execution-panel">
        <ol class="workflow-timeline workflow-timeline-deep-design">
          <li class="workflow-stage workflow-stage-completed status-success" aria-label="解析需求 已完成">
            <div class="workflow-stage-row"><span class="workflow-stage-indicator" aria-hidden="true">✓</span><span class="workflow-stage-label">解析需求</span></div>
          </li>
          <li class="workflow-stage workflow-stage-running status-running" aria-label="生成候选方案 运行中">
            <div class="workflow-stage-row"><span class="workflow-stage-indicator" aria-hidden="true">⟳</span><span class="workflow-stage-label">生成候选方案</span></div>
          </li>
        </ol>
      </div>
      <div class="recommended-variant-card">
        <div class="recommended-variant-header">
          <div class="recommended-variant-title"><span class="recommended-variant-name">推荐方案: endurance-v2</span><span class="recommended-variant-badge">AI 推荐</span></div>
          <span class="pill recommended-variant-version">v2</span>
        </div>
        <div class="recommended-variant-reasons"><span class="recommended-variant-reasons-title">推荐原因：</span><div class="recommended-variant-reason"><span class="recommended-variant-check">✓</span><span>航程更高且风险较低</span></div></div>
        <div class="graph-card-actions"><button class="toolbar-button recommended-variant-view">查看模型</button><button class="toolbar-button button-primary recommended-variant-applying" disabled>应用中...</button><button class="toolbar-button add-to-compare" disabled>对比已满</button></div>
      </div>
      <div class="variant-summary-card">
        <div class="variant-summary-header">
          <div class="variant-thumbnail variant-thumbnail-succeeded"></div>
          <div class="variant-summary-main">
            <div class="variant-summary-title-row"><span class="variant-summary-name">endurance-v2</span><span class="variant-status variant-status-succeeded">✓ 已完成</span></div>
            <span class="variant-summary-version">v2 <span class="trust-badge trust-confidence-high">高可信 · Fake CAD</span></span>
          </div>
        </div>
      </div>
    </section>

    <section class="qa-section" id="runtime-states">
      <div class="qa-cad-frame">
        <div class="cad-loading-overlay cad-loading-overlay--full">
          <div class="cad-loading-skeleton"><div class="cad-loading-skeleton-fuselage"></div><div class="cad-loading-skeleton-engine"></div><div class="cad-loading-skeleton-copy"></div></div>
          <div class="cad-loading-overlay-copy">生成 CAD 模型 (45%)</div>
          <div class="cad-loading-overlay-progress cad-loading-overlay-progress-full"><div class="cad-loading-overlay-progress-track"><div class="cad-loading-overlay-progress-fill" style="width:45%"></div></div></div>
        </div>
      </div>
      <div class="qa-cad-frame">
        <div class="cad-loading-overlay cad-loading-overlay--error">
          <div class="cad-loading-overlay-error-icon">⚠</div><div class="cad-loading-overlay-error-title">生成失败</div><div class="cad-loading-overlay-error-copy">OpenVSP 导出失败</div><div class="cad-loading-overlay-error-note">之前的模型仍然可用</div>
        </div>
      </div>
      <div class="tool-card tool-card-running">
        <div class="tool-card-header"><span class="spinner"></span><span class="tool-card-name">生成设计</span><span class="version-badge">v3</span></div>
        <div class="tool-card-body">
          <ol class="workflow-timeline"><li class="workflow-stage workflow-stage-running status-running" aria-label="生成 CAD 运行中"><div class="workflow-stage-row"><span class="workflow-stage-indicator" aria-hidden="true">⟳</span><span class="workflow-stage-label">生成 CAD</span></div></li></ol>
          <div class="workflow-progress-bar"><div class="workflow-progress-track"><div class="workflow-progress-fill" style="width:62%"></div></div><div class="workflow-progress-value">62%</div></div>
        </div>
      </div>
      <div class="runtime-notice runtime-notice-info">
        <button type="button" class="runtime-notice-toggle" aria-expanded="true" aria-controls="defaulted-fixture"><span class="runtime-notice-icon">ℹ</span>系统已补全 2 个必要参数<span class="runtime-notice-caret">▾</span></button>
        <div id="defaulted-fixture" class="runtime-notice-body"><p class="runtime-notice-copy">以下参数由系统根据规则自动补全。</p><table class="runtime-notice-table"><thead><tr><th scope="col">参数</th><th scope="col">默认值</th><th scope="col">原因</th></tr></thead><tbody><tr><td>翼展</td><td>12 m</td><td>满足最小设计规则</td></tr></tbody></table></div>
      </div>
      <div class="workflow-error-card runtime-notice status-error">
        <div class="workflow-error-header"><span class="workflow-error-icon">✗</span><span class="workflow-error-title">生成流程在 CAD 导出 阶段失败</span></div>
        <p class="workflow-error-copy">导出 STEP 文件失败</p>
        <div class="workflow-error-actions"><button class="workflow-error-retry">重试</button><button class="workflow-error-logs">查看日志</button></div>
      </div>
      <div class="runtime-notice runtime-notice-info">
        <button type="button" class="runtime-notice-toggle" aria-expanded="true" aria-controls="fallback-fixture"><span class="runtime-notice-icon">ⓘ</span>模型未调用工具，系统自动识别并执行<span class="runtime-notice-caret">▾</span></button>
        <p id="fallback-fixture" class="runtime-notice-copy">当前模型未原生支持工具调用。系统自动映射为「生成设计」操作。置信度: 86%。</p>
      </div>
    </section>
  </main>
</body>
</html>`;
}

async function qaFixture(page) {
  await page.send("Emulation.setDeviceMetricsOverride", {
    width: 820,
    height: 1200,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await page.send("Page.navigate", {
    url: `data:text/html;charset=utf-8,${encodeURIComponent(fixtureHtml())}`,
  });
  await delay(500);

  const desktop = await page.evaluate(() => {
    const disabledText = (selector) => document.querySelector(selector)?.disabled ?? null;
    const one = document.querySelector("#compare-one");
    const three = document.querySelector("#compare-three");
    const tableScroll = three?.querySelector(".compare-table-scroll");
    return {
      compareOne: {
        header: one?.querySelector(".compare-drawer-title")?.textContent?.trim(),
        count: one?.querySelector(".pill")?.textContent?.trim(),
        minNotice: one?.textContent?.includes("请至少加入 2 个方案进行对比"),
        exportDisabled: disabledText("#compare-one .compare-drawer-actions .toolbar-button"),
      },
      compareThree: {
        header: three?.querySelector(".compare-drawer-title")?.textContent?.trim(),
        notices: three?.querySelectorAll(".notice").length,
        cards: three?.querySelectorAll(".compare-item-card").length,
        table: !!three?.querySelector(".compare-drawer-table"),
        actions: three?.querySelectorAll(".compare-item-button").length,
        tableHasOverflow: tableScroll ? tableScroll.scrollWidth > tableScroll.clientWidth : false,
      },
      deepDesign: {
        timeline: !!document.querySelector("#deep-design-running .workflow-timeline"),
        runningStage: !!document.querySelector("#deep-design-running .workflow-stage-running.status-running"),
        recommended: !!document.querySelector(".recommended-variant-card"),
        recommendedDisabled: document.querySelector(".recommended-variant-applying")?.disabled ?? false,
        summary: !!document.querySelector(".variant-summary-card"),
        trust: document.querySelector(".trust-badge")?.textContent?.trim(),
      },
      runtime: {
        cadLoading: !!document.querySelector(".cad-loading-overlay--full .cad-loading-overlay-progress-fill"),
        cadError: !!document.querySelector(".cad-loading-overlay--error .cad-loading-overlay-error-title"),
        taskProgress: document.querySelector(".workflow-progress-value")?.textContent?.trim(),
        defaultedNotice: !!document.querySelector(".runtime-notice-table th"),
        workflowError: !!document.querySelector(".workflow-error-card .workflow-error-retry"),
        fallbackNotice: document.body.textContent.includes("模型未调用工具"),
      },
      horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 2,
    };
  });

  assert(desktop.compareOne.header === "方案对比", "Compare one-item header missing");
  assert(desktop.compareOne.count === "1 个方案", "Compare one-item count missing");
  assert(desktop.compareOne.minNotice, "Compare one-item minimum notice missing");
  assert(desktop.compareOne.exportDisabled === true, "Compare one-item export action is not disabled");
  assert(desktop.compareThree.notices === 2, "Compare 2+ notices missing");
  assert(desktop.compareThree.cards === 3, "Compare 2+ cards missing");
  assert(desktop.compareThree.table, "Compare 2+ table missing");
  assert(desktop.compareThree.actions >= 9, "Compare card actions missing");
  assert(desktop.compareThree.tableHasOverflow, "Compare table overflow is not exercised");
  assert(desktop.deepDesign.timeline, "Deep Design running timeline missing");
  assert(desktop.deepDesign.runningStage, "Deep Design running state class missing");
  assert(desktop.deepDesign.recommended, "Recommended variant card missing");
  assert(desktop.deepDesign.recommendedDisabled, "Recommended applying disabled state missing");
  assert(desktop.deepDesign.summary, "Variant summary card missing");
  assert(desktop.deepDesign.trust?.includes("高可信"), "Variant summary trust badge missing");
  assert(desktop.runtime.cadLoading, "CAD loading state missing");
  assert(desktop.runtime.cadError, "CAD error state missing");
  assert(desktop.runtime.taskProgress === "62%", "Runtime task progress missing");
  assert(desktop.runtime.defaultedNotice, "Defaulted-fields notice missing");
  assert(desktop.runtime.workflowError, "Workflow error card missing");
  assert(desktop.runtime.fallbackNotice, "Chat fallback notice missing");
  assert(!desktop.horizontalOverflow, "Fixture desktop has page-level horizontal overflow");

  await page.send("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 844,
    deviceScaleFactor: 2,
    mobile: true,
  });
  await delay(300);
  const mobile = await page.evaluate(() => {
    const drawer = document.querySelector("#compare-three .compare-drawer");
    const tableScroll = document.querySelector("#compare-three .compare-table-scroll");
    const drawerBox = drawer?.getBoundingClientRect();
    return {
      drawerFits: drawerBox ? drawerBox.left >= 0 && drawerBox.right <= window.innerWidth : false,
      tableOverflow: tableScroll ? tableScroll.scrollWidth > tableScroll.clientWidth : false,
      pageHorizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 2,
      overflowingButtons: [...document.querySelectorAll("button")].filter((button) => button.scrollWidth > button.clientWidth + 2).length,
    };
  });
  assert(mobile.drawerFits, "Compare drawer does not fit narrow viewport");
  assert(mobile.tableOverflow, "Compare table horizontal overflow is not available on narrow viewport");
  assert(!mobile.pageHorizontalOverflow, "Fixture narrow viewport has page-level horizontal overflow");
  assert(mobile.overflowingButtons === 0, "Buttons overflow their text on narrow viewport");

  return { desktop, mobile };
}

async function main() {
  let next = null;
  let chrome = null;
  let userDataDir = null;
  try {
    const chromePort = process.env.TASK6_QA_CHROME_PORT
      ? Number(process.env.TASK6_QA_CHROME_PORT)
      : await getFreePort();
    assert(Number.isInteger(chromePort) && chromePort > 0, "TASK6_QA_CHROME_PORT must be a positive integer");
    if (process.env.TASK6_QA_CHROME_PORT) {
      assert(
        await isPortAvailable(chromePort),
        `Chrome debugging port ${chromePort} is already in use`,
      );
    }

    userDataDir = mkdtempSync(join(tmpdir(), "aero-spec-agent-task6-browser-qa-"));
    next = startNextDev();
    chrome = startChrome({ port: chromePort, userDataDir });

    await Promise.all([
      waitForHttp(APP_URL, 30000),
      waitForJson(`http://127.0.0.1:${chromePort}/json/version`, 30000),
    ]);

    const { page, targetId } = await openCdpPage(APP_URL, chromePort);
    try {
      const realApp = await qaRealApp(page);
      const fixture = await qaFixture(page);
      const blockingConsole = page.consoleMessages.filter((message) =>
        message.type === "error" || message.type === "exception",
      );
      assert(blockingConsole.length === 0, `Browser console errors: ${JSON.stringify(blockingConsole)}`);
      const networkFailures = page.failedRequests.filter((request) =>
        !request.errorText?.includes("ERR_ABORTED"),
      );
      console.log(JSON.stringify({ realApp, fixture, networkFailures }, null, 2));
    } finally {
      await closeTarget(page, targetId);
    }
  } finally {
    stopProcessGroup(next);
    stopProcessGroup(chrome);
    if (userDataDir) {
      await removeDirectoryWithRetry(userDataDir);
    }
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
