import {
  CopywritingResult,
  CreativeFactors,
  DeconstructedVisual,
  ImageGenResult,
  LyricsResult,
  PairedPromptResult,
  PromptConfig,
  PromptGenParams,
  PromptHistoryItem,
  PromptHistoryResponse,
  PromptStatus,
  RecognizedImageResult,
} from "../types";
import { delay, requestJson } from "./client";

interface CopyStatus {
  running: boolean;
  progress: number;
  total: number;
  message: string;
  elapsed: number;
}

interface CopyResultResponse {
  results: string[];
  total_count: number;
  accepted_count: number;
}

interface LocalImageRecognitionResponse {
  success: boolean;
  id: number;
  result: {
    analysis?: string;
  };
  thumb?: string;
}

const COPY_TYPE_BY_PLATFORM: Record<string, string> = {
  xiaohongshu: "朋友圈/社群",
  douyin: "15秒带货口播",
  wechat: "朋友圈/社群",
};

// ═══════════════════════════════════════════
// Prompt generation APIs
// ═══════════════════════════════════════════

export async function getPromptConfig(): Promise<PromptConfig> {
  return requestJson<PromptConfig>("/api/prompt/config");
}

export async function startPromptGeneration(params: PromptGenParams): Promise<{ success: boolean }> {
  return requestJson<{ success: boolean }>("/api/prompt/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}

export async function stopPromptGeneration(): Promise<{ success: boolean }> {
  return requestJson<{ success: boolean }>("/api/prompt/stop", { method: "POST" });
}

export async function getPromptStatus(): Promise<PromptStatus> {
  return requestJson<PromptStatus>("/api/prompt/status");
}

export async function getPromptHistory(params: {
  page?: number;
  page_size?: number;
  sort?: string;
  search?: string;
}): Promise<PromptHistoryResponse> {
  const qs = new URLSearchParams();
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  if (params.sort) qs.set("sort", params.sort);
  if (params.search) qs.set("search", params.search);
  return requestJson<PromptHistoryResponse>(`/api/prompt/history?${qs.toString()}`);
}

export async function deletePromptHistory(pid: number): Promise<{ success: boolean }> {
  return requestJson<{ success: boolean }>(`/api/prompt/history/${pid}`, { method: "DELETE" });
}

export async function deletePromptHistoryBatch(ids: number[]): Promise<{ success: boolean }> {
  return requestJson<{ success: boolean }>("/api/prompt/history/batch-delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  });
}

export async function markPromptCopied(pid: number): Promise<{ success: boolean }> {
  return requestJson<{ success: boolean }>(`/api/prompt/history/${pid}/copy`, { method: "POST" });
}

export async function pollPromptUntilDone(
  onStatus?: (status: PromptStatus) => void,
  maxAttempts = 120,
  intervalMs = 800
): Promise<PromptStatus> {
  for (let i = 0; i < maxAttempts; i += 1) {
    const status = await getPromptStatus();
    onStatus?.(status);
    if (!status.running) return status;
    await delay(intervalMs);
  }
  throw new Error("提示词生成超时，请稍后在历史记录中查看。");
}

// ═══════════════════════════════════════════

interface SinglePromptResponse {
  success: boolean;
  title: string;
  prompt: string;
  chinesePrompt: string;
  englishPrompt: string;
}

export async function generateLocalPrompt(input: CreativeFactors & {
  aspectRatio?: string;
  styleQuality?: string;
  model?: string;
  audience?: string;
  scene?: string;
  weather?: string;
  style?: string;
  action?: string;
  minProduct?: number;
  maxProduct?: number;
  tolerance?: number;
  extra?: string;
}): Promise<PairedPromptResult> {
  const body: Record<string, unknown> = {
    model: input.model || "deepseek4",
    audience: input.audience || "默认随机(按画像比例55/15/30)",
    scene: input.scene || input.scene || "随机",
    weather: input.weather || input.lighting || "随机",
    style: input.style || "随机",
    action: input.action || input.posture || "随机",
    min_product: input.minProduct ?? 1,
    max_product: input.maxProduct ?? 1,
    tolerance: input.tolerance ?? 65,
    aspect_ratio: input.aspectRatio || "1:1",
    style_quality: input.styleQuality || "写实",
    subject: input.subject || "",
    extra: input.extra || [
      input.helper && `辅助要求：${input.helper}`,
    ].filter(Boolean).join("\n"),
  };

  const data = await requestJson<SinglePromptResponse>("/api/prompt/generate-single", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  return {
    title: data.title || extractTitle(data.prompt),
    chinesePrompt: data.chinesePrompt || data.prompt,
    englishPrompt: data.englishPrompt || data.prompt,
  };
}

export async function generateLocalImage(input: {
  prompt: string;
  aspectRatio: string;
}): Promise<ImageGenResult> {
  return requestJson<ImageGenResult>("/api/gpt-image/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt: input.prompt,
      aspectRatio: input.aspectRatio,
      n: 1,
      quality: "high",
    }),
  });
}

export async function deconstructLocalVisual(input: {
  imageUrl: string;
  prompt: string;
  title: string;
}): Promise<DeconstructedVisual> {
  let recognized: RecognizedImageResult;
  if (input.imageUrl.startsWith("data:")) {
    recognized = await recognizeImageDataUrl(input.imageUrl);
  } else {
    const data = await requestJson<LocalImageRecognitionResponse>("/api/image/recognize/url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: input.imageUrl }),
    });
    recognized = mapAnalysisToFactors(data.result?.analysis || "");
  }

  return {
    colors: [
      { hex: "#111827", name: "深墨", role: "主视觉底色" },
      { hex: "#F59E0B", name: "麦金", role: "啤酒与暖光联想" },
      { hex: "#F8FAFC", name: "泡沫白", role: "高光与留白" },
      { hex: "#64748B", name: "雾灰", role: "中性背景" },
      { hex: "#16A34A", name: "酒花绿", role: "清新辅助色" },
    ],
    composition: recognized.scene,
    lighting: recognized.lighting,
    depth: recognized.posture,
    vibe: recognized.style,
    recognizedFactors: {
      subject: recognized.subject,
      scene: recognized.scene,
      lighting: recognized.lighting,
      style: recognized.style,
      posture: recognized.posture,
      helper: recognized.helper,
    },
  };
}

