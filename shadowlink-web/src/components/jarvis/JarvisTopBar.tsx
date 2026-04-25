// shadowlink-web/src/components/jarvis/JarvisTopBar.tsx
import React, { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Settings as SettingsIcon, BookOpen, Zap } from "lucide-react";
import { useJarvisStore } from "@/stores/jarvisStore";

const MOOD_EMOJI: Record<string, string> = {
  positive: "😊",
  neutral: "😐",
  negative: "😔",
  unknown: "🤷",
};

interface TriggerDef {
  name: string;
  cooldown_minutes: number;
  participants: string[];
}

const TRIGGER_LABELS: Record<string, string> = {
  stress_spike: "⚡ 压力飙升",
  schedule_overload: "📆 日程爆满",
  sleep_poor: "😴 睡眠不足",
  free_window_detected: "🕐 空档出现",
  mood_declining: "🌧 情绪低落",
};

export const JarvisTopBar: React.FC = () => {
  const context = useJarvisStore((s) => s.context);
  const proactiveMessages = useJarvisStore((s) => s.proactiveMessages);
  const unreadCount = proactiveMessages.filter((m) => !m.read).length;

  const [showTriggers, setShowTriggers] = useState(false);
  const [triggers, setTriggers] = useState<TriggerDef[]>([]);
  const [firing, setFiring] = useState(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fetch("/api/v1/jarvis/proactive/triggers")
      .then((r) => (r.ok ? r.json() : []))
      .then(setTriggers)
      .catch(() => {});
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    if (!showTriggers) return;
    const onDocClick = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setShowTriggers(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [showTriggers]);

  const fireTrigger = async (name: string) => {
    setFiring(true);
    try {
      const res = await fetch("/api/v1/jarvis/proactive/fire", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trigger_name: name }),
      });
      const data = await res.json();
      // Add the returned messages directly to the jarvis store for instant visibility
      const addProactiveMessage = useJarvisStore.getState().addProactiveMessage;
      for (const msg of data.messages ?? []) addProactiveMessage(msg);
    } finally {
      setFiring(false);
      setShowTriggers(false);
    }
  };

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

        {/* Divider */}
        <div className="w-px h-5 bg-gray-200" />

        {/* Demo trigger dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            title="Demo: fire a proactive trigger"
            disabled={firing || triggers.length === 0}
            onClick={() => setShowTriggers((s) => !s)}
            className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-gray-600 hover:bg-gray-100 hover:text-gray-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Zap size={14} />
            <span>Demo</span>
          </button>
          {showTriggers && (
            <div
              className="absolute right-0 top-full mt-1 w-48 rounded-lg border border-gray-200 bg-white shadow-lg z-50 py-1"
              style={{ borderColor: "var(--color-border, #e5e7eb)" }}
            >
              <div className="px-3 py-1.5 text-[10px] uppercase tracking-wide text-gray-400 border-b border-gray-100">
                触发 Proactive
              </div>
              {triggers.length === 0 ? (
                <div className="px-3 py-2 text-xs text-gray-400">
                  No triggers available
                </div>
              ) : (
                triggers.map((t) => (
                  <button
                    key={t.name}
                    type="button"
                    disabled={firing}
                    onClick={() => fireTrigger(t.name)}
                    className="w-full text-left px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-100 transition-colors disabled:opacity-50"
                  >
                    {TRIGGER_LABELS[t.name] ?? t.name}
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        {/* Knowledge + Settings quick access */}
        <Link
          to="/knowledge"
          title="知识库"
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
