import { type NextRequest } from "next/server";
import { createOpenAI } from "@ai-sdk/openai";
import { generateText } from "ai";

export async function POST(req: NextRequest) {
  const { modelName, apiKey, baseUrl } = await req.json();

  if (!apiKey) {
    return Response.json({ ok: false, error: "缺少 API Key" }, { status: 400 });
  }

  try {
    const openai = createOpenAI({ apiKey, baseURL: baseUrl || undefined });
    await generateText({
      model: openai(modelName || "gpt-4o"),
      prompt: "hi",
      maxOutputTokens: 5,
    });
    return Response.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "连接失败";
    return Response.json({ ok: false, error: message }, { status: 502 });
  }
}
