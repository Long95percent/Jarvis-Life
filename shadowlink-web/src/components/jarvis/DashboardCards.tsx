import React, { useEffect, useMemo, useState } from "react";
import { jarvisScheduleApi } from "@/services/jarvisScheduleApi";
import {
  jarvisSettingsApi,
  type JarvisTimeContext,
  type UserProfile,
} from "@/services/jarvisSettingsApi";
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

export interface JarvisHeaderSnapshot {
  displayName: string;
  greeting: string;
  subtitle: string;
  timeLabel: string;
  dateLabel: string;
  weatherIcon: string;
  weatherLabel: string;
  temperatureLabel: string;
  locationLabel: string;
  loading: boolean;
}

const MOOD_EMOJI: Record<string, string> = {
  positive: "😊",
  neutral: "😌",
  negative: "😟",
  unknown: "🤖",
};

export function decodeWeather(code: number | undefined): {
  icon: string;
  label: string;
} {
  if (code === undefined) return { icon: "🌙", label: "天气同步中" };
  if (code === 0) return { icon: "☀️", label: "晴朗" };
  if (code >= 1 && code <= 3) return { icon: "⛅", label: "晴间多云" };
  if (code === 45 || code === 48) return { icon: "🌫️", label: "雾" };
  if ((code >= 51 && code <= 57) || (code >= 61 && code <= 67)) {
    return { icon: "🌧️", label: "有雨" };
  }
  if (code >= 71 && code <= 77) return { icon: "❄️", label: "有雪" };
  if (code >= 80 && code <= 82) return { icon: "🌦️", label: "阵雨" };
  if (code >= 85 && code <= 86) return { icon: "🌨️", label: "阵雪" };
  if (code >= 95) return { icon: "⛈️", label: "雷雨" };
  return { icon: "🌤️", label: "天气同步中" };
}

function formatEventTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function buildGreeting(date: Date, name: string): string {
  const hour = date.getHours();
  if (hour < 5) return `夜深了，${name}`;
  if (hour < 11) return `早上好，${name}`;
  if (hour < 14) return `中午好，${name}`;
  if (hour < 18) return `下午好，${name}`;
  return `晚上好，${name}`;
}

function buildSubtitle(
  now: Date,
  scheduleCount: number,
  stressLevel: number | null,
): string {
  const hour = now.getHours();
  if (stressLevel !== null && stressLevel >= 7) {
    return "今天负荷有点高，我们可以先把最重要的一件事理顺。";
  }
  if (scheduleCount >= 4) {
    return "今天安排不少，优先把节奏和缓冲时间照顾好。";
  }
  if (hour < 11) {
    return "适合先定下今天的节奏，再进入重点事项。";
  }
  if (hour < 18) {
    return "状态正在推进中，适合把当下最重要的事往前推一步。";
  }
  return "今晚状态不错，适合规划明天或做一个轻松收尾。";
}

export function useJarvisHeaderSnapshot(): JarvisHeaderSnapshot {
  const context = useJarvisStore((state) => state.context);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [timeContext, setTimeContext] = useState<JarvisTimeContext | null>(null);
  const [weather, setWeather] = useState<WeatherSnapshot | null>(null);
  const [now, setNow] = useState<Date>(new Date());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

    const loadHeader = async () => {
      try {
        const [timeData, lifeData, profileData] = await Promise.all([
          jarvisSettingsApi.getTimeContext(browserTimezone),
          jarvisScheduleApi.getLocalLife().catch(() => null),
          jarvisSettingsApi.getProfile().catch(() => null),
        ]);

        if (cancelled) return;
        setTimeContext(timeData);
        setNow(new Date(timeData.local_iso));
        setWeather(lifeData?.weather ?? null);
        setProfile(profileData);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void loadHeader();
    window.addEventListener("jarvis:profile-updated", loadHeader);
    return () => {
      cancelled = true;
      window.removeEventListener("jarvis:profile-updated", loadHeader);
    };
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNow((current) => new Date(current.getTime() + 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  const dateSource = timeContext ? now : new Date();
  const displayName = profile?.name?.trim() || "朋友";
  const activeEvents = context?.active_events ?? [];
  const stressLevel =
    typeof context?.stress_level === "number" ? context.stress_level : null;
  const weatherMeta = decodeWeather(weather?.weather_code);
  const timezone = timeContext?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone;

  const timeLabel = new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: timezone,
  }).format(dateSource);

  const dateLabel = new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "short",
    timeZone: timezone,
  }).format(dateSource);

  const temperatureLabel =
    weather && weather.temperature_c !== undefined
      ? `${weather.temperature_c.toFixed(0)}°`
      : "--";

  return {
    displayName,
    greeting: buildGreeting(dateSource, displayName),
    subtitle: buildSubtitle(dateSource, activeEvents.length, stressLevel),
    timeLabel,
    dateLabel,
    weatherIcon: weatherMeta.icon,
    weatherLabel: weatherMeta.label,
    temperatureLabel,
    locationLabel:
      timeContext?.location_label || profile?.location?.label || "位置未设置",
    loading,
  };
}

