/**
 * WorkflowPage — 一键短视频方案
 * 8-step: 剧情分镜 → 生图提示词 → 生图 → 评分 → 文案 → 视频提示词 → 视频生成 → 发布标签
 */
import React, { useState, useRef, useEffect } from "react";
import {
  Film, Square, Upload, Copy, Check, ChevronDown,
  RefreshCw, Zap, Clipboard,
  Settings, ChevronRight, AlertTriangle, X, Download, Hash,
} from "lucide-react";
import { WorkflowStatus, WorkflowResult, KeyframeData, PromptConfig, WorkflowEvent, WorkflowHistoryItem } from "../types";
import { startWorkflow, stopWorkflow, uploadProductImage, pollWorkflowUntilDone, getWorkflowLogs, getWorkflowHistory, getWorkflowResult, refreshWorkflowVideoStatus, backfillWorkflowVideoUrl, getScenePool, continueWorkflow, regenerateWorkflowImage, WorkflowParams } from "../api/workflow";
import { apiUrl } from "../api/client";
import { getPromptConfig } from "../api/services";
import { buildWorkflowDiagnosticText, getWorkflowLogRows } from "../workflowDiagnostics";

const STORY_TYPES = [
  { value: "正常性", label: "正常性", desc: "产品展示带货，配合文案配音" },
  { value: "趣味性", label: "趣味性", desc: "脑洞反转剧情，纯画面叙事" },
  { value: "休闲性", label: "休闲性", desc: "生活场景种草，舒适氛围感" },
];

const GENDERS = [
  { value: "随机", label: "随机" },
  { value: "男", label: "男" },
  { value: "女", label: "女" },
];

const SCENES_FALLBACK = [
  "随机", "烧烤大排档", "海边沙滩", "火锅店", "客厅沙发", "露营营地",
  "咖啡店", "KTV包厢", "夜市小吃摊", "江边步道", "公园草坪", "民宿阳台",
  "沙漠公路", "音乐节草坪", "便利店", "大学宿舍", "公司茶水间",
];

const ASPECT_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4"];

const STEP_LABELS: Record<number, string> = {
  1: "生成剧情分镜",
  2: "提取生图提示词",
  3: "gpt-image-2 生图",
  4: "AI 评分",
  5: "生成口播文案",
  6: "汇总视频提示词",
  7: "提交视频生成任务",
  8: "生成发布标签",
};

const SCORE_COLORS: Record<string, string> = {
  "超低": "bg-red-100 text-red-700 border-red-300",
  "低": "bg-orange-100 text-orange-700 border-orange-300",
  "中": "bg-yellow-100 text-yellow-700 border-yellow-300",
  "高": "bg-green-100 text-green-700 border-green-300",
  "超高": "bg-emerald-100 text-emerald-700 border-emerald-300",
};

const VIDEO_STATUS_LABELS: Record<string, string> = {
  not_configured: "未配置",
  submitted: "已提交",
  running: "生成中",
  completed: "已完成",
  failed: "失败",
};

function resolveWorkflowImageUrl(url?: string) {
  if (!url) return "";
  const normalized = url.replace(/\\/g, "/");
  if (/^(https?:|data:|blob:)/i.test(normalized)) return normalized;
  return apiUrl(normalized.startsWith("/") ? normalized : `/${normalized}`);
}

interface WorkflowPageProps {
  isActive: boolean;
  onBusyChange: (busy: boolean) => void;
}

