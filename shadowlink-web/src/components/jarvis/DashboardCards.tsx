import React, { useEffect, useState } from "react";
import { useJarvisStore } from "@/stores/jarvisStore";

interface DashboardCardsProps {
  onOpenCalendar?: () => void;
}

interface WeatherSnapshot {
  temperature_c?: number;
  weather_code?: number;
  wind_kmh?: number;
  precipitation_mm?: number;
  is_good_weather?: boolean;
  error?: string;
}

const MOOD_EMOJI: Record<string, string> = {
  positive: "😊",
  neutral: "😐",
  negative: "😟",
  unknown: "🤷",
};

function decodeWeather(code: number | undefined): { icon: string; label: string } {
  if (code === undefined) return { icon: "🌤️", label: "未知" };
  if (code === 0) return { icon: "☀️", label: "晴" };
  if (code >= 1 && code <= 3) return { icon: "⛅", label: "多云" };
  if (code === 45 || code === 48) return { icon: "🌫️", label: "雾" };
  if ((code >= 51 && code <= 57) || (code >= 61 && code <= 67)) return { icon: "🌧️", label: "雨" };
  if (code >= 71 && code <= 77) return { icon: "❄️", label: "雪" };
  if (code >= 80 && code <= 82) return { icon: "🌦️", label: "阵雨" };
  if (code >= 85 && code <= 86) return { icon: "🌨️", label: "阵雪" };
  if (code >= 95) return { icon: "⛈️", label: "雷雨" };
  return { icon: "🌤️", label: "未知" };
}

function formatEventTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

const ScheduleCard: React.FC<{ onOpenCalendar?: () => void }> = ({ onOpenCalendar }) => {
  const context = useJarvisStore((s) => s.context);
  const events = context?.active_events ?? [];

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-gray-700">📅 今日日程</h3>
        <button
          type="button"
          className="text-[10px] text-[var(--color-primary)] hover:underline"
          onClick={onOpenCalendar}
        >
          打开日历 · {events.length} 项
        </button>
      </div>
      {events.length === 0 ? (
        <p className="text-xs text-gray-400 py-3 text-center">今天暂无安排</p>
      ) : (
        <ul className="space-y-1.5 max-h-32 overflow-y-auto">
          {events.slice(0, 5).map((event, index) => (
            <li key={event.id ?? index} className="flex items-center gap-2 text-xs text-gray-700">
              <span className="w-1 h-1 rounded-full bg-[var(--color-primary)] flex-shrink-0" />
              <span className="truncate flex-1">{event.title}</span>
              <span className="text-gray-400 text-[10px] flex-shrink-0">
                {formatEventTime(event.start)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

const LifeStateCard: React.FC = () => {
  const context = useJarvisStore((s) => s.context);

  if (!context) {
    return (
      <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">💓 生活状态</h3>
        <p className="text-xs text-gray-400 text-center py-3">加载中…</p>
      </div>
    );
  }

  const metrics: Array<{ label: string; value: number; color: string }> = [
    { label: "压力", value: context.stress_level, color: context.stress_level > 7 ? "#EF4444" : "#6C63FF" },
    { label: "日程", value: context.schedule_density, color: "#3B82F6" },
    { label: "睡眠", value: context.sleep_quality, color: "#10B981" },
  ];

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700">💓 生活状态</h3>
        <span className="text-xl" title={context.mood_trend}>
          {MOOD_EMOJI[context.mood_trend] ?? "🤷"}
        </span>
      </div>
      <div className="space-y-2">
        {metrics.map((metric) => {
          const percentage = Math.min(100, (metric.value / 10) * 100);
          return (
            <div key={metric.label}>
              <div className="flex justify-between text-[10px] text-gray-500 mb-1">
                <span>{metric.label}</span>
                <span>{metric.value.toFixed(1)}</span>
              </div>
              <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${percentage}%`, backgroundColor: metric.color }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const WeatherCard: React.FC = () => {
  const [weather, setWeather] = useState<WeatherSnapshot | null>(null);
  const [locationLabel, setLocationLabel] = useState("");
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [lifeRes, profileRes] = await Promise.all([
          fetch("/api/v1/jarvis/local-life"),
          fetch("/api/v1/jarvis/profile"),
        ]);
        if (!lifeRes.ok) throw new Error(`HTTP ${lifeRes.status}`);
        const lifeData = await lifeRes.json();
        if (!cancelled) {
          setWeather(lifeData.weather ?? null);
          if (profileRes.ok) {
            const profile = await profileRes.json();
            setLocationLabel(profile?.location?.label ?? "");
          }
        }
      } catch (err) {
        if (!cancelled) setErrorMsg(String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const meta = decodeWeather(weather?.weather_code);
  const hasData = weather != null && !weather.error && weather.temperature_c !== undefined;

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">🌤️ 天气</h3>
      {loading ? (
        <p className="text-xs text-gray-400 py-3 text-center">加载中…</p>
      ) : errorMsg ? (
        <p className="text-xs text-gray-400 py-3 text-center" title={errorMsg}>
          天气获取失败
        </p>
      ) : !hasData ? (
        <p className="text-xs text-gray-400 py-3 text-center">
          {weather?.error ? "天气源暂不可用" : "天气接入中"}
        </p>
      ) : (
        <div className="flex items-center gap-3">
          <span className="text-3xl">{meta.icon}</span>
          <div className="min-w-0">
            <div className="text-sm font-semibold text-gray-800">
              {weather!.temperature_c!.toFixed(0)}° · {meta.label}
            </div>
            <div className="text-[11px] text-gray-500 truncate">
              {locationLabel || "位置未设置"}
              {weather!.wind_kmh !== undefined ? ` · 风 ${weather!.wind_kmh.toFixed(0)}km/h` : ""}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export const DashboardCards: React.FC<DashboardCardsProps> = ({ onOpenCalendar }) => (
  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
    <ScheduleCard onOpenCalendar={onOpenCalendar} />
    <LifeStateCard />
    <WeatherCard />
  </div>
);