export async function recognizeImageDataUrl(imageDataUrl: string): Promise<RecognizedImageResult> {
  const file = dataUrlToFile(imageDataUrl, "upload.png");
  return recognizeImageUpload(file);
}

export async function recognizeImageUpload(file: File): Promise<RecognizedImageResult> {
  const formData = new FormData();
  formData.append("file", file);

  const data = await requestJson<LocalImageRecognitionResponse>("/api/image/recognize/upload", {
    method: "POST",
    body: formData,
  });

  return mapAnalysisToFactors(data.result?.analysis || "");
}

export async function generateLyrics(input: {
  subject: string;
  scene: string;
  style: string;
  title: string;
}): Promise<LyricsResult> {
  const body = await runCopyJob({
    copy_type: "朋友圈/社群",
    count: 1,
    workers: 1,
    custom_topic: [
      input.title && `标题：${input.title}`,
      input.subject && `主体：${input.subject}`,
      input.scene && `场景：${input.scene}`,
      input.style && `风格：${input.style}`,
    ].filter(Boolean).join("\n"),
    custom_style: "写成适合酒标、海报和产品封面的诗意品牌金句，语言克制、有画面感。",
  });

  const title = input.title || extractTitle(body) || "微醺时刻";
  return {
    titles: uniqueNonEmpty([title, "麦香浮光", "晚风入杯"]).slice(0, 3),
    mainVerse: firstSentence(body),
    prose: body,
    tags: ["微醺", "匠心", "麦香"],
  };
}

export async function generateCopywriting(input: {
  title: string;
  factors: string;
  platform: string;
}): Promise<CopywritingResult> {
  const body = await runCopyJob({
    copy_type: COPY_TYPE_BY_PLATFORM[input.platform] || "朋友圈/社群",
    count: 1,
    workers: 1,
    custom_topic: input.factors || input.title || "",
    custom_style: "真实自然，有画面感，根据产品信息生成合适风格的文案。",
  });

  return {
    headline: extractTitle(body) || input.title || "好物推荐",
    body,
    hashtags: extractHashtags(body),
  };
}

async function waitForPromptCompletion() {
  for (let i = 0; i < 120; i += 1) {
    const status = await requestJson<PromptStatus>("/api/prompt/status");
    if (!status.running) return status;
    await delay(800);
  }
  throw new Error("本地提示词生成超时，请稍后在历史记录中查看。");
}

async function runCopyJob(payload: {
  copy_type: string;
  count: number;
  workers: number;
  custom_topic: string;
  custom_style: string;
}) {
  await requestJson<{ success: boolean }>("/api/copy/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  for (let i = 0; i < 180; i += 1) {
    const status = await requestJson<CopyStatus>("/api/copy/status");
    if (!status.running) break;
    await delay(800);
  }

  const result = await requestJson<CopyResultResponse>("/api/copy/result");
  const first = result.results.find((item) => item && !item.startsWith("[FAILED]") && !item.startsWith("[MISSING]"));
  if (!first) {
    throw new Error("本地文案生成完成，但没有可用结果。");
  }
  return first;
}

function dataUrlToFile(dataUrl: string, filename: string) {
  const [header, base64] = dataUrl.split(",");
  const mime = header.match(/data:(.*?);base64/)?.[1] || "image/png";
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new File([bytes], filename, { type: mime });
}

function mapAnalysisToFactors(analysis: string): RecognizedImageResult {
  return {
    subject: sectionText(analysis, ["提取图片主体内容", "画面主体"]) || summary(analysis),
    scene: sectionText(analysis, ["背景场景"]) || "本地识图未单独提取背景场景",
    lighting: sectionText(analysis, ["背景场景", "风格总结"]) || "本地识图未单独提取光影信息",
    style: sectionText(analysis, ["风格总结"]) || "本地识图分析",
    posture: sectionText(analysis, ["整体意图"]) || "本地识图未单独提取主体动作",
    helper: analysis || "本地识图未返回详细分析",
    matchedPreset: "本地识图",
  };
}

function sectionText(text: string, labels: string[]) {
  for (const label of labels) {
    const pattern = new RegExp(`${label}[：:]?\\s*([\\s\\S]*?)(?=\\n\\s*(?:提取图片主体内容|画面主体|背景场景|产品参数|整体意图|风格总结)[：:]?|$)`);
    const match = text.match(pattern);
    const value = match?.[1]?.trim();
    if (value) return value;
  }
  return "";
}

function summary(text: string) {
  return text.split(/\n+/).map((line) => line.trim()).find(Boolean) || "本地识图结果";
}

function firstSentence(text: string) {
  return text.split(/[。！？\n]/).map((line) => line.trim()).find(Boolean) || text;
}

function extractTitle(text: string) {
  const firstLine = text.split(/\n+/).map((line) => line.trim()).find(Boolean) || "";
  return firstLine.replace(/^#+\s*/, "").replace(/^【(.+?)】$/, "$1").slice(0, 24);
}

function extractHashtags(text: string): string[] {
  const matches = text.match(/#[\w一-鿿]+/g);
  if (matches && matches.length) return uniqueNonEmpty(matches).slice(0, 8);
  return ["#好物推荐", "#今日分享"];
}

function uniqueNonEmpty(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));
}
