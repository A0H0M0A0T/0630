/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useCallback } from "react";
import { PenTool, Image as ImageIcon, FileText, Share2, AlertTriangle } from "lucide-react";
import { ActiveTab, CreativeFactors, PipelineData } from "./types";
import HandDrawnTab from "./components/HandDrawnTab";
import ImageRecognitionTab from "./components/ImageRecognitionTab";
import LyricMatchingTab from "./components/LyricMatchingTab";
import CopywritingTab from "./components/CopywritingTab";

export default function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("hand-drawn");

  // Track which tab is currently generating (if any)
  const [generatingTab, setGeneratingTab] = useState<ActiveTab | null>(null);
  // Pending tab switch that needs user confirmation
  const [pendingSwitch, setPendingSwitch] = useState<ActiveTab | null>(null);

  // Shared Creative Factors Matrix state
  const [factors, setFactors] = useState<CreativeFactors>({
    subject: "",
    scene: "",
    lighting: "",
    style: "",
    posture: "",
    helper: ""
  });

  // Shared Pipeline Result state (persists last drawing results)
  const [pipeline, setPipeline] = useState<PipelineData>({
    factors: {
      subject: "",
      scene: "",
      lighting: "",
      style: "",
      posture: "",
      helper: ""
    },
    promptResult: null,
    imageUrl: null,
    deconstructed: null,
    isFallback: false
  });

  // States for manual tab trigger initiations (cross-over exports)
  const [lyricInitialFactors, setLyricInitialFactors] = useState({
    subject: "",
    scene: "",
    style: "",
    title: ""
  });

  const [copyInitialFactors, setCopyInitialFactors] = useState({
    title: "",
    creativeText: ""
  });

  // Handle tab click with generation-in-progress check
  const handleTabClick = useCallback((tab: ActiveTab) => {
    if (tab === activeTab) return; // Already on this tab
    if (generatingTab) {
      // Generation in progress — ask for confirmation
      setPendingSwitch(tab);
    } else {
      setActiveTab(tab);
    }
  }, [activeTab, generatingTab]);

  // User confirms switching away while generation is running
  const confirmSwitch = useCallback(() => {
    if (pendingSwitch) {
      setActiveTab(pendingSwitch);
      setPendingSwitch(null);
    }
  }, [pendingSwitch]);

  // User cancels the switch
  const cancelSwitch = useCallback(() => {
    setPendingSwitch(null);
  }, []);

  // Callback from tabs to report their generation status
  const handleTabBusyChange = useCallback((tab: ActiveTab, isBusy: boolean) => {
    setGeneratingTab(isBusy ? tab : null);
  }, []);

  // Export from Hand-drawn Tab to other tabs (programmatic — bypasses confirmation)
  const handleExport = (targetTab: "lyrics" | "copywriting", title: string, creativeText: string) => {
    if (targetTab === "lyrics") {
      setLyricInitialFactors({
        subject: factors.subject,
        scene: factors.scene,
        style: factors.style,
        title: title
      });
      setActiveTab("lyrics");
      setGeneratingTab(null); // Reset generating state on programmatic switch
    } else if (targetTab === "copywriting") {
      setCopyInitialFactors({
        title,
        creativeText
      });
      setActiveTab("copywriting");
      setGeneratingTab(null);
    }
  };

  // Import reverse-engineered factors from Image Recognition back to Hand-drawn Workspace
  const handleImportFactors = (importedFactors: CreativeFactors) => {
    setFactors(importedFactors);
    // Clear last pipeline results to avoid display mismatches, encouraging new run
    setPipeline({
      factors: importedFactors,
      promptResult: null,
      imageUrl: null,
      deconstructed: null,
      isFallback: false
    });
    setActiveTab("hand-drawn");
    setGeneratingTab(null); // Reset generating state on programmatic switch
  };

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col font-sans select-none selection:bg-black selection:text-white" id="app-root">
      
      {/* HEADER SECTION (Matching mockup design perfectly) */}
      <header className="bg-white/80 backdrop-blur-md border-b border-gray-100 px-6 md:px-12 py-5 sticky top-0 z-50 flex flex-col md:flex-row items-center justify-between gap-4" id="main-header">
        <div className="flex items-center space-x-3" id="logo-container">
          <div className="w-8 h-8 rounded-xl bg-black flex items-center justify-center text-white" id="logo-icon">
            <span className="text-base font-bold font-mono">智</span>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-gray-900 font-sans">
            极致简约 AI 全链条工作台
          </h1>
        </div>

        <nav className="flex items-center flex-wrap justify-center gap-1 md:gap-4 text-sm font-medium text-gray-600" id="main-nav">
          {/* Handdrawn button */}
          <button
            onClick={() => handleTabClick("hand-drawn")}
            id="tab-btn-hand-drawn"
            className={`flex items-center space-x-1.5 px-4 py-2 rounded-xl transition-all cursor-pointer relative ${
              activeTab === "hand-drawn"
                ? "bg-black text-white font-bold shadow-sm"
                : "hover:text-black hover:bg-gray-50"
            }`}
          >
            <PenTool className="w-4 h-4" />
            <span>手工绘图</span>
            {generatingTab === "hand-drawn" && (
              <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-yellow-400 rounded-full animate-pulse border-2 border-white"></span>
            )}
          </button>

          {/* Recognition button */}
          <button
            onClick={() => handleTabClick("recognition")}
            id="tab-btn-recognition"
            className={`flex items-center space-x-1.5 px-4 py-2 rounded-xl transition-all cursor-pointer relative ${
              activeTab === "recognition"
                ? "bg-black text-white font-bold shadow-sm"
                : "hover:text-black hover:bg-gray-50"
            }`}
          >
            <ImageIcon className="w-4 h-4" />
            <span>手动识图</span>
            {generatingTab === "recognition" && (
              <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-yellow-400 rounded-full animate-pulse border-2 border-white"></span>
            )}
          </button>

          {/* Lyrics button */}
          <button
            onClick={() => handleTabClick("lyrics")}
            id="tab-btn-lyrics"
            className={`flex items-center space-x-1.5 px-4 py-2 rounded-xl transition-all cursor-pointer relative ${
              activeTab === "lyrics"
                ? "bg-black text-white font-bold shadow-sm"
                : "hover:text-black hover:bg-gray-50"
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>手动配词</span>
            {generatingTab === "lyrics" && (
              <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-yellow-400 rounded-full animate-pulse border-2 border-white"></span>
            )}
          </button>

          {/* Copywriting button */}
          <button
            onClick={() => handleTabClick("copywriting")}
            id="tab-btn-copywriting"
            className={`flex items-center space-x-1.5 px-4 py-2 rounded-xl transition-all cursor-pointer relative ${
              activeTab === "copywriting"
                ? "bg-black text-white font-bold shadow-sm"
                : "hover:text-black hover:bg-gray-50"
            }`}
          >
            <Share2 className="w-4 h-4" />
            <span>爆款文案</span>
            {generatingTab === "copywriting" && (
              <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-yellow-400 rounded-full animate-pulse border-2 border-white"></span>
            )}
          </button>

          {/* Pipeline ready status pill */}
          <div className="ml-2 bg-gray-50 px-3 py-1.5 rounded-full flex items-center space-x-2 border border-gray-100 shrink-0" id="pulse-badge">
            <span className={`w-2 h-2 rounded-full animate-pulse ${generatingTab ? "bg-yellow-500" : "bg-green-500"}`}></span>
            <span className="text-[10px] text-gray-500 font-bold uppercase tracking-wider">
              {generatingTab ? "Generation Running" : "Creative Flow Ready"}
            </span>
          </div>
        </nav>
      </header>

      {/* BODY/MAIN WORKSPACE SECTION */}
      <main className="flex-grow flex items-center justify-center p-4 md:p-8" id="main-content">
        <div
          className="bg-white w-full max-w-6xl rounded-[2.5rem] overflow-hidden shadow-2xl border border-gray-100/50 flex flex-col md:flex-row min-h-[600px] transition-all"
          id="main-dashboard-container"
        >
          {/* All tabs are kept mounted — hidden with CSS, not unmounted.
              This preserves async operations (image gen, recognition, lyrics, copywriting)
              when the user navigates between tabs. */}
          <div style={{ display: activeTab === "hand-drawn" ? "flex" : "none", width: "100%", flex: 1 }}>
            <HandDrawnTab
              factors={factors}
              setFactors={setFactors}
              pipeline={pipeline}
              setPipeline={setPipeline}
              onExport={handleExport}
              isActive={activeTab === "hand-drawn"}
              onBusyChange={(busy: boolean) => handleTabBusyChange("hand-drawn", busy)}
            />
          </div>

          <div style={{ display: activeTab === "recognition" ? "flex" : "none", width: "100%", flex: 1 }}>
            <ImageRecognitionTab
              onImportFactors={handleImportFactors}
              isActive={activeTab === "recognition"}
              onBusyChange={(busy: boolean) => handleTabBusyChange("recognition", busy)}
            />
          </div>

          <div style={{ display: activeTab === "lyrics" ? "flex" : "none", width: "100%", flex: 1 }}>
            <LyricMatchingTab
              initialFactors={lyricInitialFactors.subject ? lyricInitialFactors : {
                subject: factors.subject,
                scene: factors.scene,
                style: factors.style,
                title: pipeline.promptResult?.title || ""
              }}
              artworkUrl={pipeline.imageUrl}
              isActive={activeTab === "lyrics"}
              onBusyChange={(busy: boolean) => handleTabBusyChange("lyrics", busy)}
            />
          </div>

          <div style={{ display: activeTab === "copywriting" ? "flex" : "none", width: "100%", flex: 1 }}>
            <CopywritingTab
              initialFactors={copyInitialFactors.title ? copyInitialFactors : {
                title: pipeline.promptResult?.title || "",
                creativeText: factors.subject ? `主体: ${factors.subject}\n场景: ${factors.scene}\n风格: ${factors.style}` : ""
              }}
              isActive={activeTab === "copywriting"}
              onBusyChange={(busy: boolean) => handleTabBusyChange("copywriting", busy)}
            />
          </div>
        </div>
      </main>

      {/* Confirmation Dialog — shown when user tries to switch tabs during generation */}
      {pendingSwitch && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-sm" id="confirm-switch-overlay">
          <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md mx-4 text-center border border-gray-100">
            <div className="w-14 h-14 rounded-full bg-yellow-100 text-yellow-600 flex items-center justify-center mx-auto mb-5">
              <AlertTriangle className="w-7 h-7" />
            </div>
            <h3 className="text-lg font-bold text-gray-900 mb-2">确认切换页面？</h3>
            <p className="text-sm text-gray-500 leading-relaxed mb-6">
              当前 <strong className="text-gray-700">{
                generatingTab === "hand-drawn" ? "手工绘图" :
                generatingTab === "recognition" ? "手动识图" :
                generatingTab === "lyrics" ? "手动配词" : "爆款文案"
              }</strong> 正在生成中，切换导航栏不会中断后台任务，但你将看不到进度更新。确定要切换吗？
            </p>
            <div className="flex space-x-3 justify-center">
              <button
                onClick={cancelSwitch}
                className="px-6 py-2.5 rounded-xl bg-black text-white font-bold text-sm hover:bg-gray-800 transition-all cursor-pointer"
              >
                留在当前页
              </button>
              <button
                onClick={confirmSwitch}
                className="px-6 py-2.5 rounded-xl bg-gray-100 text-gray-600 font-bold text-sm hover:bg-gray-200 transition-all cursor-pointer"
              >
                仍然切换
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