export default function WorkflowPage({ isActive, onBusyChange }: WorkflowPageProps) {
  // ── Config ──
  const [storyType, setStoryType] = useState("正常性");
  const [gender, setGender] = useState("随机");
  const [scene, setScene] = useState("随机");
  const [showSceneDropdown, setShowSceneDropdown] = useState(false);
  const [productImage, setProductImage] = useState("");
  const [productFilename, setProductFilename] = useState("");
  const [uploading, setUploading] = useState(false);
  // ── 高级参数 ──
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [promptConfig, setPromptConfig] = useState<PromptConfig | null>(null);
  const [advModel, setAdvModel] = useState("deepseek4");
  const [advAudience, setAdvAudience] = useState("默认随机(按画像比例55/15/30)");
  const [advWeather, setAdvWeather] = useState("随机");
  const [advStyle, setAdvStyle] = useState("随机");
  const [advAction, setAdvAction] = useState("随机");
  const [advAspectRatio, setAdvAspectRatio] = useState("1:1");
  const [advExtra, setAdvExtra] = useState("");

  // ── Run state ──
  const [running, setRunning] = useState(false);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [status, setStatus] = useState<WorkflowStatus | null>(null);
  const [result, setResult] = useState<WorkflowResult | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState("");
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [scenePool, setScenePool] = useState<string[]>(["随机"]);
  const [videoUrlInput, setVideoUrlInput] = useState("");
  const [videoRefreshing, setVideoRefreshing] = useState(false);
  const [videoSaving, setVideoSaving] = useState(false);
  const [reviewBusy, setReviewBusy] = useState(false);

  // Report busy state to parent (running = workflow in progress)
  useEffect(() => {
    onBusyChange(running);
  }, [running, onBusyChange]);
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);
  const [history, setHistory] = useState<WorkflowHistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadHistory = async () => {
    try {
      const h = await getWorkflowHistory(20);
      setHistory(h.items);
    } catch {}
  };

  useEffect(() => {
    getPromptConfig().then(setPromptConfig).catch(() => {});
    getScenePool().then((r) => setScenePool(["随机", ...r.scenes])).catch(() => setScenePool(["随机", ...SCENES_FALLBACK]));
    loadHistory();
  }, []);

  useEffect(() => {
    if (isActive) loadHistory();
  }, [isActive]);

  const handleToggleHistory = () => {
    if (!showHistory) loadHistory();
    setShowHistory((open) => !open);
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const res = await uploadProductImage(file);
      setProductImage(res.path);
      setProductFilename(res.filename);
    } catch {
      setError("产品图上传失败");
    } finally {
      setUploading(false);
    }
  };

  const handleStart = async () => {
    setError("");
    setResult(null);
    setStatus(null);
    setEvents([]);
    setDiagnosticsOpen(false);
    setRunning(true);
    try {
      const params: WorkflowParams = {
        story_type: storyType,
        gender,
        scene,
        product_image: productImage,
        model: advModel,
        audience: advAudience,
        weather: advWeather,
        style: advStyle,
        action: advAction,
        extra: advExtra,
        aspect_ratio: advAspectRatio,
      };
      const { workflow_id } = await startWorkflow(params);
      setWorkflowId(workflow_id);
      const finalResult = await pollWorkflowUntilDone(
        workflow_id,
        (s) => { setStatus({ ...s }); },
        300,
        1500
      );
      setResult(finalResult);
      setStatus((prev) => prev ? { ...prev, status: finalResult.status, current_step: finalResult.status === "failed" ? `失败: ${finalResult.error_message || "未知错误"}` : "完成" } : null);
      loadHistory();
    } catch (e: any) {
      setError(e.message || "工作流执行失败");
    } finally {
      setRunning(false);
    }
  };

  const handleStop = async () => {
    if (workflowId) {
      await stopWorkflow(workflowId);
      setRunning(false);
    }
  };

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(""), 2000);
  };

  const handleDownloadAll = () => {
    if (!result) return;
    const allText = [
      `# 短视频方案 — ${result.story_type} · ${result.scene}`,
      ``,
      `## 生图提示词`,
      result.image_prompts?.[0] || "(无)",
      ``,
      `## 剧情分镜原文`,
      result.storyboard_text || "(无)",
      ``,
      `## 口播文案`,
      result.copy_text || "(无)",
      ``,
      `## 最终视频提示词`,
      result.video_prompt || "(无)",
    ].join("\n");

    const blob = new Blob([allText], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `workflow_${result.id}_prompts.txt`;
    a.click();
    URL.revokeObjectURL(url);
    setCopied("download");
    setTimeout(() => setCopied(""), 2000);
  };

  const handleDownloadImage = () => {
    if (!result?.image_urls?.[0]) return;
    const a = document.createElement("a");
    a.href = resolveWorkflowImageUrl(result.image_urls[0]);
    a.download = `workflow_${result.id}_img.png`;
    a.click();
  };

  const handleVideoRefresh = async () => {
    if (!workflowId) return;
    setVideoRefreshing(true);
    try {
      const r = await refreshWorkflowVideoStatus(workflowId);
      setResult((prev) => prev ? { ...prev, video_status: r.video_status, video_job_id: r.video_job_id, video_url: r.video_url, video_error: r.video_error } : prev);
    } catch {
      // silently fail — the backend returns current state on error too
    } finally {
      setVideoRefreshing(false);
    }
  };

  const handleVideoBackfill = async () => {
    if (!workflowId || !videoUrlInput.trim()) return;
    setVideoSaving(true);
    try {
      const r = await backfillWorkflowVideoUrl(workflowId, videoUrlInput.trim());
      setResult((prev) => prev ? { ...prev, video_status: r.video_status, video_job_id: r.video_job_id, video_url: r.video_url, video_error: r.video_error } : prev);
      setVideoUrlInput("");
    } catch {
      // silently fail
    } finally {
      setVideoSaving(false);
    }
  };

  const handleReviewContinue = async () => {
    if (!workflowId) return;
    setReviewBusy(true);
    try {
      await continueWorkflow(workflowId);
      // Poll until done (resumed from Step 5)
      const finalResult = await pollWorkflowUntilDone(
        workflowId,
        (s) => { setStatus({ ...s }); },
        300, 1500
      );
      setResult(finalResult);
      setStatus((prev) => prev ? { ...prev, status: finalResult.status, current_step: finalResult.status === "failed" ? `失败: ${finalResult.error_message || "未知错误"}` : "完成" } : null);
    } catch (e: any) {
      setError(e.message || "继续执行失败");
    } finally {
      setReviewBusy(false);
    }
  };

  const handleReviewRegenerate = async () => {
    if (!workflowId) return;
    setReviewBusy(true);
    try {
      await regenerateWorkflowImage(workflowId);
      // Poll until done (regenerated from Step 3)
      const finalResult = await pollWorkflowUntilDone(
        workflowId,
        (s) => { setStatus({ ...s }); },
        300, 1500
      );
      setResult(finalResult);
      setStatus((prev) => prev ? { ...prev, status: finalResult.status, current_step: finalResult.status === "failed" ? `失败: ${finalResult.error_message || "未知错误"}` : "完成" } : null);
      loadHistory();
    } catch (e: any) {
      setError(e.message || "重新生成失败");
    } finally {
      setReviewBusy(false);
    }
  };

  const refreshLogs = async (workflowId: string) => {
    try {
      const logs = await getWorkflowLogs(workflowId);
      setEvents(logs.items);
    } catch {
      // The status poll already shows the main error. Log refresh should not break the workflow UI.
    }
  };

  // Fetch logs only when user explicitly opens the panel
  useEffect(() => {
    if (!diagnosticsOpen || !workflowId) return;
    refreshLogs(workflowId);
    // Refresh every 2s while panel is open
    const timer = setInterval(() => refreshLogs(workflowId), 2000);
    return () => clearInterval(timer);
  }, [diagnosticsOpen, workflowId]);

  const failedEvent = events.find((event) => event.event_type === "failed");
  const activeStep = status?.step_index ?? (result ? 8 : 0);
  const diagnosticText = buildWorkflowDiagnosticText({ events, failedEvent, result, status });
  const logRows = getWorkflowLogRows(events);
  const visibleHistory = history.filter((item) => item.image_urls?.[0]);
  const isFailed = !!failedEvent || status?.status === "failed";
  const currentStepLabel = failedEvent?.step_name || status?.current_step || STEP_LABELS[activeStep] || "正在执行";

  return (
    <div className="flex w-full min-h-[480px] flex-col md:flex-row" id="workflow-page">
      <section className="w-full md:w-[55%] p-5 md:p-8 border-b md:border-b-0 md:border-r border-gray-100 flex flex-col" id="workflow-config">
        <div>
          <div className="flex items-center space-x-3 mb-5">
            <div className="grid grid-cols-2 gap-1 w-5 h-5 text-gray-500">
              <div className="border-2 border-current rounded-[3px]" />
              <div className="border-2 border-current rounded-[3px]" />
              <div className="border-2 border-current rounded-[3px]" />
              <div className="border-2 border-current rounded-[3px]" />
            </div>
            <h2 className="text-xl md:text-2xl font-bold text-gray-900 tracking-tight">短视频导演台</h2>
          </div>

          <div className="flex flex-wrap gap-2.5 mb-5">
            {STORY_TYPES.map((st) => (
              <button
                key={st.value}
                disabled={running}
                onClick={() => setStoryType(st.value)}
                title={st.desc}
                className={`transition-all duration-300 px-5 py-2.5 rounded-full text-sm font-medium border cursor-pointer hover:scale-102 active:scale-98 ${
                  storyType === st.value
                    ? "bg-black text-white border-black shadow-md"
                    : "bg-gray-50 text-gray-700 border-gray-100 hover:bg-gray-100"
                }`}
              >
                {st.label}
              </button>
            ))}
          </div>

          <div className="space-y-3 mb-4">
            <div className="relative">
              <button
                disabled={running}
                onClick={() => fileInputRef.current?.click()}
                className={`w-full min-h-[50px] flex items-center gap-3 px-5 bg-gray-50 border rounded-2xl transition-all cursor-pointer ${
                  productImage
                    ? "border-black text-gray-900 bg-white"
                    : "border-gray-100 hover:bg-gray-100 text-gray-500"
                }`}
              >
                <Upload className="w-5 h-5 text-gray-400 shrink-0" />
                <div className="min-w-0 text-left">
                  <div className="text-sm font-bold text-gray-800">
                    {uploading ? "产品图上传中..." : productFilename || "上传 S101 产品正面照"}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">作为 gpt-image-2 的商品参考图</div>
                </div>
              </button>
              <input ref={fileInputRef} type="file" accept=".png,.jpg,.jpeg" onChange={handleUpload} className="hidden" />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="bg-gray-50 border border-gray-100 rounded-2xl p-3.5">
                <label className="block text-xs font-bold text-gray-500 mb-2">性别锁定</label>
                <div className="flex gap-2">
                  {GENDERS.map((g) => (
                    <button
                      key={g.value}
                      disabled={running}
                      onClick={() => setGender(g.value)}
                      className={`flex-1 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                        gender === g.value ? "bg-black text-white" : "bg-white text-gray-600 border border-gray-100 hover:text-black"
                      }`}
                    >
                      {g.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="relative bg-gray-50 border border-gray-100 rounded-2xl p-3.5">
                <label className="block text-xs font-bold text-gray-500 mb-2">场景</label>
                <button
                  disabled={running}
                  onClick={() => setShowSceneDropdown(!showSceneDropdown)}
                  className="w-full flex items-center justify-between px-3 py-2.5 bg-white border border-gray-100 rounded-xl text-sm text-gray-700 cursor-pointer hover:bg-gray-50"
                >
                  <span className="truncate">{scene}</span>
                  <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" />
                </button>
                {showSceneDropdown && (
                  <div className="absolute left-4 right-4 z-20 mt-1 bg-white border border-gray-100 rounded-xl shadow-xl max-h-48 overflow-y-auto">
                    {scenePool.map((s) => (
                      <button
                        key={s}
                        onClick={() => { setScene(s); setShowSceneDropdown(false); }}
                        className={`w-full text-left px-3 py-2 text-xs hover:bg-gray-50 cursor-pointer ${
                          scene === s ? "text-black font-bold bg-gray-50" : "text-gray-600"
                        }`}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full flex items-center justify-between px-5 py-3 bg-gray-50 border border-gray-100 rounded-2xl hover:bg-gray-100 transition-colors cursor-pointer"
            >
              <span className="text-sm font-bold text-gray-700 flex items-center space-x-2">
                <Settings className="w-4 h-4" />
                <span>高级参数</span>
              </span>
              <ChevronRight className={`w-4 h-4 text-gray-400 transition-transform ${showAdvanced ? "rotate-90" : ""}`} />
            </button>

            {showAdvanced && (
              <div className="bg-gray-50/50 border border-gray-100 rounded-2xl p-5 space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-gray-500 mb-1.5">模型</label>
                    <select value={advModel} onChange={(e) => setAdvModel(e.target.value)} disabled={running} className="w-full px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm text-gray-700 outline-none focus:ring-2 focus:ring-black/10">
                      {(promptConfig?.available_models ? Object.entries(promptConfig.available_models) : [["deepseek4", "DeepSeek V4-Pro"]]).map(([k, v]) => (
                        <option key={k} value={k}>{v}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-500 mb-1.5">目标人群</label>
                    <select value={advAudience} onChange={(e) => setAdvAudience(e.target.value)} disabled={running} className="w-full px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm text-gray-700 outline-none focus:ring-2 focus:ring-black/10">
                      {(promptConfig?.audience_options || ["默认随机(按画像比例55/15/30)"]).map((o) => (
                        <option key={o} value={o}>{o}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-gray-500 mb-1.5">光线/天气</label>
                    <select value={advWeather} onChange={(e) => setAdvWeather(e.target.value)} disabled={running} className="w-full px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm text-gray-700 outline-none focus:ring-2 focus:ring-black/10">
                      {["随机", ...(promptConfig?.weather_options || [])].map((o) => (
                        <option key={o} value={o}>{o}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-500 mb-1.5">视觉风格</label>
                    <select value={advStyle} onChange={(e) => setAdvStyle(e.target.value)} disabled={running} className="w-full px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm text-gray-700 outline-none focus:ring-2 focus:ring-black/10">
                      {["随机", ...(promptConfig?.style_options || [])].map((o) => (
                        <option key={o} value={o}>{o}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-gray-500 mb-1.5">动作/姿态</label>
                    <select value={advAction} onChange={(e) => setAdvAction(e.target.value)} disabled={running} className="w-full px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm text-gray-700 outline-none focus:ring-2 focus:ring-black/10">
                      {["随机", ...(promptConfig?.action_options || [])].map((o) => (
                        <option key={o} value={o}>{o}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-500 mb-1.5">图片比例</label>
                    <select value={advAspectRatio} onChange={(e) => setAdvAspectRatio(e.target.value)} disabled={running} className="w-full px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm text-gray-700 outline-none focus:ring-2 focus:ring-black/10">
                      {ASPECT_RATIOS.map((r) => (
                        <option key={r} value={r}>{r}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-500 mb-1.5">附加要求</label>
                  <input value={advExtra} onChange={(e) => setAdvExtra(e.target.value)} disabled={running} placeholder="如：强调产品拉环盖设计、夜景暖色调..." className="w-full px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm text-gray-700 outline-none focus:ring-2 focus:ring-black/10" />
                </div>
              </div>
            )}
          </div>

          {error && (
            <div className="bg-red-50 border border-red-100 text-red-700 rounded-2xl p-4 text-sm">
              {error}
            </div>
          )}
        </div>

        <div className="mt-4">
          {!running ? (
            <button onClick={handleStart} className="w-full min-h-[58px] rounded-[2rem] bg-black text-white font-bold text-base shadow-xl shadow-gray-300/60 hover:bg-gray-900 transition-all cursor-pointer flex items-center justify-center space-x-3">
              <Zap className="w-5 h-5" />
              <span>一键生成短视频方案</span>
            </button>
          ) : (
            <button onClick={handleStop} className="w-full min-h-[58px] rounded-[2rem] bg-gray-400 text-white font-bold text-base shadow-xl shadow-gray-300/60 hover:bg-gray-500 transition-all cursor-pointer flex items-center justify-center space-x-3">
              <Square className="w-5 h-5" />
              <span>停止生成</span>
            </button>
          )}
        </div>
      </section>

      <section className="w-full md:w-[45%] p-5 md:p-8 flex flex-col relative" id="workflow-monitor">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3 min-w-0">
            <h2 className="text-xl md:text-2xl font-bold text-gray-900 tracking-tight">流水线监视器</h2>
            {visibleHistory.length > 0 && (
              <button
                onClick={handleToggleHistory}
                className={`shrink-0 rounded-full border px-3 py-1.5 text-xs font-bold transition-colors cursor-pointer ${
                  showHistory
                    ? "bg-black text-white border-black"
                    : "bg-gray-50 text-gray-500 border-gray-100 hover:text-black hover:border-gray-200"
                }`}
                type="button"
              >
                历史图片 · {visibleHistory.length}
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            {workflowId && (
              <button
                onClick={() => setDiagnosticsOpen((open) => !open)}
                className={`text-[11px] font-medium hover:text-gray-600 ${
                  diagnosticsOpen ? "text-gray-500" : "text-gray-300"
                }`}
                title="开发者日志"
                type="button"
              >
                log
              </button>
            )}
            {status && (
              <span className={`text-xs px-3 py-1.5 rounded-full font-bold ${
                status.status === "completed" ? "bg-green-100 text-green-700" :
                status.status === "failed" ? "bg-red-100 text-red-700" :
                "bg-gray-100 text-gray-700"
              }`}>
                {status.status === "completed" ? "完成" : status.status === "failed" ? "失败" : "进行中"}
              </span>
            )}
          </div>
        </div>

        {!running && showHistory && visibleHistory.length > 0 && (
          <div className="absolute left-5 right-5 md:left-8 md:right-8 top-[4.75rem] z-20 rounded-3xl border border-gray-100 bg-white p-4 shadow-2xl shadow-gray-200/80">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-xs font-bold text-gray-400 tracking-wider">
                历史图片 · {visibleHistory.length} 张
              </h3>
              <button
                onClick={() => setShowHistory(false)}
                className="text-xs font-bold text-gray-400 hover:text-black cursor-pointer"
                type="button"
              >
                收起
              </button>
            </div>
            <div className="grid grid-cols-3 gap-2 max-h-[360px] overflow-y-auto pr-1">
              {visibleHistory.map((item) => (
                <button
                  key={item.id}
                  onClick={() => {
                    setWorkflowId(item.id);
                    setShowHistory(false);
                    getWorkflowResult(item.id).then(setResult).catch(() => {});
                  }}
                  className="relative group rounded-xl overflow-hidden border border-gray-100 bg-gray-50 hover:border-gray-300 transition-colors cursor-pointer aspect-square"
                  title={`${item.story_type} · ${item.scene}`}
                >
                  <img
                    src={resolveWorkflowImageUrl(item.image_urls[0])}
                    alt={item.scene}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                  <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <p className="text-[9px] text-white font-bold truncate">{item.story_type} · {item.scene}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="min-h-0">
          {(running || isFailed) && !result && (
            <div className={`min-h-[190px] rounded-3xl p-6 flex flex-col justify-center text-center border ${
              isFailed ? "bg-red-50/60 border-red-100" : "bg-blue-50/60 border-blue-100"
            }`}>
              <div className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-5 shadow-sm ${
                isFailed ? "bg-white text-red-500" : "bg-blue-100 text-blue-600"
              }`}>
                {isFailed ? (
                  <AlertTriangle className="w-6 h-6" />
                ) : (
                  <RefreshCw className="w-6 h-6 animate-spin" />
                )}
              </div>
              <h3 className={`text-lg font-bold mb-2 ${isFailed ? "text-red-700" : "text-gray-900"}`}>
                {isFailed ? "生成失败" : currentStepLabel}
              </h3>
              <p className={`text-sm leading-relaxed ${isFailed ? "text-red-500" : "text-gray-500"}`}>
                {isFailed ? (failedEvent?.message || status?.error_message || "流水线执行失败") : "系统正在处理当前任务，请稍候。"}
              </p>
            </div>
          )}

          {/* ── Idle ── */}
          {!running && !isFailed && !result && (
            <div className="min-h-[190px] bg-gray-50 rounded-3xl p-6 flex flex-col justify-center text-center border border-gray-100">
              <div className="w-12 h-12 rounded-full bg-white border border-gray-100 flex items-center justify-center mx-auto mb-4 shadow-sm">
                <Film className="w-6 h-6 text-gray-500" />
              </div>
              <h3 className="text-lg font-bold text-gray-800 mb-2">导演台处于空闲状态</h3>
              <p className="text-sm leading-relaxed text-gray-500">
                配置剧情类型与产品图后，系统会自动跑完剧情、四宫格生图、评分、文案和最终视频提示词。
              </p>
            </div>
          )}

          {/* ── Needs review card (score gate triggered) ── */}
          {!running && result && result.status === "needs_review" && (
            <div className="bg-amber-50 border border-amber-200 rounded-3xl p-6 text-center">
              <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center mx-auto mb-4">
                <AlertTriangle className="w-6 h-6 text-amber-600" />
              </div>
              <h3 className="text-lg font-bold text-amber-800 mb-2">评分闸门触发</h3>
              <p className="text-sm text-amber-700 mb-5">
                {result.error_message || "图片评分较低，请选择继续或重新生成。"}
              </p>
              <div className="flex justify-center gap-3">
                <button
                  onClick={handleReviewContinue}
                  disabled={reviewBusy}
                  className="rounded-xl bg-black px-5 py-3 text-sm font-bold text-white hover:bg-gray-900 transition-colors cursor-pointer disabled:opacity-50"
                >
                  {reviewBusy ? "执行中..." : "继续使用当前图片"}
                </button>
                <button
                  onClick={handleReviewRegenerate}
                  disabled={reviewBusy}
                  className="rounded-xl border border-amber-300 bg-white px-5 py-3 text-sm font-bold text-amber-800 hover:bg-amber-100 transition-colors cursor-pointer disabled:opacity-50"
                >
                  {reviewBusy ? "生成中..." : "重新生成图片"}
                </button>
              </div>
            </div>
          )}

          {/* ── Log overlay — absolutely positioned, doesn't push content ── */}
          {diagnosticsOpen && (
            <div className="absolute right-4 top-16 bottom-4 left-4 z-30 flex flex-col bg-white/98 backdrop-blur rounded-2xl border border-gray-200 shadow-2xl overflow-hidden">
              {/* Header */}
              <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100 shrink-0">
                <AlertTriangle className={`h-3.5 w-3.5 ${failedEvent ? "text-red-500" : "text-gray-300"}`} />
                <span className="text-xs font-bold text-gray-500">开发者日志</span>
                {events.length > 0 && (
                  <span className="rounded bg-gray-100 px-1.5 py-px text-[10px] font-bold text-gray-400">{events.length}</span>
                )}
                {failedEvent && (
                  <span className="rounded bg-red-50 px-1.5 py-px text-[10px] font-bold text-red-500">失败</span>
                )}
                <button
                  onClick={() => handleCopy(diagnosticText, "diagnostic")}
                  className="ml-auto text-[10px] text-gray-400 hover:text-gray-600"
                >
                  {copied === "diagnostic" ? "已复制" : "复制"}
                </button>
                <button
                  onClick={() => setDiagnosticsOpen(false)}
                  className="text-gray-400 hover:text-gray-600"
                  type="button"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>

              {/* Error banner */}
              {failedEvent && (
                <div className="mx-4 mt-3 rounded-lg border border-red-100 bg-red-50/80 px-3 py-2 shrink-0">
                  <p className="text-xs font-bold text-red-700">第 {failedEvent.step_index} 步失败 · {failedEvent.step_name}</p>
                  <p className="text-[11px] text-red-600 mt-0.5 leading-relaxed">{failedEvent.message}</p>
                </div>
              )}

              {/* Log list — light theme */}
              <div className="flex-1 overflow-y-auto px-4 py-3">
                {logRows.length > 0 ? (
                  <div className="space-y-1.5">
                    {logRows.map((row) => (
                      <div
                        key={row.id}
                        className={`rounded-lg px-3 py-2 text-[11px] leading-relaxed ${
                          row.tone === "error"
                            ? "bg-red-50/70 border border-red-100"
                            : "bg-gray-50 border border-gray-100"
                        }`}
                      >
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="font-mono text-gray-400">{row.time}</span>
                          <span className="text-gray-300">·</span>
                          <span className="text-gray-500">{row.meta}</span>
                        </div>
                        <div className={`whitespace-pre-wrap break-words ${
                          row.tone === "error" ? "text-red-700" : "text-gray-700"
                        }`}>
                          {row.text}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="h-full flex items-center justify-center text-xs text-gray-300">
                    日志加载中...
                  </div>
                )}
              </div>
            </div>
          )}

          {result && (
            <div className="space-y-5 max-h-[560px] overflow-y-auto pr-1">
              {/* ── Toolbar: copy all + download all ── */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleCopy([
                    `生图提示词:`, result.image_prompts?.[0] || "(无)", ``,
                    `剧情分镜原文:`, result.storyboard_text || "(无)", ``,
                    `口播文案:`, result.copy_text || "(无)", ``,
                    `最终视频提示词:`, result.video_prompt || "(无)",
                  ].join("\n"), "all")}
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-xl border border-gray-200 bg-white py-2 text-xs font-bold text-gray-700 hover:border-gray-300 hover:text-black cursor-pointer"
                >
                  {copied === "all" ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied === "all" ? "已复制" : "复制全部提示词"}</span>
                </button>
                <button
                  onClick={handleDownloadAll}
                  className="flex items-center justify-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3 py-2 text-xs font-bold text-gray-700 hover:border-gray-300 hover:text-black cursor-pointer"
                >
                  {copied === "download" ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Download className="w-3.5 h-3.5" />}
                  <span>{copied === "download" ? "已下载" : "下载 .txt"}</span>
                </button>
              </div>

              {/* ── Final video prompt ── */}
              <div className="bg-gray-50 border border-gray-100 rounded-2xl p-5">
                <div className="flex items-center mb-3">
                  <span className="text-xs font-bold text-gray-500 tracking-wider">最终视频提示词 (Step 6)</span>
                  <button onClick={() => handleCopy(result.video_prompt, "video_prompt")} className="ml-auto bg-black text-white rounded-lg px-3 py-1.5 text-xs font-bold hover:bg-gray-900 flex items-center space-x-1 cursor-pointer">
                    {copied === "video_prompt" ? <Check className="w-3.5 h-3.5" /> : <Clipboard className="w-3.5 h-3.5" />}
                    <span>{copied === "video_prompt" ? "已复制" : "复制"}</span>
                  </button>
                </div>
                <pre className="text-xs text-gray-700 whitespace-pre-wrap bg-white border border-gray-100 rounded-xl p-4 max-h-52 overflow-y-auto leading-relaxed">{result.video_prompt}</pre>
              </div>

              {(result.video_url || result.video_status || result.video_error || result.video_job_id) && (
                <div className="bg-white border border-gray-100 rounded-2xl p-5">
                  <div className="flex items-center mb-3">
                    <span className="text-xs font-bold text-gray-500 tracking-wider">视频生成 (Step 7)</span>
                    <div className="ml-auto flex items-center gap-2">
                      {result.video_status && (
                        <span className="rounded-full bg-gray-100 px-2.5 py-1 text-[10px] font-bold text-gray-600">
                          {VIDEO_STATUS_LABELS[result.video_status] || result.video_status}
                        </span>
                      )}
                      {workflowId && (
                        <button
                          onClick={handleVideoRefresh}
                          disabled={videoRefreshing}
                          className="rounded-full bg-gray-50 border border-gray-100 px-2.5 py-1 text-[10px] font-bold text-gray-500 hover:text-black hover:border-gray-200 transition-colors cursor-pointer disabled:opacity-50"
                        >
                          {videoRefreshing ? "刷新中..." : "刷新状态"}
                        </button>
                      )}
                    </div>
                  </div>
                  {result.video_url ? (
                    <video
                      src={resolveWorkflowImageUrl(result.video_url)}
                      controls
                      className="w-full rounded-xl border border-gray-100 bg-black"
                    />
                  ) : (
                    <>
                      <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50 p-4 text-center">
                        <Film className="mx-auto mb-2 h-5 w-5 text-gray-400" />
                        <p className="text-xs font-bold text-gray-700">
                          {result.video_error || "视频任务已记录，等待生成结果。"}
                        </p>
                      </div>
                      {workflowId && (
                        <div className="mt-3 flex gap-2">
                          <input
                            value={videoUrlInput}
                            onChange={(e) => setVideoUrlInput(e.target.value)}
                            placeholder="粘贴视频地址..."
                            className="flex-1 px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs text-gray-700 outline-none focus:ring-2 focus:ring-black/10"
                          />
                          <button
                            onClick={handleVideoBackfill}
                            disabled={videoSaving || !videoUrlInput.trim()}
                            className="shrink-0 rounded-xl bg-black px-4 py-2 text-xs font-bold text-white hover:bg-gray-900 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                          >
                            {videoSaving ? "保存中..." : "保存"}
                          </button>
                        </div>
                      )}
                    </>
                  )}
                  {result.video_job_id && (
                    <p className="mt-2 text-[11px] text-gray-400">任务 ID：{result.video_job_id}</p>
                  )}
                  {result.video_url && result.video_error && (
                    <p className="mt-2 text-xs text-gray-500">{result.video_error}</p>
                  )}
                </div>
              )}

              {/* ── Hashtags (Step 8) ── */}
              {result.hashtags && (
                <div className="bg-white border border-gray-100 rounded-2xl p-5">
                  <div className="flex items-center mb-3">
                    <span className="text-xs font-bold text-gray-500 tracking-wider">发布标签 (Step 8)</span>
                    <span className="ml-auto rounded-full bg-indigo-50 px-2.5 py-1 text-[10px] font-bold text-indigo-600">
                      {result.hashtags.platform} · {result.hashtags.tag_count} 标签
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5 mb-3">
                    {result.hashtags.tags_list.map((tag: string, i: number) => (
                      <span
                        key={i}
                        className="inline-flex items-center gap-1 rounded-lg bg-indigo-50 px-2.5 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100 transition-colors cursor-pointer"
                        onClick={() => { navigator.clipboard.writeText(tag); }}
                        title="点击复制"
                      >
                        <Hash className="w-3 h-3" />
                        {tag}
                      </span>
                    ))}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(result.hashtags!.tags_string);
                      }}
                      className="flex items-center gap-1 rounded-lg bg-gray-100 px-3 py-1.5 text-[11px] font-bold text-gray-600 hover:bg-gray-200 transition-colors cursor-pointer"
                    >
                      <Copy className="w-3 h-3" />
                      一键复制全部
                    </button>
                    <span className="text-[10px] text-gray-400">
                      语言: {result.hashtags.detected_language} · {result.hashtags.generated_at}
                    </span>
                  </div>
                </div>
              )}

              {/* ── Generated image ── */}
              <div className="relative group overflow-hidden rounded-3xl shadow-md border border-gray-100 bg-white">
                {result.image_urls?.[0] ? (
                  <img src={resolveWorkflowImageUrl(result.image_urls[0])} alt="四宫格图片" className="w-full aspect-square object-cover transition-transform duration-500 group-hover:scale-102" />
                ) : (
                  <div className="w-full aspect-square bg-gray-100 flex flex-col items-center justify-center text-gray-400">
                    <RefreshCw className="w-6 h-6 opacity-30 mb-2" />
                    <span className="text-xs">图片生成失败</span>
                  </div>
                )}
                <button
                  onClick={handleDownloadImage}
                  className="absolute top-3 right-3 bg-black/50 text-white rounded-lg px-2 py-1.5 text-[10px] font-bold hover:bg-black/70 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer flex items-center gap-1"
                  title="下载图片"
                >
                  <Download className="w-3 h-3" /> 下载
                </button>
                <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/80 to-transparent p-5 text-white">
                  <span className="text-[10px] uppercase tracking-widest text-gray-300">四宫格镜头</span>
                  <h4 className="text-xl font-bold tracking-tight">{result.story_type} · {result.scene}</h4>
                </div>
              </div>

              {/* ── Keyframes grid ── */}
              <div className="grid grid-cols-2 gap-2">
                {result.keyframes?.map((kf: KeyframeData, i: number) => {
                  const positions = ["左上", "右上", "左下", "右下"];
                  return (
                    <div key={i} className="bg-gray-50 rounded-2xl p-3 border border-gray-100">
                      <p className="text-[10px] font-bold text-gray-900 mb-1">{positions[i]} · 镜头{i + 1}</p>
                      <p className="text-[11px] text-gray-600 leading-relaxed line-clamp-3" title={kf.description}>{kf.description?.slice(0, 68)}</p>
                    </div>
                  );
                })}
              </div>

              {/* ── Score ── */}
              {result.scores?.[0] && (
                <div className="bg-white border border-gray-100 rounded-2xl p-5">
                  <div className="flex items-center mb-3">
                    <span className="text-xs font-bold text-gray-500 tracking-wider">评分结果</span>
                    <span className={`ml-auto text-xs px-2.5 py-1 rounded-full border font-bold ${SCORE_COLORS[result.scores[0].score] || ""}`}>{result.scores[0].score}</span>
                  </div>
                  <p className="text-xs text-gray-600 leading-relaxed">{result.scores[0].reason}</p>
                </div>
              )}

              {/* ── Image prompt (Step 2 keyframe prompt) ── */}
              <div className="bg-white border border-gray-100 rounded-2xl p-5">
                <div className="flex items-center mb-3">
                  <span className="text-xs font-bold text-gray-500 tracking-wider">生图提示词 (Step 2)</span>
                  <button onClick={() => handleCopy(result.image_prompts?.[0] || "", "img_prompt")} className="ml-auto text-xs text-gray-400 hover:text-black flex items-center space-x-1 cursor-pointer">
                    {copied === "img_prompt" ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copied === "img_prompt" ? "已复制" : "复制"}</span>
                  </button>
                </div>
                <pre className="text-xs text-gray-600 whitespace-pre-wrap bg-gray-50 border border-gray-100 rounded-xl p-3 max-h-44 overflow-y-auto leading-relaxed">{result.image_prompts?.[0] || "(未生成)"}</pre>
              </div>

              {/* ── Copy text ── */}
              <div className="bg-white border border-gray-100 rounded-2xl p-5">
                <div className="flex items-center mb-3">
                  <span className="text-xs font-bold text-gray-500 tracking-wider">口播文案 (Step 5)</span>
                  <button onClick={() => handleCopy(result.copy_text, "copy")} className="ml-auto text-xs text-gray-400 hover:text-black flex items-center space-x-1 cursor-pointer">
                    {copied === "copy" ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copied === "copy" ? "已复制" : "复制"}</span>
                  </button>
                </div>
                <p className="text-sm text-gray-700 leading-relaxed">{result.copy_text}</p>
              </div>

              {/* ── Storyboard text ── */}
              <div className="bg-white border border-gray-100 rounded-2xl p-5">
                <div className="flex items-center mb-3">
                  <span className="text-xs font-bold text-gray-500 tracking-wider">剧情分镜原文 (Step 1)</span>
                  <button onClick={() => handleCopy(result.storyboard_text, "storyboard")} className="ml-auto text-xs text-gray-400 hover:text-black flex items-center space-x-1 cursor-pointer">
                    {copied === "storyboard" ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copied === "storyboard" ? "已复制" : "复制"}</span>
                  </button>
                </div>
                <pre className="text-xs text-gray-600 whitespace-pre-wrap max-h-44 overflow-y-auto leading-relaxed">{result.storyboard_text}</pre>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
