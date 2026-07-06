/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from "react";
import { Sparkles, Clipboard, Check, Share2, RefreshCw, Send } from "lucide-react";
import { CopywritingResult } from "../types";
import { generateCopywriting } from "../api/services";

const PLATFORMS = [
  { id: "douyin", name: "15秒口播", icon: "🎵" },
  { id: "xiaohongshu", name: "小红书种草", icon: "📕" },
  { id: "wechat", name: "朋友圈社群", icon: "💬" },
];

interface CopywritingTabProps {
  initialFactors: { title: string; creativeText: string };
  artworkUrl?: string | null;
  isActive: boolean;
  onBusyChange: (busy: boolean) => void;
}

export default function CopywritingTab({ initialFactors, artworkUrl, isActive, onBusyChange }: CopywritingTabProps) {
  const [content, setContent] = useState("");
  const [platform, setPlatform] = useState("douyin");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CopywritingResult | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [copiedText, setCopiedText] = useState<string | null>(null);

  // Report busy state to parent
  useEffect(() => {
    onBusyChange(loading);
  }, [loading, onBusyChange]);

  useEffect(() => {
    const parts = [];
    if (initialFactors.title) parts.push(initialFactors.title);
    if (initialFactors.creativeText) parts.push(initialFactors.creativeText);
    if (parts.length) setContent(parts.join("\n"));
  }, [initialFactors]);

  const generateCopy = async () => {
    try {
      setLoading(true);
      setErrorMessage("");
      const firstLine = content.split(/\n+/).map((l) => l.trim()).find(Boolean) || "";
      const data = await generateCopywriting({
        title: firstLine.slice(0, 40),
        factors: content,
        platform,
      });
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
    <div className="flex w-full min-h-[600px] flex-col md:flex-row">
      {/* Left Column */}
      <section className="w-full md:w-[45%] p-6 md:p-12 border-b md:border-b-0 md:border-r border-gray-100 flex flex-col justify-between">
        <div className="w-full space-y-6">
          <div className="flex items-center space-x-3">
            <Share2 className="w-6 h-6 text-gray-500" />
            <h2 className="text-xl md:text-2xl font-bold text-gray-900">AI 文案</h2>
          </div>

          <p className="text-xs text-gray-500 leading-relaxed">
            选择平台，粘贴产品信息，一键生成推广文案。
          </p>

          {/* Platform buttons */}
          <div className="grid grid-cols-3 gap-2">
            {PLATFORMS.map((p) => (
              <button
                key={p.id}
                onClick={() => { setPlatform(p.id); setResult(null); }}
                className={`py-3 px-2 rounded-xl text-xs font-bold border flex flex-col items-center justify-center transition-all cursor-pointer ${
                  platform === p.id
                    ? "bg-black text-white border-black"
                    : "bg-gray-50 text-gray-600 border-gray-100 hover:bg-gray-100"
                }`}
              >
                <span className="text-lg mb-1">{p.icon}</span>
                <span>{p.name}</span>
              </button>
            ))}
          </div>

          {/* Content textarea — optional, backend auto-loads 介绍.txt */}
          <div>
            <label className="block text-xs font-bold text-gray-500 mb-2 uppercase tracking-wide">
              补充方向（选填）
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={4}
              className="w-full px-4 py-3 bg-gray-50 border-0 rounded-xl focus:ring-2 focus:ring-black/10 focus:bg-white text-sm outline-none resize-none transition-all"
              placeholder="可选：补充特定角度或卖点方向。留空则直接基于产品介绍生成。"
            />
          </div>
        </div>

        <div className="mt-8">
          {errorMessage && (
            <div className="mb-4 text-xs font-medium text-red-500 bg-red-50 p-3 rounded-lg border border-red-100">
              {errorMessage}
            </div>
          )}

          <button
            onClick={generateCopy}
            disabled={loading}
            className={`w-full text-white py-5 rounded-[2rem] flex items-center justify-center space-x-3 text-lg font-bold transition-all shadow-lg cursor-pointer ${
              loading
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-black hover:bg-gray-800"
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

      {/* Right Column */}
      <section className="w-full md:w-[55%] p-6 md:p-12 flex flex-col justify-between bg-white">
        <div className="w-full flex-grow flex flex-col">
          <h2 className="text-xl md:text-2xl font-bold mb-8 text-gray-900">文案预览</h2>

          {loading && (
            <div className="flex flex-col items-center justify-center py-20 text-center space-y-4">
              <div className="w-12 h-12 rounded-full border-4 border-gray-200 border-t-black animate-spin" />
              <div>
                <h4 className="font-bold text-gray-800 text-base">正在生成文案...</h4>
                <p className="text-xs text-gray-400 mt-1">AI 正在撰写社交媒体分享内容...</p>
              </div>
            </div>
          )}

          {!loading && !result && (
            <div className="bg-gray-50 rounded-3xl p-10 text-center flex-grow flex flex-col justify-center items-center">
              <Send className="w-10 h-10 text-gray-300 mb-3" />
              <h3 className="text-lg font-bold mb-3 text-gray-800">暂无文案</h3>
              <p className="text-xs text-gray-500 max-w-sm">
                选择平台，点击【一键生成文案】即可基于产品介绍自动生成。
              </p>
            </div>
          )}

          {!loading && result && (
            <div className="space-y-6 flex-grow">
              {/* Phone mockup */}
              <div className="bg-gray-950 rounded-[2.5rem] p-3 shadow-xl max-w-md mx-auto w-full border-4 border-gray-800 relative overflow-hidden">
                <div className="absolute top-4 left-1/2 -translate-x-1/2 w-28 h-4 bg-gray-800 rounded-full z-20 flex items-center justify-center">
                  <div className="w-12 h-1 bg-gray-900 rounded-full" />
                </div>
                <div className="bg-white rounded-[2rem] p-5 pt-7 max-h-[350px] overflow-y-auto text-xs text-gray-800 space-y-3">
                  <div className="flex items-center space-x-2 border-b border-gray-100 pb-2.5">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-pink-400 to-rose-600 flex items-center justify-center text-[10px] text-white font-bold">
                      AI
                    </div>
                    <div>
                      <h4 className="font-bold text-gray-900 text-xs">智绘工作台官方推广</h4>
                      <p className="text-[9px] text-gray-400">刚刚发布了作品</p>
                    </div>
                  </div>
                  <h3 className="text-sm font-extrabold text-gray-900 leading-snug">{result.headline}</h3>
                  <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">{result.body}</p>
                  <div className="flex flex-wrap gap-1 pt-1">
                    {result.hashtags.map((tag, idx) => (
                      <span key={idx} className="text-[10px] text-blue-600 font-bold">{tag}</span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Action bar */}
              <div className="bg-gray-50 border border-gray-100 p-4 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-3">
                <div>
                  <h4 className="text-xs font-bold text-gray-800">宣发就绪</h4>
                  <p className="text-[10px] text-gray-400 mt-0.5">一键复制整篇图文。</p>
                </div>
                <button
                  onClick={copyFullPost}
                  className="bg-black hover:bg-gray-800 text-white font-bold py-3 px-5 rounded-xl text-xs flex items-center space-x-1.5 transition-all cursor-pointer shrink-0"
                >
                  {copiedText === "fullPost" ? (
                    <>
                      <Check className="w-4 h-4 text-green-400" />
                      <span>已复制！</span>
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