const LifePulseCard: React.FC = () => {
  const context = useJarvisStore((state) => state.context);

  if (!context) {
    return (
      <div className="rounded-[26px] border border-white/70 bg-white/90 p-5 shadow-sm">
        <div className="text-sm font-semibold text-slate-700">生活状态</div>
        <div className="mt-3 text-sm text-slate-400">同步中...</div>
      </div>
    );
  }

  return (
    <div className="rounded-[26px] border border-white/70 bg-white/90 p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-700">生活状态</div>
          <div className="mt-1 text-xs text-slate-400">
            压力 {context.stress_level.toFixed(1)} / 日程 {context.schedule_density.toFixed(1)}
          </div>
        </div>
        <div className="text-2xl">{MOOD_EMOJI[context.mood_trend] ?? MOOD_EMOJI.unknown}</div>
      </div>
    </div>
  );
};

const WeatherStatusCard: React.FC = () => {
  const snapshot = useJarvisHeaderSnapshot();

  return (
    <div className="rounded-[26px] border border-white/70 bg-white/90 p-5 shadow-sm">
      <div className="text-sm font-semibold text-slate-700">天气</div>
      <div className="mt-3 flex items-center gap-3">
        <span className="text-3xl">{snapshot.weatherIcon}</span>
        <div className="min-w-0">
          <div className="text-lg font-semibold text-slate-900">
            {snapshot.temperatureLabel}
          </div>
          <div className="text-xs text-slate-500">{snapshot.weatherLabel}</div>
        </div>
      </div>
    </div>
  );
};

const ClockStatusCard: React.FC = () => {
  const snapshot = useJarvisHeaderSnapshot();

  return (
    <div className="rounded-[26px] border border-white/70 bg-white/90 p-5 shadow-sm">
      <div className="text-sm font-semibold text-slate-700">本地时间</div>
      <div className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
        {snapshot.timeLabel}
      </div>
      <div className="mt-1 text-xs text-slate-500">{snapshot.dateLabel}</div>
    </div>
  );
};

export const TodayScheduleCard: React.FC<DashboardCardsProps> = ({
  onOpenCalendar,
}) => {
  const context = useJarvisStore((state) => state.context);
  const todayKey = new Date().toLocaleDateString("sv-SE");
  const events = useMemo(
    () => [...(context?.active_events ?? [])]
      .filter((event) => new Date(event.start).toLocaleDateString("sv-SE") === todayKey)
      .sort((left, right) => {
        return +new Date(left.start) - +new Date(right.start);
      }),
    [context?.active_events, todayKey],
  );

  return (
    <section className="rounded-[28px] border border-white/70 bg-white/95 p-5 shadow-sm shadow-slate-200/60">
      <div className="flex items-start gap-3">
        <div>
          <div className="text-base font-semibold text-slate-800">今日安排</div>
          <div className="mt-1 text-xs text-slate-400">
            {events.length > 0 ? `已同步 ${events.length} 项安排` : "今天暂时还没有安排"}
          </div>
        </div>
      </div>

      {events.length === 0 ? (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-5 text-sm text-slate-400">
          还没有已确认日程，可以让 Alfred 或 Maxwell 帮你安排一天。
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          {events.slice(0, 5).map((event, index) => (
            <div key={event.id ?? `${event.title}-${index}`} className="flex gap-3">
              <span className="mt-2 h-2.5 w-2.5 rounded-full bg-indigo-400" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium text-slate-800">
                    {formatEventTime(event.start)}
                  </span>
                  <span className="text-xs text-slate-400">
                    {event.end ? formatEventTime(event.end) : ""}
                  </span>
                </div>
                <div className="mt-1 truncate text-sm text-slate-600">
                  {event.title}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={onOpenCalendar}
        className="mt-5 flex w-full items-center justify-center gap-2 rounded-2xl border border-indigo-100 bg-indigo-50 px-4 py-3 text-sm font-medium text-indigo-700 transition hover:bg-indigo-100"
      >
        查看日程
      </button>
    </section>
  );
};

export const DashboardCards: React.FC<DashboardCardsProps> = ({
  onOpenCalendar,
}) => (
  <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
    <ClockStatusCard />
    <TodayScheduleCard onOpenCalendar={onOpenCalendar} />
    <LifePulseCard />
    <WeatherStatusCard />
  </div>
);
