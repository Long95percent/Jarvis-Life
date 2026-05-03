// shadowlink-web/src/components/jarvis/JarvisTopBar.tsx
import React from "react";
import { Link } from "react-router-dom";
import { Settings as SettingsIcon, BookOpen } from "lucide-react";
import { useJarvisStore } from "@/stores/jarvisStore";

const MOOD_EMOJI: Record<string, string> = {
  positive: "😊",
  neutral: "😐",
  negative: "😔",
  unknown: "🤷",
};

export const JarvisTopBar: React.FC = () => {
  const context = useJarvisStore((s) => s.context);
  const proactiveMessages = useJarvisStore((s) => s.proactiveMessages);
  const unreadCount = proactiveMessages.filter((m) => !m.read).length;

  return (
    <header
      className="flex items-center justify-between px-6 py-3 border-b"
      style={{
        borderColor: "var(--color-border, #e5e7eb)",
        background:
          "linear-gradient(90deg, color-mix(in srgb, var(--color-primary) 8%, white), white 55%)",
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3">
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center text-lg shadow-sm"
          style={{
            backgroundColor: "var(--color-primary)",
            color: "white",
          }}
        >
          🎩
        </div>
        <div>
          <div className="font-semibold text-[var(--color-text,#1f2937)] leading-none">
            Jarvis
          </div>
          <div className="text-[11px] text-gray-500 leading-none mt-1">
            · Be IronMan
          </div>
        </div>
      </div>

      {/* Tagline (centered) */}
      <div className="flex-1 flex justify-center mx-6">
        <span className="text-xs text-gray-500 italic">
          你的多智能体生活管家 · 选一个场景，召唤专家圆桌
        </span>
      </div>

      {/* Life status compact indicator */}
      <div className="flex items-center gap-4 text-sm">
        {context ? (
          <>
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] text-gray-500">压力</span>
              <span
                className="font-semibold text-sm"
                style={{
                  color: context.stress_level > 7 ? "#EF4444" : "#6C63FF",
                }}
              >
                {context.stress_level.toFixed(1)}
              </span>
            </div>
            <span className="text-xl" title={`Mood: ${context.mood_trend}`}>
              {MOOD_EMOJI[context.mood_trend] ?? "🤷"}
            </span>
          </>
        ) : (
          <span className="text-xs text-gray-400">加载中…</span>
        )}
        <div className="relative">
          <span className="text-xl">🔔</span>
          {unreadCount > 0 && (
            <span
              className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full text-[10px] font-semibold text-white flex items-center justify-center"
              style={{ backgroundColor: "#EF4444" }}
            >
              {unreadCount}
            </span>
          )}
        </div>

        {/* Knowledge + Settings quick access */}
        <Link
          to="/knowledge"
          title="个人画像"
          className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-800 transition-colors"
        >
          <BookOpen size={18} />
        </Link>
        <Link
          to="/settings"
          title="设置"
          className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-800 transition-colors"
        >
          <SettingsIcon size={18} />
        </Link>
      </div>
    </header>
  );
};
