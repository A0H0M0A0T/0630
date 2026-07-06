/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from "react";
import { motion } from "motion/react";
import { Sparkles, Clipboard, Check, Quote, RefreshCw, PenTool, Image as ImageIcon } from "lucide-react";
import { LyricsResult } from "../types";
import { generateLyrics as generateLocalLyrics } from "../api/services";

interface LyricMatchingTabProps {
  initialFactors: {
    subject: string;
    scene: string;
    style: string;
    title: string;
  };
  artworkUrl: string | null;
}

export default function LyricMatchingTab({ initialFactors, artworkUrl }: LyricMatchingTabProps) {
  const [subject, setSubject] = useState(initialFactors.subject || "");
  const [scene, setScene] = useState(initialFactors.scene || "");
  const [style, setStyle] = useState(initialFactors.style || "");
  const [artworkTitle, setArtworkTitle] = useState(initialFactors.title || "");

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<LyricsResult | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [copiedText, setCopiedText] = useState<string | null>(null);
  const [selectedTitle, setSelectedTitle] = useState("");

  // Update when inherited props change
  useEffect(() => {
    if (initialFactors.subject) setSubject(initialFactors.subject);
    if (initialFactors.scene) setScene(initialFactors.scene);
    if (initialFactors.style) setStyle(initialFactors.style);
    if (initialFactors.title) {
      setArtworkTitle(initialFactors.title);
      setSelectedTitle(initialFactors.title);
    }
  }, [initialFactors]);

  const generateLyrics = async () => {
    try {
      setLoading(true);
      setErrorMessage("");
      
      const data: LyricsResult = await generateLocalLyrics({
        subject,
        scene,
        style,
        title: artworkTitle
      });
      setResult(data);
      if (data.titles && data.titles.length > 0) {
        setSelectedTitle(data.titles[0]);
      } else if (artworkTitle) {
        setSelectedTitle(artworkTitle);
      }
    } catch (error: any) {
      console.error(error);
      setErrorMessage(error.message || "配词生成出错，请重试");
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(id);
    setTimeout(() => setCopiedText(null), 2000);
  };

  return (
    <div className="flex w-full min-h-[600px] flex-col md:flex-row" id="lyric-matching-container">
      {/* Left Column - Design Intent Entry */}
      <section className="w-full md:w-[45%] p-6 md:p-12 border-b md:border-b-0 md:border-r border-gray-100 flex flex-col justify-between" id="lyric-inputs-section">
        <div className="w-full space-y-6">
          <div className="flex items-center space-x-3">
            <PenTool className="w-6 h-6 text-gray-500" />
            <h2 className="text-xl md:text-2xl font-bold text-gray-900">AI 配词</h2>
          </div>

          <p className="text-xs md:text-sm text-gray-500 leading-relaxed">
            输入啤酒特征、场景和风格，一键生成适合酒标、瓶身或海报的金句宣传语。
          </p>

          <div className="space-y-4" id="lyric-form">
            <div>
              <label className="block text-xs font-bold text-gray-500 mb-2 uppercase tracking-wide">
                精酿/产品主体描绘
              </label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className="w-full px-4 py-3 bg-gray-50 border-0 rounded-xl focus:ring-2 focus:ring-black/10 focus:bg-white text-sm outline-none transition-all"
                placeholder="例如：晶莹剔透的精酿小麦白啤，泡沫细腻，散发麦芽香气"
                id="lyric-input-subject"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-500 mb-2 uppercase tracking-wide">
                场景氛围勾勒
              </label>
              <input
                type="text"
                value={scene}
                onChange={(e) => setScene(e.target.value)}
                className="w-full px-4 py-3 bg-gray-50 border-0 rounded-xl focus:ring-2 focus:ring-black/10 focus:bg-white text-sm outline-none transition-all"
                placeholder="例如：夏日海滩露营派对，落日晚霞与暖黄色野营灯火交织"
                id="lyric-input-scene"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-500 mb-2 uppercase tracking-wide">
                视觉设计风格
              </label>
              <input
                type="text"
                value={style}
                onChange={(e) => setStyle(e.target.value)}
                className="w-full px-4 py-3 bg-gray-50 border-0 rounded-xl focus:ring-2 focus:ring-black/10 focus:bg-white text-sm outline-none transition-all"
                placeholder="例如：清新时尚海报风格，高端微距静物，高饱和度质感"
                id="lyric-input-style"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-500 mb-2 uppercase tracking-wide">
                备选或原始标题 (可选)
              </label>
              <input
                type="text"
                value={artworkTitle}
                onChange={(e) => setArtworkTitle(e.target.value)}
                className="w-full px-4 py-3 bg-gray-50 border-0 rounded-xl focus:ring-2 focus:ring-black/10 focus:bg-white text-sm outline-none transition-all"
                placeholder="输入产品现有名称 (如：麦浪工坊)，或留空让 AI 推荐"
                id="lyric-input-title"
              />
            </div>
          </div>
        </div>

        <div className="mt-8" id="lyric-actions">
          {errorMessage && (
            <div className="mb-4 text-xs font-medium text-red-500 bg-red-50 p-3 rounded-lg border border-red-100">
              {errorMessage}
            </div>
          )}

          <button
            onClick={generateLyrics}
            disabled={loading || (!subject && !scene)}
            id="lyric-generate-btn"
            className={`w-full text-white py-5 rounded-[2rem] flex items-center justify-center space-x-3 text-lg font-bold transition-all transform active:scale-95 shadow-lg cursor-pointer ${
              loading || (!subject && !scene)
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-black hover:bg-gray-800 hover:scale-[0.99]"
            }`}
          >
            {loading ? (
              <>
                <RefreshCw className="w-6 h-6 animate-spin" />
                <span>正在生成配词...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-6 h-6" />
                <span>一键生成配词</span>
              </>
            )}
          </button>
        </div>
      </section>

      {/* Right Column - Visual Card Cover Poster Preview */}
      <section className="w-full md:w-[55%] p-6 md:p-12 flex flex-col justify-between bg-white" id="lyric-results-section">
        <div className="w-full flex-grow flex flex-col justify-start">
          <h2 className="text-xl md:text-2xl font-bold mb-8 text-gray-900">意境金句卡</h2>

          {loading && (
            <div className="flex flex-col items-center justify-center py-20 text-center space-y-4" id="loading-lyrics">
              <div className="w-12 h-12 rounded-full border-4 border-gray-200 border-t-black animate-spin" />
              <div>
                <h4 className="font-bold text-gray-800 text-base">正在创作配词...</h4>
                <p className="text-xs text-gray-400 mt-1">AI 正在根据产品调性生成微醺意境金句和 Slogan...</p>
              </div>
            </div>
          )}

          {!loading && !result && (
            <div className="bg-gray-50 rounded-3xl p-6 md:p-10 text-center flex-grow flex flex-col justify-center items-center" id="empty-lyrics-state">
              <Quote className="w-10 h-10 text-gray-300 mb-3" />
              <h3 className="text-lg md:text-xl font-bold mb-3 text-gray-800">暂无金句卡</h3>
              <p className="text-xs md:text-sm leading-relaxed text-gray-500 max-w-sm">
                在左侧输入啤酒特征或导入因子，点击【一键生成配词】即可。
              </p>
            </div>
          )}

          {!loading && result && (
            <div className="space-y-6 flex-grow flex flex-col" id="lyric-results-display">
              {/* Interactive Recommended Titles list */}
              <div>
                <span className="text-xs font-bold text-gray-400 uppercase tracking-wide">1. 推荐标题 (点击应用)</span>
                <div className="flex flex-wrap gap-2 mt-2.5" id="suggested-titles">
                  {result.titles.map((t, idx) => (
                    <button
                      key={idx}
                      onClick={() => setSelectedTitle(t)}
                      id={`title-recommend-${idx}`}
                      className={`px-4 py-2 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
                        selectedTitle === t
                          ? "bg-black text-white border-black shadow-sm scale-102"
                          : "bg-gray-50 text-gray-600 border-gray-100 hover:bg-gray-100"
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              {/* Poster Card Preview block */}
              <div
                className="relative overflow-hidden rounded-[2rem] aspect-[16/10] w-full shadow-lg border border-gray-100 text-white flex flex-col justify-between p-6 md:p-8 shrink-0 select-none group"
                id="lyric-poster-card"
              >
                {/* Visual Background (Artwork URL or abstract atmospheric pattern) */}
                <div className="absolute inset-0 bg-gray-950 z-0">
                  {artworkUrl ? (
                    <img
                      src={artworkUrl}
                      alt="Aesthetic Background"
                      referrerPolicy="no-referrer"
                      className="w-full h-full object-cover opacity-55 transition-transform duration-500 group-hover:scale-102"
                    />
                  ) : (
                    <div className="w-full h-full bg-gradient-to-tr from-rose-950/40 via-purple-950/40 to-slate-900 opacity-60" />
                  )}
                  {/* Overlay vignette */}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/40 to-transparent" />
                </div>

                {/* Cover Header */}
                <div className="relative z-10 flex justify-between items-start">
                  <div>
                    <span className="text-[9px] uppercase tracking-widest text-gray-400 font-mono">ART COVER</span>
                    <h4 className="text-lg font-extrabold font-sans tracking-tight text-white/95">
                      {selectedTitle || "意境"}
                    </h4>
                  </div>
                  <div className="flex space-x-1.5" id="poster-tags">
                    {result.tags.map((tag, i) => (
                      <span key={i} className="text-[8px] bg-white/10 backdrop-blur-md text-white/90 border border-white/10 px-2 py-0.5 rounded-full font-bold">
                        #{tag}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Centered Lyric quote */}
                <div className="relative z-10 text-center my-2 max-w-md mx-auto" id="poster-quote">
                  <Quote className="w-6 h-6 text-white/20 mx-auto mb-2.5" />
                  <p className="text-sm md:text-lg font-bold font-serif tracking-wider leading-relaxed text-white drop-shadow-md">
                    {result.mainVerse}
                  </p>
                </div>

                {/* Bottom details */}
                <div className="relative z-10 flex justify-between items-end border-t border-white/10 pt-3 text-[9px] text-gray-400">
                  <p className="italic font-sans text-left truncate max-w-xs">{result.prose}</p>
                  <span className="font-mono text-white/60">© AI CREATIVE STATION</span>
                </div>
              </div>

              {/* Copy actions list */}
              <div className="space-y-3 bg-gray-50 rounded-2xl p-4 border border-gray-100 mt-auto" id="copy-lyrics-box">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-bold text-gray-500">金句配词副本</span>
                  <button
                    onClick={() => copyToClipboard(result.mainVerse, "mainVerseCopy")}
                    className="text-gray-400 hover:text-black flex items-center space-x-1 text-xs cursor-pointer"
                  >
                    {copiedText === "mainVerseCopy" ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Clipboard className="w-3.5 h-3.5" />}
                    <span>复制主金句</span>
                  </button>
                </div>
                <p className="text-xs text-gray-600 bg-white border border-gray-100 p-2.5 rounded-lg font-serif">
                  {result.mainVerse}
                </p>

                <div className="flex justify-between items-center border-t border-gray-100 pt-3">
                  <span className="text-xs font-bold text-gray-500">意境展开长文案</span>
                  <button
                    onClick={() => copyToClipboard(result.prose, "proseCopy")}
                    className="text-gray-400 hover:text-black flex items-center space-x-1 text-xs cursor-pointer"
                  >
                    {copiedText === "proseCopy" ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Clipboard className="w-3.5 h-3.5" />}
                    <span>复制长文案</span>
                  </button>
                </div>
                <p className="text-xs text-gray-500 leading-relaxed bg-white border border-gray-100 p-2.5 rounded-lg italic">
                  {result.prose}
                </p>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
