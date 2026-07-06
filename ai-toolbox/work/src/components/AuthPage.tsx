import React, { useState } from "react";
import { login, register } from "../api/auth";
import { AlertCircle, RefreshCw, User, Lock } from "lucide-react";

interface AuthPageProps {
  onLogin: (username: string) => void;
}

export default function AuthPage({ onLogin }: AuthPageProps) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!username.trim() || !password) {
      setError("请填写用户名和密码");
      return;
    }
    setLoading(true);
    try {
      if (mode === "register") {
        if (password.length < 4) {
          setError("密码至少 4 个字符");
          setLoading(false);
          return;
        }
        await register(username.trim(), password);
      }
      await login(username.trim(), password);
      onLogin(username.trim());
    } catch (err: any) {
      setError(err.message || "操作失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center p-4 overflow-hidden font-sans selection:bg-black selection:text-white bg-white">
      {/* Background wave decoration */}
      <div className="absolute inset-0 pointer-events-none">
        <svg className="absolute top-0 left-0 w-full h-full" viewBox="0 0 1440 900" fill="none" preserveAspectRatio="xMidYMid slice">
          {/* Large soft blobs */}
          <ellipse cx="150" cy="400" rx="650" ry="400" fill="#e5e7eb" opacity="0.7" />
          <ellipse cx="1300" cy="250" rx="550" ry="350" fill="#e5e7eb" opacity="0.6" />
          <ellipse cx="720" cy="850" rx="800" ry="300" fill="#d1d5db" opacity="0.45" />
          <ellipse cx="400" cy="100" rx="400" ry="200" fill="#d1d5db" opacity="0.35" />
          {/* Wave layers — more opaque and overlapping */}
          <path d="M0 500 Q300 300 600 450 T1200 400 T1440 450 V900 H0Z" fill="#e5e7eb" opacity="0.55" />
          <path d="M0 600 Q360 380 720 520 T1440 470 V900 H0Z" fill="#d1d5db" opacity="0.4" />
          <path d="M0 700 Q400 500 800 620 T1440 560 V900 H0Z" fill="#d1d5db" opacity="0.5" />
          <path d="M0 780 Q350 620 700 730 T1440 680 V900 H0Z" fill="#c7cbd1" opacity="0.3" />
        </svg>
      </div>

      {/* Login Card */}
      <div className="relative z-10 w-full max-w-[420px] bg-white rounded-3xl shadow-[0_8px_30px_rgba(0,0,0,0.06)] border border-gray-100 px-8 py-10 sm:px-10 sm:py-12">

        {/* Logo */}
        <div className="flex justify-center mb-6">
          <div className="w-14 h-14 rounded-2xl bg-black flex items-center justify-center shadow-[0_4px_14px_rgba(0,0,0,0.15)]">
            <span className="text-white text-2xl font-bold font-mono">智</span>
          </div>
        </div>

        {/* Title */}
        <h1 className="text-center text-2xl font-bold text-gray-900 tracking-tight mb-1">
          {mode === "login" ? "欢迎回来" : "创建账号"}
        </h1>
        {mode === "register" && (
          <p className="text-center text-sm text-gray-400 mb-8">注册新账号开始使用</p>
        )}

        {/* Error Message */}
        {error && (
          <div className="mb-6 flex items-center gap-2.5 text-sm font-medium text-red-600 bg-red-50 p-3.5 rounded-xl border border-red-100">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Username */}
          <div className="relative">
            <User className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-gray-400" />
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="账号"
              autoComplete="username"
              className="w-full pl-11 pr-4 py-3.5 bg-gray-50 border border-gray-200 rounded-xl text-[15px] text-gray-900 placeholder-gray-400 outline-none focus:border-black focus:ring-2 focus:ring-black/5 transition-all duration-200"
            />
          </div>

          {/* Password */}
          <div className="relative">
            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-gray-400" />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="密码"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              className="w-full pl-11 pr-4 py-3.5 bg-gray-50 border border-gray-200 rounded-xl text-[15px] text-gray-900 placeholder-gray-400 outline-none focus:border-black focus:ring-2 focus:ring-black/5 transition-all duration-200"
            />
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-black hover:bg-gray-900 active:bg-black active:scale-[0.98] text-white py-3.5 rounded-xl font-semibold text-[15px] transition-all duration-200 shadow-[0_4px_10px_rgba(0,0,0,0.1)] hover:shadow-[0_6px_15px_rgba(0,0,0,0.15)] disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center space-x-2 mt-6"
          >
            {loading ? (
              <>
                <RefreshCw className="w-5 h-5 animate-spin" />
                <span>处理中...</span>
              </>
            ) : (
              <span>{mode === "login" ? "登录" : "注册"}</span>
            )}
          </button>
        </form>

        {/* Links Row */}
        <div className="flex items-center justify-between mt-5 text-sm">
          <span className="text-gray-400 cursor-default">忘记密码</span>
          <button
            onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
            className="text-gray-500 hover:text-black transition-colors cursor-pointer font-medium"
          >
            {mode === "login" ? "注册账号" : "返回登录"}
          </button>
        </div>

      </div>
    </div>
  );
}
