/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useRef, useEffect } from "react";
import { motion } from "motion/react";
import { Upload, Camera, Search, ArrowRight, RefreshCw, FileText, Check } from "lucide-react";
import { RecognizedImageResult, CreativeFactors } from "../types";

interface ImageRecognitionTabProps {
  onImportFactors: (factors: CreativeFactors, presetName: string | null) => void;
  isActive: boolean;
  onBusyChange: (busy: boolean) => void;
}

export default function ImageRecognitionTab({ onImportFactors, isActive, onBusyChange }: ImageRecognitionTabProps) {
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RecognizedImageResult | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [successImport, setSuccessImport] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Report busy state to parent
  useEffect(() => {
    onBusyChange(loading);
  }, [loading, onBusyChange]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const processFile = (file: File) => {
    if (!file.type.startsWith("image/")) {
      setErrorMessage("请上传有效的图片文件 (PNG, JPG, WEBP)！");
      return;
    }

    setErrorMessage("");
    setSuccessImport(false);
    const reader = new FileReader();
    reader.onload = (e) => {
      if (e.target?.result) {
        setImageSrc(e.target.result as string);
        setResult(null);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      processFile(e.target.files[0]);
    }
  };

  const runAnalysis = async () => {
    if (!imageSrc) return;

    try {
      setLoading(true);
      setErrorMessage("");
      setSuccessImport(false);

      const response = await fetch("/api/recognize-image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: imageSrc })
      });

      if (!response.ok) {
        throw new Error("图像智能识图分析失败，请检查 API 配置或重试。");
      }

      const data = await response.json();
      setResult(data);
    } catch (error: any) {
      console.error(error);
      setErrorMessage(error.message || "智能分析出错，请重试。");
    } finally {
      setLoading(false);
    }
  };

  const triggerImport = () => {
    if (!result) return;
    const factors: CreativeFactors = {
      subject: result.subject,
      scene: result.scene,
      lighting: result.lighting,
      style: result.style,
      posture: result.posture,
      helper: result.helper
    };
    
    onImportFactors(factors, result.matchedPreset === "其他" ? null : result.matchedPreset);
    setSuccessImport(true);
  };

  const resetImage = () => {
    setImageSrc(null);
    setResult(null);
    setErrorMessage("");
    setSuccessImport(false);
  };

  return (
    <div className="flex w-full min-h-[600px] flex-col md:flex-row" id="image-recognition-container">
      {/* Left Column - Image Upload and Zone */}
      <section className="w-full md:w-[50%] p-6 md:p-12 border-b md:border-b-0 md:border-r border-gray-100 flex flex-col justify-between" id="upload-zone-section">
        <div className="w-full">
          <div className="flex items-center space-x-3 mb-8">
            <Camera className="w-6 h-6 text-gray-500" />
            <h2 className="text-xl md:text-2xl font-bold text-gray-900">手动识图</h2>
          </div>

          <p className="text-xs md:text-sm text-gray-500 leading-relaxed mb-6">
            上传啤酒包装、海报或宣传照，AI 将自动分析画面并提取其主体、背景、色彩与镜头风格。
          </p>

          {!imageSrc ? (
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              id="drop-zone"
              className={`border-2 border-dashed rounded-3xl p-10 flex flex-col items-center justify-center space-y-4 cursor-pointer transition-all duration-300 min-h-[300px] ${
                isDragging
                  ? "border-black bg-gray-50/50"
                  : "border-gray-200 bg-gray-50 hover:bg-gray-100/50 hover:border-gray-300"
              }`}
            >
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileSelect}
                accept="image/*"
                className="hidden"
                id="file-selector"
              />
              <div className="w-14 h-14 rounded-full bg-white shadow-sm flex items-center justify-center text-gray-400">
                <Upload className="w-6 h-6" />
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-gray-800">拖拽图片至此，或点击上传</p>
                <p className="text-xs text-gray-400 mt-1">支持 PNG, JPG, JPEG, WEBP 格式</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4" id="image-preview-area">
              <div className="relative group overflow-hidden rounded-3xl border border-gray-100 max-h-[350px]" id="uploaded-preview-box">
                <img
                  src={imageSrc}
                  alt="Uploaded target"
                  className="w-full h-full object-contain bg-gray-900/5"
                  referrerPolicy="no-referrer"
                />
                {!loading && !result && (
                  <button
                    onClick={resetImage}
                    className="absolute top-4 right-4 bg-black/70 hover:bg-black text-white px-3.5 py-1.5 rounded-full text-xs font-bold transition-all cursor-pointer"
                    id="change-img-btn"
                  >
                    更换图片
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {imageSrc && (
          <div className="mt-8" id="analysis-actions">
            {errorMessage && (
              <div className="mb-4 text-xs font-medium text-red-500 bg-red-50 p-3 rounded-lg border border-red-100" id="recognition-error">
                {errorMessage}
              </div>
            )}

            <button
              onClick={runAnalysis}
              disabled={loading}
              id="analysis-trigger-btn"
              className={`w-full text-white py-5 rounded-[2rem] flex items-center justify-center space-x-3 text-lg font-bold transition-all transform active:scale-95 shadow-lg cursor-pointer ${
                loading ? "bg-gray-400 cursor-not-allowed" : "bg-black hover:bg-gray-800 hover:scale-[0.99]"
              }`}
            >
              {loading ? (
                <>
                  <RefreshCw className="w-6 h-6 animate-spin" />
                  <span>正在分析图片...</span>
                </>
              ) : (
                <>
                  <Search className="w-6 h-6" />
                  <span>一键智能分析</span>
                </>
              )}
            </button>
          </div>
        )}
      </section>

      {/* Right Column - Reversed engineered Factors Matrix */}
      <section className="w-full md:w-[50%] p-6 md:p-12 flex flex-col justify-between bg-white" id="results-section">
        <div className="w-full">
          <h2 className="text-xl md:text-2xl font-bold mb-8 text-gray-900">识图分析结果</h2>

          {loading && (
            <div className="flex flex-col items-center justify-center py-20 text-center space-y-4" id="loading-factor-state">
              <div className="w-12 h-12 rounded-full border-4 border-gray-200 border-t-black animate-spin" />
              <div>
                <h4 className="font-bold text-gray-800 text-base">正在分析画面...</h4>
                <p className="text-xs text-gray-400 mt-1">AI 正在提取主体姿态、背景元素和光影风格...</p>
              </div>
            </div>
          )}

          {!loading && !result && (
            <div className="bg-gray-50 rounded-3xl p-6 md:p-10 text-center" id="empty-recognition-state">
              <h3 className="text-lg md:text-xl font-bold mb-3 text-gray-800">暂无分析数据</h3>
              <p className="text-xs md:text-sm leading-relaxed text-gray-500">
                上传啤酒包装、海报或宣传照，点击【一键智能分析】，AI将自动为您分析。
              </p>
            </div>
          )}

          {!loading && result && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-5"
              id="recognition-factors-list"
            >
              {result.matchedPreset && result.matchedPreset !== "其他" && (
                <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-3 flex items-center justify-between text-xs" id="preset-match-badge">
                  <span className="text-blue-600 font-bold">🎯 最贴近的预设风格</span>
                  <span className="bg-blue-600 text-white font-bold px-2 py-0.5 rounded-full">{result.matchedPreset}</span>
                </div>
              )}

              {/* Factors list cards */}
              <div className="space-y-3.5" id="reverse-factors-cards">
                <div className="bg-gray-50 p-4 rounded-xl flex items-start space-x-3">
                  <span className="text-base bg-white shadow-xs p-1.5 rounded-md">👤</span>
                  <div>
                    <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider">目标主体 / 角色</h4>
                    <p className="text-sm font-semibold text-gray-800 mt-0.5">{result.subject}</p>
                  </div>
                </div>

                <div className="bg-gray-50 p-4 rounded-xl flex items-start space-x-3">
                  <span className="text-base bg-white shadow-xs p-1.5 rounded-md">📍</span>
                  <div>
                    <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider">背景场景 / 地理</h4>
                    <p className="text-sm font-semibold text-gray-800 mt-0.5">{result.scene}</p>
                  </div>
                </div>

                <div className="bg-gray-50 p-4 rounded-xl flex items-start space-x-3">
                  <span className="text-base bg-white shadow-xs p-1.5 rounded-md">☀️</span>
                  <div>
                    <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider">光影气候 / 天气</h4>
                    <p className="text-sm font-semibold text-gray-800 mt-0.5">{result.lighting}</p>
                  </div>
                </div>

                <div className="bg-gray-50 p-4 rounded-xl flex items-start space-x-3">
                  <span className="text-base bg-white shadow-xs p-1.5 rounded-md">📸</span>
                  <div>
                    <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider">视觉风格 / 艺术</h4>
                    <p className="text-sm font-semibold text-gray-800 mt-0.5">{result.style}</p>
                  </div>
                </div>

                <div className="bg-gray-50 p-4 rounded-xl flex items-start space-x-3">
                  <span className="text-base bg-white shadow-xs p-1.5 rounded-md">🏃</span>
                  <div>
                    <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider">主体姿态 / 动作</h4>
                    <p className="text-sm font-semibold text-gray-800 mt-0.5">{result.posture}</p>
                  </div>
                </div>

                <div className="bg-gray-50 p-4 rounded-xl flex items-start space-x-3">
                  <span className="text-base bg-white shadow-xs p-1.5 rounded-md">⚙️</span>
                  <div>
                    <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider">辅助指令</h4>
                    <p className="text-sm font-semibold text-gray-800 mt-0.5">{result.helper}</p>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </div>

        {result && !loading && (
          <div className="mt-8 space-y-3" id="import-actions">
            {successImport && (
              <div className="text-center text-xs text-green-600 bg-green-50 py-2.5 rounded-xl border border-green-100 flex items-center justify-center space-x-1" id="success-import-toast">
                <Check className="w-4 h-4" />
                <span>创意因子已成功导入工作台！可切换至手工绘图查看。</span>
              </div>
            )}

            <button
              onClick={triggerImport}
              id="import-factors-btn"
              className="w-full bg-black hover:bg-gray-800 text-white py-4 px-6 rounded-2xl font-bold flex items-center justify-center space-x-2 transition-all transform hover:scale-[0.99] active:scale-95 shadow-md cursor-pointer"
            >
              <FileText className="w-5 h-5" />
              <span>导入创意因子矩阵并编辑</span>
              <ArrowRight className="w-4 h-4" />
            </button>

            <button
              onClick={resetImage}
              id="reset-recognition-btn"
              className="w-full bg-gray-50 hover:bg-gray-100 border border-gray-100 text-gray-600 py-3 px-6 rounded-2xl font-semibold text-xs flex items-center justify-center transition-all cursor-pointer"
            >
              <span>清除并重新上传</span>
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
