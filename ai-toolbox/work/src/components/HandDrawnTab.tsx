/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  User,
  PlusCircle,
  Sparkles,
  Clipboard,
  Check,
  Eye,
  Layers,
  Palette,
  ArrowRight,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Download,
  StopCircle,
  Trash2,
  History,
  Search,
  X,
  Sun,
  Activity,
} from "lucide-react";
import { CreativeFactors, PipelineData, PipelineStatus, PromptConfig, PromptHistoryItem, PromptStatus } from "../types";
import {
  deconstructLocalVisual,
  generateLocalImage,
  generateLocalPrompt,
  getPromptConfig,
  getPromptHistory,
  deletePromptHistory,
  deletePromptHistoryBatch,
  markPromptCopied,
  stopPromptGeneration,
} from "../api/services";

// Standard preset tags data
const PRESETS = {
  gufeng: {
    name: "精酿麦浪风",
    icon: "🌾",
    factors: {
      subject: "一杯金黄澄澈的精酿原浆啤酒，顶部堆叠着慕斯般细腻绵密的雪白泡沫，气泡微弱上升",
      scene: "落日余晖下的金黄大麦田，微风拂面，几颗沉甸甸的大麦穗随意散落在原木酒桶旁",
      lighting: "温暖治愈的逆光，夕阳金光穿透剔透的酒杯，呈现出琥珀般温暖而尊贵的色调",
      style: "商业静物摄影，极简德式高级美学，微距景深，温润饱满",
      posture: "精致扎马克杯外壁凝结着晶莹饱满的水珠，其中一颗正缓缓滑落，折射出夕阳暖光",
      helper: "高光质感，冷热对比，通透感，极高精细度，大片视感"
    }
  },
  space: {
    name: "冰爽夏日派对",
    icon: "🧊",
    factors: {
      subject: "冰镇小麦白啤与切开的清爽青柠檬，在晶莹剔透的冰块堆中半遮半掩，冷雾袅袅",
      scene: "夏日傍晚的海滩露天派对酒吧，背景有模糊的落日余影、椰树摇曳与炫彩霓虹",
      lighting: "海滩晚霞冷暖色调交织，清爽的淡蓝色霓虹环境光投射在冰块与玻璃杯上",
      style: "青春动感纪实摄影，日系清凉，高对比胶片感，色彩饱满活泼",
      posture: "手持酒杯在半空中轻轻碰撞，雪白的泡沫微微溢出杯口，充满夏日欢聚的张力",
      helper: "解暑清爽感，微醺氛围，空气感，清凉质感，夏日大片"
    }
  },
  summer: {
    name: "赛博蒸汽精酿",
    icon: "⚡",
    factors: {
      subject: "一款印有极具未来感潮流液态金属标签的罐装黑啤，泛着深邃浓郁的巧克力与烘焙麦芽色泽",
      scene: "赛博朋克风的雨后深夜都市街头，彩色霓虹灯牌在潮湿的水洼中倒影折射，科技感与市井烟火并存",
      lighting: "迷幻冷艳的紫红与魅惑深蓝霓虹双色侧打光，高对比度，边缘反射冷冽冷光",
      style: "科幻未来主义视觉，3D 概念艺术，现代工业机械美学",
      posture: "金属磨砂罐身折射着流光，一束干冰雾气从刚刚拉开的拉环处喷薄而出，动感定格",
      helper: "潮流酷炫，高级哑光材质，虚幻引擎5渲染，光线追踪，硬核科幻"
    }
  }
};

interface HandDrawnTabProps {
  factors: CreativeFactors;
  setFactors: React.Dispatch<React.SetStateAction<CreativeFactors>>;
  pipeline: PipelineData;
  setPipeline: React.Dispatch<React.SetStateAction<PipelineData>>;
  onExport: (title: string, creativeText: string) => void;
  isActive: boolean;
  onBusyChange: (busy: boolean) => void;
}

