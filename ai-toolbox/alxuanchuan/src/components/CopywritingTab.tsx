/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from "react";
import { motion } from "motion/react";
import { Sparkles, Clipboard, Check, Share2, RefreshCw, Send, HelpCircle } from "lucide-react";
import { CopywritingResult } from "../types";

// Standard preset social platforms
const PLATFORMS = [
  { id: "xiaohongshu", name: "小红书 (Red Book)", icon: "📕", placeholder: "种草评测、高感度生活美学、多Emoji" },
  { id: "douyin", name: "抖音 (TikTok)", icon: "🎵", placeholder: "黄金前三秒吸睛、强反差口播、引导留评" },
  { id: "wechat", name: "微信公众号 (WeChat)", icon: "💬", placeholder: "深度情感共鸣、结构化叙事、引经据典" }
];

interface CopywritingTabProps {
  initialFactors: {
    title: string;
    creativeText: string;
  };
  isActive: boolean;
  onBusyChange: (busy: boolean) => void;
}

export default function CopywritingTab({ initialFactors, isActive, onBusyChange }: CopywritingTabProps) {
  const [title, setTitle] = useState(initialFactors.title || "");
  const [creativeText, setCreativeText] = useState(initialFactors.creativeText || "");
  const [platform, setPlatform] = useState("xiaohongshu");

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CopywritingResult | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [copiedText, setCopiedText] = useState<string | null>(null);

  // Report busy state to parent
  useEffect(() => {
    onBusyChange(loading);
  }, [loading, onBusyChange]);

  useEffect(() => {
    if (initialFactors.title) setTitle(initialFactors.title);
    if (initialFactors.creativeText) setCreativeText(initialFactors.creativeText);
  }, [initialFactors]);

  const generateCopy = async () => {
    try {
      setLoading(true);
      setErrorMessage("");

      const chosenPlatformName = PLATFORMS.find((p) => p.id === platform)?.name || "小红书";

      const response = await fetch("/api/explosive-copywriting", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          factors: creativeText,
          platform: chosenPlatformName
        })
      });

      if (!response.ok) {
        throw new Error("文案生成失败，请稍后重试。");
      }

      const data = await response.json();
      setResult(data);
    } catch (error: any) {
      console.error(error);
      setErrorMessage(error.message || "文案生成出错，请重试");
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(id);
    setTimeout(() => setCopiedText(null), 2000);
  };

  const copyFullPost = () => {
    if (!result) return;
    const full = `${result.headline}\n\n${result.body}\n\n${result.hashtags.join(" ")}`;
    copyToClipboard(full, "fullPost");
  };

  return (
    <div className="flex w-full min-h-[600px] flex-col md:flex-row" id="copywriting-container">
      {/* Left Column - Copywriting Inputs & Presets */}
      <section className="w-full md:w-[45%] p-6 md:p-12 border-b md:border-b-0 md:border-r border-gray-100 flex flex-col justify-between" id="copy-inputs-section">
        <div className="w-full space-y-6">
          <div className="flex items-center space-x-3">
            <Share2 className="w-6 h-6 text-gray-500" />
            <h2 className="text-xl md:text-2xl font-bold text-gray-900">爆款文案</h2>
          </div>

          <p className="text-xs md:text-sm text-gray-500 leading-relaxed">
            选择社交发布平台，AI 将一键生成适合发布的啤酒宣传和种草文案。
          </p>

          {/* Platform selection zone */}
          <div>
            <label className="block text-xs font-bold text-gray-400 mb-2.5 uppercase tracking-wide">
              目标社交发布平台
            </label>
            <div className="grid grid-cols-3 gap-2" id="platform-selectors-grid">
              {PLATFORMS.map((p) => (
                <button
                  key={p.id}
                  onClick={() => {
                    setPlatform(p.id);
                    setResult(null);
                  }}
                  id={`platform-${p.id}`}
                  className={`py-3 px-2 rounded-xl text-xs font-bold border flex flex-col items-center justify-center transition-all cursor-pointer ${
                    platform === p.id
                      ? "bg-black text-white border-black shadow-sm"
                      : "bg-gray-50 text-gray-600 border-gray-100 hover:bg-gray-100"
                  }`}
                >
                  <span className="text-lg mb-1">{p.icon}</span>
                  <span>{p.name.split(" ")[0]}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Form details */}
          <div className="space-y-4" id="copywriting-form">
            <div>
              <label className="block text-xs font-bold text-gray-500 mb-2 uppercase tracking-wide">
                推广啤酒品牌 / 产品名称
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-4 py-3 bg-gray-50 border-0 rounded-xl focus:ring-2 focus:ring-black/10 focus:bg-white text-sm outline-none transition-all"
                placeholder="例如：麦浪工坊·德式小麦白啤"
                id="copy-input-title"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-500 mb-2 uppercase tracking-wide">
                创意因子与啤酒亮点 (可选)
              </label>
              <textarea
                value={creativeText}
                onChange={(e) => setCreativeText(e.target.value)}
                rows={4}
                className="w-full px-4 py-3 bg-gray-50 border-0 rounded-xl focus:ring-2 focus:ring-black/10 focus:bg-white text-sm outline-none resize-none transition-all"
                placeholder="在此输入精酿特色、口感、消费场景。例如：100%纯麦芽酿造，麦香浓郁，冰镇后饮用，伴随雪白细腻泡沫，适合深夜露营、好友聚会或解压烧烤必备。"
                id="copy-input-creativeText"
              />
            </div>
          </div>
        </div>

        <div className="mt-8" id="copy-actions">
          {errorMessage && (
            <div className="mb-4 text-xs font-medium text-red-500 bg-red-50 p-3 rounded-lg border border-red-100">
              {errorMessage}
            </div>
          )}

          <button
            onClick={generateCopy}
            disabled={loading || (!title && !creativeText)}
            id="copy-generate-btn"
            className={`w-full text-white py-5 rounded-[2rem] flex items-center justify-center space-x-3 text-lg font-bold transition-all transform active:scale-95 shadow-lg cursor-pointer ${
              loading || (!title && !creativeText)
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-black hover:bg-gray-800 hover:scale-[0.99]"
            }`}
          >
            {loading ? (
              <>
                <RefreshCw className="w-6 h-6 animate-spin" />
                <span>正在生成文案...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-6 h-6" />
                <span>一键生成文案</span>
              </>
            )}
          </button>
        </div>
      </section>

      {/* Right Column - Social Post Mockphone Preview */}
      <section className="w-full md:w-[55%] p-6 md:p-12 flex flex-col justify-between bg-white" id="copy-results-section">
        <div className="w-full flex-grow flex flex-col justify-start">
          <h2 className="text-xl md:text-2xl font-bold mb-8 text-gray-900">文案预览</h2>

          {loading && (
            <div className="flex flex-col items-center justify-center py-20 text-center space-y-4" id="loading-copywriting">
              <div className="w-12 h-12 rounded-full border-4 border-gray-200 border-t-black animate-spin" />
              <div>
                <h4 className="font-bold text-gray-800 text-base">正在生成文案...</h4>
                <p className="text-xs text-gray-400 mt-1">
                  正在分析产品亮点并撰写社交媒体分享内容...
                </p>
              </div>
            </div>
          )}

          {!loading && !result && (
            <div className="bg-gray-50 rounded-3xl p-6 md:p-10 text-center flex-grow flex flex-col justify-center items-center" id="empty-copy-state">
              <Send className="w-10 h-10 text-gray-300 mb-3 animate-pulse" />
              <h3 className="text-lg md:text-xl font-bold mb-3 text-gray-800">暂无文案</h3>
              <p className="text-xs md:text-sm leading-relaxed text-gray-500 max-w-sm">
                选择发布平台并输入啤酒亮点，点击【一键生成文案】即可。
              </p>
            </div>
          )}

          {!loading && result && (
            <div className="space-y-6 flex-grow flex flex-col justify-between" id="copy-results-display">
              {/* Phone Smartphone Mockup for Social post */}
              <div className="bg-gray-950 rounded-[2.5rem] p-3 shadow-xl max-w-md mx-auto w-full border-4 border-gray-800 relative overflow-hidden" id="phone-mockup">
                {/* Speaker pill */}
                <div className="absolute top-4 left-1/2 -translate-x-1/2 w-28 h-4 bg-gray-800 rounded-full z-20 flex items-center justify-center">
                  <div className="w-12 h-1 bg-gray-900 rounded-full" />
                </div>

                <div className="bg-white rounded-[2rem] p-5 pt-7 max-h-[350px] overflow-y-auto font-sans text-xs text-gray-800 space-y-3 scrollbar-none" id="phone-content-view">
                  {/* Mock profile */}
                  <div className="flex items-center space-x-2 border-b border-gray-100 pb-2.5">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-pink-400 to-rose-600 flex items-center justify-center text-[10px] text-white font-bold font-mono">
                      AI
                    </div>
                    <div>
                      <h4 className="font-bold text-gray-900 text-xs">智绘工作台官方推广</h4>
                      <p className="text-[9px] text-gray-400">刚刚发布了作品</p>
                    </div>
                  </div>

                  {/* Headline */}
                  <h3 className="text-sm font-extrabold text-gray-900 leading-snug">
                    {result.headline}
                  </h3>

                  {/* Body Paragraphs formatted beautifully */}
                  <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap font-sans">
                    {result.body}
                  </p>

                  {/* Hashtags list */}
                  <div className="flex flex-wrap gap-1 pt-1">
                    {result.hashtags.map((tag, idx) => (
                      <span key={idx} className="text-[10px] text-blue-600 font-bold hover:underline">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Full Copy action bar */}
              <div className="bg-gray-50 border border-gray-100 p-4 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-3 shrink-0" id="copy-bar">
                <div className="text-left">
                  <h4 className="text-xs font-bold text-gray-800">宣发全链条就绪</h4>
                  <p className="text-[10px] text-gray-400 mt-0.5">直接一键复制整篇带平台排版的爆款图文。</p>
                </div>

                <button
                  onClick={copyFullPost}
                  id="copy-full-post-btn"
                  className="bg-black hover:bg-gray-800 text-white font-bold py-3 px-5 rounded-xl text-xs flex items-center justify-center space-x-1.5 transition-all transform hover:scale-[1.01] active:scale-98 cursor-pointer shrink-0"
                >
                  {copiedText === "fullPost" ? (
                    <>
                      <Check className="w-4 h-4 text-green-400" />
                      <span>已复制到剪贴板！</span>
                    </>
                  ) : (
                    <>
                      <Clipboard className="w-4 h-4" />
                      <span>复制全链文案</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
