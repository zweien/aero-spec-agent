import { type NextRequest } from "next/server";

export async function POST(req: NextRequest) {
  const { modelName, apiKey, baseUrl } = await req.json();

  if (!apiKey) {
    return Response.json({ ok: false, error: "缺少 API Key" }, { status: 400 });
  }

  const url = `${baseUrl || "https://api.openai.com/v1"}/chat/completions`;

  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: modelName || "gpt-4o",
        messages: [{ role: "user", content: "hi" }],
        max_tokens: 5,
      }),
      signal: AbortSignal.timeout(15000),
    });

    if (!resp.ok) {
      const body = await resp.text().catch(() => "");
      const hint = resp.status === 502 ? " (上游服务不可用)" : "";
      return Response.json({
        ok: false,
        error: `HTTP ${resp.status}${hint}: ${body.slice(0, 120) || "(空响应)"}`,
      }, { status: 502 });
    }

    // Verify the response is valid JSON with choices
    const data = await resp.json();
    if (data?.choices?.length) {
      return Response.json({ ok: true });
    }
    return Response.json({
      ok: false,
      error: `API 返回格式异常: ${JSON.stringify(data).slice(0, 120)}`,
    }, { status: 502 });
  } catch (err) {
    const message = err instanceof Error ? err.message : "连接失败";
    const cause = (err as { cause?: { code?: string; message?: string } }).cause;
    if (message.includes("abort") || message.includes("timeout")) {
      return Response.json({ ok: false, error: "连接超时（15秒），请检查 Base URL 是否正确" }, { status: 502 });
    }
    if (cause?.code === "UND_ERR_SOCKET" || message.includes("other side closed") || message.includes("ECONNREFUSED")) {
      return Response.json({ ok: false, error: "无法连接到 API 服务器，请检查 Base URL 和网络" }, { status: 502 });
    }
    if (message === "fetch failed") {
      return Response.json({ ok: false, error: "DNS 解析失败或网络不可达，请检查 Base URL" }, { status: 502 });
    }
    return Response.json({ ok: false, error: message }, { status: 502 });
  }
}