export default function HandDrawnTab({
  factors,
  setFactors,
  pipeline,
  setPipeline,
  onExport,
  isActive,
  onBusyChange
}: HandDrawnTabProps) {
  const [status, setStatus] = useState<PipelineStatus>("idle");

  // Report busy state to parent so nav can warn before switching
  useEffect(() => {
    const isBusy = status === "generating_prompt" || status === "generating_image" || status === "deconstructing_visual";
    onBusyChange(isBusy);
  }, [status, onBusyChange]);
  const [errorMessage, setErrorMessage] = useState("");
  const [copiedText, setCopiedText] = useState<string | null>(null);
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [aspectRatio, setAspectRatio] = useState("1:1");
  const [styleQuality, setStyleQuality] = useState("写实");

  // Advanced parameters
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [promptConfig, setPromptConfig] = useState<PromptConfig | null>(null);
  const [advModel, setAdvModel] = useState("deepseek4");
  const [advAudience, setAdvAudience] = useState("默认随机(按画像比例55/15/30)");
  const [advScene, setAdvScene] = useState("随机");
  const [advWeather, setAdvWeather] = useState("随机");
  const [advStyle, setAdvStyle] = useState("随机");
  const [advAction, setAdvAction] = useState("随机");
  const [advMinProduct, setAdvMinProduct] = useState(1);
  const [advMaxProduct, setAdvMaxProduct] = useState(3);
  const [advBatch, setAdvBatch] = useState(1);
  const [advTolerance, setAdvTolerance] = useState(65);
  const [advExtra, setAdvExtra] = useState("");

  // Prompt running status
  const [promptRunning, setPromptRunning] = useState(false);
  const [promptStatusMsg, setPromptStatusMsg] = useState("");

  // History panel
  const [showHistory, setShowHistory] = useState(false);
  const [historyItems, setHistoryItems] = useState<PromptHistoryItem[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyPage, setHistoryPage] = useState(1);
  const [historySort, setHistorySort] = useState("latest");
  const [historySearch, setHistorySearch] = useState("");
  const [historySelected, setHistorySelected] = useState<Set<number>>(new Set());

  // Load prompt config on mount
  useEffect(() => {
    getPromptConfig().then(setPromptConfig).catch(() => {});
  }, []);

  // Multi-image batch results
  const [batchImages, setBatchImages] = useState<Array<{ prompt: string; imageUrl: string; title: string }>>([]);

  const applyPreset = (key: keyof typeof PRESETS) => {
    setFactors(PRESETS[key].factors);
    setActivePreset(key);
    // Pulse animation
  };

  const handleInputChange = (field: keyof CreativeFactors, value: string) => {
    setFactors((prev) => ({ ...prev, [field]: value }));
    setActivePreset(null);
  };

  // History helpers
  const loadHistory = async (page = 1, sort = historySort, search = historySearch) => {
    try {
      const data = await getPromptHistory({ page, page_size: 20, sort, search });
      setHistoryItems(data.items);
      setHistoryTotal(data.total);
      setHistoryPage(page);
      setHistorySort(sort);
    } catch {}
  };

  const toggleHistorySelect = (id: number) => {
    const next = new Set(historySelected);
    if (next.has(id)) next.delete(id); else next.add(id);
    setHistorySelected(next);
  };

  const handleCopyHistory = async (item: PromptHistoryItem) => {
    try {
      await navigator.clipboard.writeText(item.prompt);
      await markPromptCopied(item.id);
      loadHistory(historyPage);
    } catch {}
  };

  const handleDeleteHistory = async (id: number) => {
    try {
      await deletePromptHistory(id);
      loadHistory(historyPage);
    } catch {}
  };

  const handleBatchDelete = async () => {
    if (historySelected.size === 0) return;
    try {
      await deletePromptHistoryBatch(Array.from(historySelected));
      setHistorySelected(new Set());
      loadHistory(1);
    } catch {}
  };

  const runPipeline = async () => {
    if (!factors.subject && !factors.scene && !factors.style) {
      setStatus("failed");
      setErrorMessage("请至少填写主体、场景或风格中的一项，或选择上方预设因子！");
      return;
    }

    try {
      setErrorMessage("");

      // Step 1: Generate prompts via single-prompt endpoint
      setStatus("generating_prompt");
      const count = Math.max(1, advBatch);
      const prompts: Array<{ prompt: string; title: string }> = [];
      for (let i = 0; i < count; i++) {
        setPromptStatusMsg(`正在生成第 ${i + 1}/${count} 个提示词...`);
        const promptData = await generateLocalPrompt({
          ...factors,
          aspectRatio,
          styleQuality,
          model: advModel,
          audience: advAudience,
          scene: advScene,
          weather: advWeather,
          style: advStyle,
          action: advAction,
          minProduct: advMinProduct,
          maxProduct: advMaxProduct,
          tolerance: advTolerance,
          extra: advExtra,
        });
        prompts.push({ prompt: promptData.englishPrompt, title: promptData.title });
      }

      const primaryPrompt = prompts[0].prompt;
      const primaryTitle = prompts[0].title;
      setPipeline((prev) => ({ ...prev, factors: { ...factors }, promptResult: { title: primaryTitle, englishPrompt: primaryPrompt, chinesePrompt: primaryPrompt } }));

      // Step 2: Generate images for all prompts
      setStatus("generating_image");
      const images: Array<{ prompt: string; imageUrl: string; title: string }> = [];
      for (let i = 0; i < prompts.length; i++) {
        setPromptStatusMsg(`正在生成第 ${i + 1}/${prompts.length} 张图片...`);
        try {
          const imgData = await generateLocalImage({ prompt: prompts[i].prompt, aspectRatio });
          images.push({ prompt: prompts[i].prompt, imageUrl: imgData.imageUrl, title: prompts[i].title });
        } catch {
          images.push({ prompt: prompts[i].prompt, imageUrl: "", title: `${prompts[i].title} (生成失败)` });
        }
      }
      setBatchImages(images);
      const primaryImage = images[0]?.imageUrl || "";
      setPipeline((prev) => ({ ...prev, imageUrl: primaryImage, isFallback: false }));

      // Step 3: Deconstruct primary image
      setStatus("deconstructing_visual");
      const deconstructData = primaryImage ? await deconstructLocalVisual({
        prompt: primaryPrompt,
        title: primaryTitle,
        imageUrl: primaryImage,
      }) : null;
      if (deconstructData) {
        setPipeline((prev) => ({ ...prev, deconstructed: deconstructData }));
      }

      setStatus("completed");
      setPromptStatusMsg("");
      setPromptRunning(false);
    } catch (error: any) {
      console.error(error);
      setStatus("failed");
      setPromptRunning(false);
      setErrorMessage(error.message || "流水线执行过程中发生错误");
    }
  };

  const handleStop = async () => {
    try {
      await stopPromptGeneration();
      setPromptRunning(false);
      setPromptStatusMsg("已停止");
    } catch {}
  };

  const handleClearResults = () => {
    setPipeline({
      factors: { ...factors },
      promptResult: null,
      imageUrl: null,
      deconstructed: null,
      isFallback: false,
    });
    setBatchImages([]);
    setStatus("idle");
    setErrorMessage("");
    setPromptStatusMsg("");
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(label);
    setTimeout(() => setCopiedText(null), 2000);
  };

  const downloadImage = async (url: string, filename: string) => {
    try {
      const r = await fetch(url);
      const blob = await r.blob();
      const objUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objUrl;
      a.download = filename || "image.png";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(objUrl);
    } catch {
      window.open(url, "_blank");
    }
  };

  const triggerExport = () => {
    if (!pipeline.promptResult) return;
    const summary = `主题: ${factors.subject}, 场景: ${factors.scene}, 风格: ${factors.style}, 提示词: ${pipeline.promptResult.chinesePrompt}`;
    onExport(pipeline.promptResult.title, summary);
  };

  // Check if step is active or completed based on pipeline status
  const getStepStatusClass = (step: 1 | 2 | 3) => {
    if (status === "completed") return "completed";
    
    if (step === 1) {
      if (status === "generating_prompt") return "active";
      if (status === "generating_image" || status === "deconstructing_visual") return "completed";
    } else if (step === 2) {
      if (status === "generating_image") return "active";
      if (status === "deconstructing_visual") return "completed";
    } else if (step === 3) {
      if (status === "deconstructing_visual") return "active";
    }
    
    return "inactive";
  };

  return (
    <div className="flex w-full min-h-[600px] flex-col md:flex-row" id="hand-drawn-container">
      {/* Left Column - Creative Matrix */}
      <section className="w-full md:w-[55%] p-6 md:p-12 border-b md:border-b-0 md:border-r border-gray-100 flex flex-col justify-between" id="creative-matrix-section">
        <div>
          <div className="flex items-center space-x-3 mb-8">
            <div className="grid grid-cols-2 gap-1 w-5 h-5 text-gray-500">
              <div className="border-2 border-current rounded-[3px]"></div>
              <div className="border-2 border-current rounded-[3px]"></div>
              <div className="border-2 border-current rounded-[3px]"></div>
              <div className="border-2 border-current rounded-[3px]"></div>
            </div>
            <h2 className="text-xl md:text-2xl font-bold text-gray-900 font-sans tracking-tight">创意因子矩阵</h2>
          </div>

          {/* Presets Selection */}
          <div className="flex flex-wrap gap-2.5 mb-8" id="quick-presets-container">
            {Object.entries(PRESETS).map(([key, data]) => (
              <button
                key={key}
                onClick={() => applyPreset(key as keyof typeof PRESETS)}
                id={`preset-btn-${key}`}
                className={`transition-all duration-300 px-5 py-2.5 rounded-full flex items-center space-x-2 text-sm font-medium border cursor-pointer hover:scale-102 active:scale-98 ${
                  activePreset === key
                    ? "bg-black text-white border-black shadow-md"
                    : "bg-gray-50 text-gray-700 border-gray-100 hover:bg-gray-100"
                }`}
              >
                <span>{data.icon}</span>
                <span>{data.name}</span>
              </button>
            ))}
          </div>

          {/* Form Inputs — only Subject + Helper; rest via Advanced Params */}
          <div className="space-y-4 mb-6" id="matrix-inputs-container">
            {/* Subject */}
            <div className="relative" id="input-subject-group">
              <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none text-gray-400">
                <User className="w-5 h-5" />
              </div>
              <input
                type="text"
                value={factors.subject}
                onChange={(e) => handleInputChange("subject", e.target.value)}
                className="w-full pl-12 pr-4 py-4 bg-gray-50 border-0 rounded-xl focus:ring-2 focus:ring-black/10 focus:bg-white text-sm text-gray-800 placeholder-gray-400 outline-none transition-all"
                placeholder="宣传主体 (例如：精酿啤酒玻璃杯，顶部有细腻慕斯泡沫，杯壁挂着冰晶水珠)"
                id="input-subject"
              />
            </div>

            {/* Helper Optional */}
            <div className="relative" id="input-helper-group">
              <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none text-gray-400">
                <PlusCircle className="w-5 h-5" />
              </div>
              <input
                type="text"
                value={factors.helper}
                onChange={(e) => handleInputChange("helper", e.target.value)}
                className="w-full pl-12 pr-4 py-4 bg-gray-50 border-0 rounded-xl focus:ring-2 focus:ring-black/10 focus:bg-white text-sm italic text-gray-800 placeholder-gray-400 outline-none transition-all"
                placeholder="辅助指令 (可选) (例如：冷热对比，通透澄澈，极高精细度，大片视感)"
                id="input-helper"
              />
            </div>
          </div>

          {/* Advanced Parameters Toggle */}
          <div className="mt-4" id="advanced-params-section">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full flex items-center justify-between px-5 py-3.5 bg-gray-50 border border-gray-100 rounded-2xl hover:bg-gray-100 transition-colors cursor-pointer"
              id="toggle-advanced-btn"
            >
              <span className="text-sm font-bold text-gray-700 flex items-center space-x-2">
                <Sparkles className="w-4 h-4" />
                <span>高级参数</span>
                {promptRunning && <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />}
              </span>
              {showAdvanced ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
            </button>

            {showAdvanced && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                className="bg-gray-50/50 border border-gray-100 rounded-2xl p-5 mt-3 space-y-4 overflow-hidden"
                id="advanced-params-panel"
              >
                {/* Model + Audience row */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-gray-500 mb-1.5">模型</label>
                    <select
                      value={advModel}
                      onChange={(e) => setAdvModel(e.target.value)}
                      className="w-full px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm text-gray-700 outline-none focus:ring-2 focus:ring-black/10"
                    >
                      {promptConfig?.available_models ? (
                        Object.entries(promptConfig.available_models).map(([k, v]) => (
                          <option key={k} value={k}>{v}</option>
                        ))
                      ) : (
                        <option value="deepseek4">DeepSeek V4-Pro</option>
                      )}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-500 mb-1.5">目标人群</label>
                    <select
                      value={advAudience}
                      onChange={(e) => setAdvAudience(e.target.value)}
                      className="w-full px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm text-gray-700 outline-none focus:ring-2 focus:ring-black/10"
                    >
                      {(promptConfig?.audience_options || ["默认随机(按画像比例55/15/30)"]).map((o) => (
                        <option key={o} value={o}>{o}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Scene + Weather row */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-gray-500 mb-1.5">场景</label>
                    <select
                      value={advScene}
                      onChange={(e) => setAdvScene(e.target.value)}
                      className="w-full px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm text-gray-700 outline-none focus:ring-2 focus:ring-black/10"
                    >
                      <option value="随机">随机</option>
                      {(promptConfig?.scene_options || []).map((o) => (
                        <option key={o} value={o}>{o}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-500 mb-1.5">光线天气</label>
                    <select
                      value={advWeather}
                      onChange={(e) => setAdvWeather(e.target.value)}
                      className="w-full px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm text-gray-700 outline-none focus:ring-2 focus:ring-black/10"
                    >
                      <option value="随机">随机</option>
                      {(promptConfig?.weather_options || []).map((o) => (
                        <option key={o} value={o}>{o}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Style + Action row */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-gray-500 mb-1.5">风格</label>
                    <select
                      value={advStyle}
                      onChange={(e) => setAdvStyle(e.target.value)}
                      className="w-full px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm text-gray-700 outline-none focus:ring-2 focus:ring-black/10"
                    >
                      <option value="随机">随机</option>
                      {(promptConfig?.style_options || []).map((o) => (
                        <option key={o} value={o}>{o}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-500 mb-1.5">动作</label>
                    <select
                      value={advAction}
                      onChange={(e) => setAdvAction(e.target.value)}
                      className="w-full px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm text-gray-700 outline-none focus:ring-2 focus:ring-black/10"
                    >
                      <option value="随机">随机</option>
                      {(promptConfig?.action_options || []).map((o) => (
                        <option key={o} value={o}>{o}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Product range */}
                <div>
                  <label className="block text-xs font-bold text-gray-500 mb-1.5">产品数量范围</label>
                  <div className="flex items-center space-x-2">
                    <input
                      type="number"
                      min={1}
                      max={10}
                      value={advMinProduct}
                      onChange={(e) => setAdvMinProduct(Math.max(1, parseInt(e.target.value) || 1))}
                      className="w-20 px-3 py-2 bg-white border border-gray-200 rounded-xl text-sm text-center outline-none focus:ring-2 focus:ring-black/10"
                    />
                    <span className="text-gray-400 text-sm">–</span>
                    <input
                      type="number"
                      min={1}
                      max={10}
                      value={advMaxProduct}
                      onChange={(e) => setAdvMaxProduct(Math.max(advMinProduct, parseInt(e.target.value) || advMinProduct))}
                      className="w-20 px-3 py-2 bg-white border border-gray-200 rounded-xl text-sm text-center outline-none focus:ring-2 focus:ring-black/10"
                    />
                  </div>
                </div>

                {/* Generation count quick buttons */}
                <div>
                  <label className="block text-xs font-bold text-gray-500 mb-1.5">生成数量（每次生成几张图）</label>
                  <div className="flex flex-wrap gap-2">
                    {[1, 2, 3, 5, 10, 20].map((n) => (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setAdvBatch(n)}
                        className={`px-4 py-2 rounded-xl text-sm font-medium transition-all cursor-pointer ${
                          advBatch === n
                            ? "bg-black text-white shadow-sm"
                            : "bg-white text-gray-600 border border-gray-200 hover:bg-gray-50"
                        }`}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Tolerance slider */}
                <div>
                  <label className="block text-xs font-bold text-gray-500 mb-1.5">
                    相似度容忍：<span className="text-black font-bold">{advTolerance}%</span>
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={advTolerance}
                    onChange={(e) => setAdvTolerance(parseInt(e.target.value))}
                    className="w-full accent-black"
                  />
                </div>

                {/* Extra requirements */}
                <div>
                  <label className="block text-xs font-bold text-gray-500 mb-1.5">附加要求</label>
                  <textarea
                    value={advExtra}
                    onChange={(e) => setAdvExtra(e.target.value)}
                    rows={2}
                    className="w-full px-4 py-2.5 bg-white border border-gray-200 rounded-xl text-sm text-gray-700 outline-none focus:ring-2 focus:ring-black/10 resize-none placeholder-gray-400"
                    placeholder="例如：高光质感、通透感、极高精细度..."
                  />
                </div>
              </motion.div>
            )}
          </div>

          {/* Canvas Ratio & Style selection */}
          <div className="bg-gray-50/70 border border-gray-100 rounded-2xl p-5 space-y-4 my-4" id="image-config-panel">
            {/* Canvas Ratio Row */}
            <div className="flex items-center space-x-4" id="canvas-ratio-row">
              <span className="text-sm font-bold text-gray-700 min-w-[5rem]">画布比例：</span>
              <div className="flex flex-wrap gap-2.5" id="ratio-options">
                {["1:1", "16:9", "3:4"].map((ratio) => (
                  <button
                    key={ratio}
                    type="button"
                    onClick={() => setAspectRatio(ratio)}
                    className={`px-5 py-2 rounded-full text-sm font-medium transition-all cursor-pointer ${
                      aspectRatio === ratio
                        ? "bg-black text-white shadow-sm"
                        : "bg-white text-gray-700 border border-gray-200 hover:bg-gray-50 hover:border-gray-300"
                    }`}
                  >
                    {ratio}
                  </button>
                ))}
              </div>
            </div>

            {/* Quality/Style Row */}
            <div className="flex items-center space-x-4" id="style-quality-row">
              <span className="text-sm font-bold text-gray-700 min-w-[5rem]">渲染画质：</span>
              <div className="flex flex-wrap gap-2.5" id="style-options">
                {["写实", "二次元", "赛博", "水彩"].map((styleOpt) => (
                  <button
                    key={styleOpt}
                    type="button"
                    onClick={() => setStyleQuality(styleOpt)}
                    className={`px-5 py-2 rounded-full text-sm font-medium transition-all cursor-pointer ${
                      styleQuality === styleOpt
                        ? "bg-black text-white shadow-sm"
                        : "bg-white text-gray-700 border border-gray-200 hover:bg-gray-50 hover:border-gray-300"
                    }`}
                  >
                    {styleOpt}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* CTA Trigger Button with drawing icon */}
        <div id="cta-button-container">
          {status === "failed" && errorMessage && (
            <div className="mb-4 text-xs font-medium text-red-500 bg-red-50 p-3 rounded-lg border border-red-100 flex items-center space-x-2" id="error-alert">
              <span>⚠️</span>
              <span>{errorMessage}</span>
            </div>
          )}

          {promptStatusMsg && promptRunning && (
            <div className="mb-3 text-xs font-medium text-blue-600 bg-blue-50 p-2.5 rounded-lg border border-blue-100 flex items-center space-x-2" id="prompt-status-bar">
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              <span>{promptStatusMsg}</span>
            </div>
          )}

          <div className="flex space-x-2" id="action-buttons-row">
            <button
              onClick={runPipeline}
              disabled={status !== "idle" && status !== "completed" && status !== "failed"}
              id="run-pipeline-btn"
              className={`flex-1 text-white py-5 rounded-[2rem] flex items-center justify-center space-x-3 text-lg font-bold transition-all transform active:scale-95 shadow-lg select-none cursor-pointer ${
                status !== "idle" && status !== "completed" && status !== "failed"
                  ? "bg-gray-400 cursor-not-allowed"
                  : "bg-black hover:bg-gray-800 hover:scale-[0.99]"
              }`}
            >
              {status !== "idle" && status !== "completed" && status !== "failed" ? (
                <>
                  <RefreshCw className="w-6 h-6 animate-spin" />
                  <span>本地生成中...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-6 h-6" />
                  <span>一键全链条智绘</span>
                </>
              )}
            </button>

            {promptRunning && (
              <button
                onClick={handleStop}
                className="px-5 py-5 rounded-[2rem] bg-red-500 hover:bg-red-600 text-white flex items-center justify-center space-x-2 text-sm font-bold transition-all shadow-md cursor-pointer"
                id="stop-btn"
              >
                <StopCircle className="w-5 h-5" />
                <span>停止</span>
              </button>
            )}
          </div>

          {(status === "completed" || status === "failed" || pipeline.promptResult) && (
            <button
              onClick={handleClearResults}
              className="w-full mt-2 py-3 rounded-2xl bg-gray-50 hover:bg-gray-100 border border-gray-200 text-gray-500 flex items-center justify-center space-x-2 text-xs font-semibold transition-all cursor-pointer"
              id="clear-results-btn"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>清空结果</span>
            </button>
          )}
        </div>
      </section>

      {/* Right Column - Pipeline Monitor */}
      <section className="w-full md:w-[45%] p-6 md:p-12 flex flex-col justify-between" id="pipeline-monitor-section">
        <div className="w-full">
          <div className="flex items-center justify-between mb-8">
            <h2 className="text-xl md:text-2xl font-bold text-gray-900">
              {showHistory ? "提示词历史" : "流水线监视器"}
            </h2>
            <button
              onClick={() => { setShowHistory(!showHistory); if (!showHistory) loadHistory(); }}
              className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center space-x-1.5 transition-all cursor-pointer ${
                showHistory ? "bg-black text-white" : "bg-gray-50 text-gray-500 hover:bg-gray-100 border border-gray-200"
              }`}
              id="toggle-history-btn"
            >
              {showHistory ? <X className="w-3.5 h-3.5" /> : <History className="w-3.5 h-3.5" />}
              <span>{showHistory ? "关闭" : "历史"}</span>
            </button>
          </div>

          {/* History Panel */}
          {showHistory && (
            <div className="flex-1 flex flex-col" id="history-panel">
              {/* Search + Sort */}
              <div className="flex items-center space-x-2 mb-4">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
                  <input
                    type="text"
                    value={historySearch}
                    onChange={(e) => setHistorySearch(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") loadHistory(); }}
                    placeholder="搜索提示词..."
                    className="w-full pl-9 pr-3 py-2.5 bg-gray-50 border border-gray-100 rounded-xl text-xs outline-none focus:ring-2 focus:ring-black/10"
                  />
                  {historySearch && (
                    <button onClick={() => { setHistorySearch(""); loadHistory(1, historySort, ""); }} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
                <button
                  onClick={() => { setHistorySort("latest"); loadHistory(1, "latest", historySearch); }}
                  className={`px-3 py-2 rounded-lg text-xs font-medium transition-all cursor-pointer ${historySort === "latest" ? "bg-black text-white" : "bg-gray-50 text-gray-500 hover:bg-gray-100"}`}
                >
                  最新
                </button>
                <button
                  onClick={() => { setHistorySort("most_copied"); loadHistory(1, "most_copied", historySearch); }}
                  className={`px-3 py-2 rounded-lg text-xs font-medium transition-all cursor-pointer ${historySort === "most_copied" ? "bg-black text-white" : "bg-gray-50 text-gray-500 hover:bg-gray-100"}`}
                >
                  最多复制
                </button>
                {historySelected.size > 0 && (
                  <button
                    onClick={handleBatchDelete}
                    className="px-3 py-2 rounded-lg bg-red-50 text-red-600 hover:bg-red-100 text-xs font-medium transition-all cursor-pointer"
                  >
                    删除({historySelected.size})
                  </button>
                )}
              </div>

              {/* History list */}
              <div className="flex-1 overflow-y-auto max-h-[420px] space-y-2 pr-1" id="history-list">
                {historyItems.length === 0 && (
                  <div className="text-center py-12 text-gray-400 text-xs">暂无历史记录</div>
                )}
                {historyItems.map((item) => (
                  <div
                    key={item.id}
                    className={`bg-gray-50 border rounded-xl p-3.5 transition-all ${
                      historySelected.has(item.id) ? "border-black bg-gray-100" : "border-gray-100"
                    }`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div
                        className="flex-1 cursor-pointer"
                        onClick={() => toggleHistorySelect(item.id)}
                      >
                        <p className="text-xs text-gray-700 leading-relaxed line-clamp-3 font-mono select-all">
                          {item.prompt}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3 text-[10px] text-gray-400">
                        <span>复制: {item.copy_count || 0}</span>
                        {item.created_at && <span>{item.created_at}</span>}
                      </div>
                      <div className="flex items-center space-x-1.5">
                        <button
                          onClick={() => handleCopyHistory(item)}
                          className="px-2.5 py-1 rounded-lg bg-white border border-gray-200 text-gray-500 hover:text-black hover:border-gray-300 text-[10px] font-medium transition-all cursor-pointer"
                        >
                          复制
                        </button>
                        <button
                          onClick={() => handleDeleteHistory(item.id)}
                          className="px-2 py-1 rounded-lg text-red-400 hover:text-red-600 hover:bg-red-50 text-[10px] font-medium transition-all cursor-pointer"
                        >
                          删除
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Pagination */}
              {historyTotal > 20 && (
                <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
                  <button
                    onClick={() => historyPage > 1 && loadHistory(historyPage - 1)}
                    disabled={historyPage <= 1}
                    className="text-xs text-gray-500 hover:text-black disabled:text-gray-300 font-medium cursor-pointer"
                  >
                    ← 上一页
                  </button>
                  <span className="text-[10px] text-gray-400">{historyTotal} 条记录</span>
                  <button
                    onClick={() => historyPage * 20 < historyTotal && loadHistory(historyPage + 1)}
                    disabled={historyPage * 20 >= historyTotal}
                    className="text-xs text-gray-500 hover:text-black disabled:text-gray-300 font-medium cursor-pointer"
                  >
                    下一页 →
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Steps - hidden when history shown */}
          <div className={`space-y-6 md:space-y-8 mb-8 relative pl-3 ${showHistory ? 'hidden' : ''}`} id="steps-progress-bar">
            {/* The vertical connector line */}
            <div className="absolute left-[23px] top-3 bottom-3 w-[1.5px] bg-gray-100 z-0"></div>

            {/* Step 1 */}
            <div className="flex items-center space-x-6 relative z-10" id="progress-step-1">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center transition-all duration-300 ${
                  getStepStatusClass(1) === "completed"
                    ? "bg-blue-500 border-2 border-blue-200 text-white"
                    : getStepStatusClass(1) === "active"
                    ? "bg-blue-100 border-4 border-blue-400 animate-pulse"
                    : "bg-gray-100 border-2 border-transparent"
                }`}
              >
                {getStepStatusClass(1) === "completed" ? (
                  <Check className="w-3.5 h-3.5 stroke-[3px]" />
                ) : (
                  <div className={`w-2 h-2 rounded-full ${getStepStatusClass(1) === "active" ? "bg-blue-600" : "bg-gray-400"}`} />
                )}
              </div>
              <span
                className={`text-sm md:text-base font-semibold transition-colors duration-300 ${
                  getStepStatusClass(1) === "active"
                    ? "text-blue-600 font-bold"
                    : getStepStatusClass(1) === "completed"
                    ? "text-gray-800"
                    : "text-gray-400"
                }`}
              >
                步骤 1: 自动生成生图提示词
              </span>
            </div>

            {/* Step 2 */}
            <div className="flex items-center space-x-6 relative z-10" id="progress-step-2">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center transition-all duration-300 ${
                  getStepStatusClass(2) === "completed"
                    ? "bg-blue-500 border-2 border-blue-200 text-white"
                    : getStepStatusClass(2) === "active"
                    ? "bg-blue-100 border-4 border-blue-400 animate-pulse"
                    : "bg-gray-100 border-2 border-transparent"
                }`}
              >
                {getStepStatusClass(2) === "completed" ? (
                  <Check className="w-3.5 h-3.5 stroke-[3px]" />
                ) : (
                  <div className={`w-2 h-2 rounded-full ${getStepStatusClass(2) === "active" ? "bg-blue-600" : "bg-gray-400"}`} />
                )}
              </div>
              <span
                className={`text-sm md:text-base font-semibold transition-colors duration-300 ${
                  getStepStatusClass(2) === "active"
                    ? "text-blue-600 font-bold"
                    : getStepStatusClass(2) === "completed"
                    ? "text-gray-800"
                    : "text-gray-400"
                }`}
              >
                步骤 2: 自动绘图
              </span>
            </div>

            {/* Step 3 */}
            <div className="flex items-center space-x-6 relative z-10" id="progress-step-3">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center transition-all duration-300 ${
                  getStepStatusClass(3) === "completed"
                    ? "bg-blue-500 border-2 border-blue-200 text-white"
                    : getStepStatusClass(3) === "active"
                    ? "bg-blue-100 border-4 border-blue-400 animate-pulse"
                    : "bg-gray-100 border-2 border-transparent"
                }`}
              >
                {getStepStatusClass(3) === "completed" ? (
                  <Check className="w-3.5 h-3.5 stroke-[3px]" />
                ) : (
                  <div className={`w-2 h-2 rounded-full ${getStepStatusClass(3) === "active" ? "bg-blue-600" : "bg-gray-400"}`} />
                )}
              </div>
              <span
                className={`text-sm md:text-base font-semibold transition-colors duration-300 ${
                  getStepStatusClass(3) === "active"
                    ? "text-blue-600 font-bold"
                    : getStepStatusClass(3) === "completed"
                    ? "text-gray-800"
                    : "text-gray-400"
                }`}
              >
                步骤 3: 自动识别图片
              </span>
            </div>
          </div>
        </div>

        {/* Dynamic Display of Outputs or Idle State */}
        <div className={`w-full flex-grow flex flex-col justify-center ${showHistory ? 'hidden' : ''}`} id="monitor-content-area">
          <AnimatePresence mode="wait">
            {status === "idle" && (
              <motion.div
                key="idle-state"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="bg-gray-50 rounded-3xl p-6 md:p-10 text-center"
                id="idle-state-card"
              >
                <h3 className="text-lg md:text-xl font-bold mb-3 text-gray-800">流水线处于空闲状态</h3>
                <p className="text-xs md:text-sm leading-relaxed text-gray-500">
                  选择上方预设或输入创意因子，点击【一键全链条智绘】，系统将调用 work 本地后端生成提示词、图片并识别。
                </p>
              </motion.div>
            )}

            {/* Step 1 Output - Prompts generated */}
            {status === "generating_prompt" && (
              <motion.div
                key="loading-prompt"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className="bg-blue-50/50 border border-blue-100 rounded-3xl p-6 flex flex-col items-center text-center space-y-4"
                id="loading-step1-card"
              >
                <div className="w-12 h-12 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center animate-spin">
                  <RefreshCw className="w-6 h-6" />
                </div>
                <div>
                  <h4 className="font-bold text-blue-900 text-base">正在生成生图提示词...</h4>
                  <p className="text-xs text-blue-500 mt-1">
                    AI 正在根据您的创意因子编译图像生成提示词...
                  </p>
                </div>
              </motion.div>
            )}

            {/* Step 2 Output - Image generating */}
            {status === "generating_image" && (
              <motion.div
                key="loading-image"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className="bg-blue-50/50 border border-blue-100 rounded-3xl p-6 flex flex-col items-center text-center space-y-4"
                id="loading-step2-card"
              >
                <div className="w-12 h-12 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center animate-bounce">
                  <Sparkles className="w-6 h-6" />
                </div>
                <div>
                  <h4 className="font-bold text-blue-900 text-base">正在生成图片...</h4>
                  <p className="text-xs text-blue-500 mt-1">
                    “{pipeline.promptResult?.title}” 正在被绘制...
                  </p>
                </div>
                {pipeline.promptResult && (
                  <div className="w-full bg-white p-3.5 rounded-xl border border-blue-100 text-left text-xs text-gray-600 font-mono select-all">
                    {pipeline.promptResult.englishPrompt}
                  </div>
                )}
              </motion.div>
            )}

            {/* Step 3 Output - Auto image recognition & Deconstructing Visuals */}
            {status === "deconstructing_visual" && (
              <motion.div
                key="loading-deconstruct"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className="bg-blue-50/50 border border-blue-100 rounded-3xl p-6 flex flex-col items-center text-center space-y-4"
                id="loading-step3-card"
              >
                <div className="w-12 h-12 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center">
                  <Palette className="w-6 h-6 animate-pulse" />
                </div>
                <div>
                  <h4 className="font-bold text-blue-900 text-base">正在自动识别图片...</h4>
                  <p className="text-xs text-blue-500 mt-1">
                    AI 正在对生成的啤酒图片进行自动分析与因子提取...
                  </p>
                </div>
              </motion.div>
            )}

            {/* Pipeline Completed - Render full blueprint */}
            {status === "completed" && pipeline.promptResult && pipeline.imageUrl && (
              <motion.div
                key="completed-results"
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-6 w-full max-h-[500px] overflow-y-auto pr-1"
                id="completed-results-container"
              >
                <div className="relative group overflow-hidden rounded-3xl shadow-md border border-gray-100 bg-white" id="result-image-card">
                  <img
                    src={pipeline.imageUrl}
                    alt={pipeline.promptResult.title}
                    referrerPolicy="no-referrer"
                    className="w-full aspect-square object-cover transition-transform duration-500 group-hover:scale-102"
                  />
                  {pipeline.isFallback && (
                    <div className="absolute top-3 left-3 bg-black/65 backdrop-blur-sm text-[10px] text-white px-2.5 py-1 rounded-full font-sans tracking-wide" id="fallback-badge">
                      设计感精选
                    </div>
                  )}
                  <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/80 to-transparent p-5 text-white flex justify-between items-end">
                    <div>
                      <span className="text-[10px] uppercase tracking-widest text-gray-300">作品标题</span>
                      <h4 className="text-xl font-bold font-sans tracking-tight">{pipeline.promptResult.title}</h4>
                    </div>
                    <div className="flex space-x-1.5">
                      <button
                        onClick={() => downloadImage(pipeline.imageUrl || "", `${pipeline.promptResult?.title || "image"}.png`)}
                        className="p-2 rounded-full bg-white/25 hover:bg-white/40 text-white border border-white/20 transition-all cursor-pointer"
                        title="下载图片"
                      >
                        <Download className="w-4.5 h-4.5" />
                      </button>
                      <button
                        onClick={() => copyToClipboard(pipeline.imageUrl || "", "imageUrl")}
                        className="p-2 rounded-full bg-white/25 hover:bg-white/40 text-white border border-white/20 transition-all cursor-pointer"
                        title="复制图片链接"
                      >
                        {copiedText === "imageUrl" ? <Check className="w-4.5 h-4.5" /> : <Clipboard className="w-4.5 h-4.5" />}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Batch image grid (when multiple images) */}
                {batchImages.length > 1 && (
                  <div className="space-y-2" id="batch-images-grid">
                    <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">
                      全部生成结果 ({batchImages.length} 张)
                    </span>
                    <div className="grid grid-cols-2 gap-2">
                      {batchImages.map((img, i) => (
                        <div
                          key={i}
                          onClick={() => {
                            setPipeline((prev) => ({ ...prev, imageUrl: img.imageUrl }));
                          }}
                          className={`relative overflow-hidden rounded-xl border-2 cursor-pointer transition-all ${
                            pipeline.imageUrl === img.imageUrl ? "border-black" : "border-gray-100 hover:border-gray-300"
                          }`}
                        >
                          {img.imageUrl ? (
                            <img
                              src={img.imageUrl}
                              alt={img.title}
                              referrerPolicy="no-referrer"
                              className="w-full aspect-square object-cover"
                            />
                          ) : (
                            <div className="w-full aspect-square bg-gray-100 flex items-center justify-center text-gray-400 text-xs">
                              生成失败
                            </div>
                          )}
                          <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/60 to-transparent p-1.5">
                            <p className="text-[9px] text-white font-medium truncate">{img.title}</p>
                          </div>
                          {pipeline.imageUrl === img.imageUrl && (
                            <div className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-black text-white flex items-center justify-center">
                              <Check className="w-3 h-3" />
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Generated Prompt Content Box */}
                <div className="bg-gray-50 border border-gray-100 rounded-2xl p-5 space-y-4" id="paired-prompts-box">
                  <div>
                    <div className="flex justify-between items-center mb-1.5">
                      <span className="text-xs font-bold text-gray-500 tracking-wider">中文意境描述</span>
                      <button
                        onClick={() => copyToClipboard(pipeline.promptResult?.chinesePrompt || "", "chinese")}
                        className="text-gray-400 hover:text-black flex items-center space-x-1 text-xs cursor-pointer"
                      >
                        {copiedText === "chinese" ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Clipboard className="w-3.5 h-3.5" />}
                        <span>复制</span>
                      </button>
                    </div>
                    <p className="text-sm text-gray-700 leading-relaxed font-sans">{pipeline.promptResult.chinesePrompt}</p>
                  </div>

                  <div className="border-t border-gray-100 pt-3">
                    <div className="flex justify-between items-center mb-1.5">
                      <span className="text-xs font-bold text-gray-500 tracking-wider">AI 图像搭配提示词 (English)</span>
                      <button
                        onClick={() => copyToClipboard(pipeline.promptResult?.englishPrompt || "", "english")}
                        className="text-gray-400 hover:text-black flex items-center space-x-1 text-xs cursor-pointer"
                      >
                        {copiedText === "english" ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Clipboard className="w-3.5 h-3.5" />}
                        <span>复制</span>
                      </button>
                    </div>
                    <p className="text-xs text-gray-600 bg-white border border-gray-100 p-3.5 rounded-xl font-mono leading-relaxed max-h-[100px] overflow-y-auto">
                      {pipeline.promptResult.englishPrompt}
                    </p>
                  </div>
                </div>

                {/* Visual Deconstruction Blueprint */}
                {pipeline.deconstructed && (
                  <div className="bg-white border border-gray-100 rounded-2xl p-5 space-y-4" id="visual-deconstruction-box">
                    <div className="flex items-center space-x-2 text-gray-800 font-bold text-sm">
                      <Palette className="w-4.5 h-4.5 text-black" />
                      <span>1. 色彩解构方案 (Color Blueprint)</span>
                    </div>

                    {/* Copiable interactive swatches */}
                    <div className="grid grid-cols-5 gap-2" id="color-swatches-grid">
                      {pipeline.deconstructed.colors.map((color, index) => (
                        <div
                          key={index}
                          onClick={() => copyToClipboard(color.hex, `hex-${index}`)}
                          className="flex flex-col items-center group cursor-pointer"
                          title={`点击复制: ${color.hex} (${color.role})`}
                        >
                          <div
                            style={{ backgroundColor: color.hex }}
                            className="w-full aspect-square rounded-lg shadow-sm border border-gray-100 transition-transform duration-200 group-hover:scale-105"
                          />
                          <span className="text-[10px] font-bold text-gray-800 mt-1 truncate w-full text-center">
                            {color.name}
                          </span>
                          <span className="text-[8px] text-gray-400 font-mono">
                            {copiedText === `hex-${index}` ? "已复制!" : color.hex}
                          </span>
                        </div>
                      ))}
                    </div>

                    <div className="border-t border-gray-50 pt-3 space-y-3" id="deconstruct-text-details">
                      {/* Composition */}
                      <div className="flex items-start space-x-2">
                        <Eye className="w-4 h-4 text-gray-400 mt-0.5 shrink-0" />
                        <div>
                          <h5 className="text-xs font-bold text-gray-800">2. 构图框架手法</h5>
                          <p className="text-xs text-gray-600 leading-relaxed mt-0.5">{pipeline.deconstructed.composition}</p>
                        </div>
                      </div>

                      {/* Lighting */}
                      <div className="flex items-start space-x-2">
                        <Sun className="w-4 h-4 text-gray-400 mt-0.5 shrink-0" />
                        <div>
                          <h5 className="text-xs font-bold text-gray-800">3. 光影气候控制</h5>
                          <p className="text-xs text-gray-600 leading-relaxed mt-0.5">{pipeline.deconstructed.lighting}</p>
                        </div>
                      </div>

                      {/* Layering */}
                      <div className="flex items-start space-x-2">
                        <Layers className="w-4 h-4 text-gray-400 mt-0.5 shrink-0" />
                        <div>
                          <h5 className="text-xs font-bold text-gray-800">4. 层次结构配比</h5>
                          <p className="text-xs text-gray-600 leading-relaxed mt-0.5">{pipeline.deconstructed.depth}</p>
                        </div>
                      </div>

                      {/* Vibe */}
                      <div className="flex items-start space-x-2">
                        <Sparkles className="w-4 h-4 text-gray-400 mt-0.5 shrink-0" />
                        <div>
                          <h5 className="text-xs font-bold text-gray-800">5. 意境氛围基调</h5>
                          <p className="text-xs text-gray-600 leading-relaxed mt-0.5">{pipeline.deconstructed.vibe}</p>
                        </div>
                      </div>

                      {/* Automated Reverse-engineered Factors Section */}
                      {pipeline.deconstructed.recognizedFactors && (
                        <div className="border-t border-gray-100 pt-4 mt-4 space-y-3" id="automated-recognition-factors">
                          <div className="flex items-center space-x-2 text-gray-800 font-bold text-sm">
                            <Activity className="w-4.5 h-4.5 text-black" />
                            <span>6. 自动图像识别结果</span>
                          </div>
                          <div className="bg-gray-50 rounded-xl p-3.5 space-y-2 text-xs">
                            <div className="leading-relaxed">
                              <span className="font-bold text-gray-700">● 识别主体：</span>
                              <span className="text-gray-600">{pipeline.deconstructed.recognizedFactors.subject}</span>
                            </div>
                            <div className="leading-relaxed">
                              <span className="font-bold text-gray-700">● 识别场景：</span>
                              <span className="text-gray-600">{pipeline.deconstructed.recognizedFactors.scene}</span>
                            </div>
                            <div className="leading-relaxed">
                              <span className="font-bold text-gray-700">● 识别光影：</span>
                              <span className="text-gray-600">{pipeline.deconstructed.recognizedFactors.lighting}</span>
                            </div>
                            <div className="leading-relaxed">
                              <span className="font-bold text-gray-700">● 识别风格：</span>
                              <span className="text-gray-600">{pipeline.deconstructed.recognizedFactors.style}</span>
                            </div>
                            <div className="leading-relaxed">
                              <span className="font-bold text-gray-700">● 识别姿态：</span>
                              <span className="text-gray-600">{pipeline.deconstructed.recognizedFactors.posture}</span>
                            </div>
                            <div className="leading-relaxed">
                              <span className="font-bold text-gray-700">● 辅助指令：</span>
                              <span className="text-gray-600">{pipeline.deconstructed.recognizedFactors.helper}</span>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Export to AI 文案 */}
                <div className="flex space-x-2.5 pt-2" id="cross-export-actions">
                  <button
                    onClick={triggerExport}
                    className="flex-1 bg-gray-50 border border-gray-200 hover:bg-gray-100 text-gray-700 font-bold py-3 px-4 rounded-xl text-xs flex items-center justify-center space-x-1.5 transition-all cursor-pointer"
                  >
                    <span>导出到 AI 文案</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Footer info text from mockup */}
        <div className="mt-8 flex items-center space-x-2 text-[10px] text-gray-400 uppercase tracking-tight" id="pipeline-footer-info">
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
          </svg>
          <span>技术与技术绱智能选弱弱测的技术族，常生不易崭适的技术。</span>
        </div>
      </section>
    </div>
  );
}
