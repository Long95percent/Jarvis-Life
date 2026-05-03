import React, { useEffect, useMemo, useState } from "react";
import { type ProactiveMessage } from "@/services/jarvisApi";
import { jarvisCareApi, type CareTrendDetail, type CareTrendPoint, type CareTrendsResponse } from "@/services/jarvisCareApi";

type TrendRange = "week" | "month" | "year";
type MetricKey = "mood_score" | "stress_score" | "energy_score" | "sleep_risk_score" | "schedule_pressure_score";

interface Props {
  recentCareMessages?: ProactiveMessage[];
  onOpenMira?: () => void;
  onOpenDetails?: () => void;
  variant?: "full" | "compact";
}

const METRICS: Array<{ key: MetricKey; label: string; color: string; bg: string }> = [
  { key: "mood_score", label: "心情", color: "bg-emerald-500", bg: "bg-emerald-50 text-emerald-800" },
  { key: "stress_score", label: "压力", color: "bg-amber-500", bg: "bg-amber-50 text-amber-800" },
  { key: "energy_score", label: "能量", color: "bg-sky-500", bg: "bg-sky-50 text-sky-800" },
  { key: "sleep_risk_score", label: "睡眠", color: "bg-violet-500", bg: "bg-violet-50 text-violet-800" },
  { key: "schedule_pressure_score", label: "计划压力", color: "bg-rose-500", bg: "bg-rose-50 text-rose-800" },
];

function scoreText(value: number | null | undefined): string {
  return typeof value === "number" ? value.toFixed(1) : "--";
}

function scoreValue(point: CareTrendPoint, metric: MetricKey): number | null {
  const value = point[metric];
  return typeof value === "number" ? value : null;
}

function barHeight(value: number | null | undefined): string {
  const score = typeof value === "number" ? Math.max(0, Math.min(10, value)) : 0;
  return `${Math.max(6, score * 8)}%`;
}

function heatOpacity(value: number | null | undefined): number {
  if (typeof value !== "number") return 0.12;
  return 0.18 + Math.max(0, Math.min(10, value)) * 0.08;
}

function dayLabel(date: string): string {
  const [, month, day] = date.split("-");
  return `${month}/${day}`;
}

function latestWithData(series: CareTrendPoint[]): CareTrendPoint | undefined {
  return [...series].reverse().find((item) => METRICS.some((metric) => typeof item[metric.key] === "number"));
}

function careMessageMatches(message: ProactiveMessage): boolean {
  const trigger = message.trigger || "";
  return message.agent_id === "mira" || trigger.startsWith("care") || trigger.includes("risk") || trigger.includes("overload") || trigger.includes("streak") || trigger.includes("planner_missed");
}

export const CareTrendsPanel: React.FC<Props> = ({
  recentCareMessages = [],
  onOpenMira,
  onOpenDetails,
  variant = "full",
}) => {
  const [range, setRange] = useState<TrendRange>("week");
  const [metric, setMetric] = useState<MetricKey>("stress_score");
  const [data, setData] = useState<CareTrendsResponse | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [dayDetail, setDayDetail] = useState<CareTrendDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [trackingEnabled, setTrackingEnabled] = useState(true);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = async (targetRange = range) => {
    setLoading(true);
    setError("");
    try {
      const [settings, trends] = await Promise.all([
        jarvisCareApi.getCareSettings().catch(() => ({ psychological_tracking_enabled: true })),
        jarvisCareApi.getCareTrends({ range: targetRange }),
      ]);
      setTrackingEnabled(Boolean(settings.psychological_tracking_enabled && trends.tracking_enabled !== false));
      setData(trends);
      setSelectedDate((prev) => prev && trends.details[prev] ? prev : latestWithData(trends.series)?.date ?? trends.series[trends.series.length - 1]?.date ?? null);
      setDayDetail(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "心理中心加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(range); }, [range]);

  const latest = useMemo(() => latestWithData(data?.series ?? []), [data]);
  const selectedDetail = dayDetail ?? (selectedDate && data ? data.details[selectedDate] : null);
  const selectedMetric = METRICS.find((item) => item.key === metric) ?? METRICS[1];
  const careMessages = useMemo(() => recentCareMessages.filter(careMessageMatches).slice(0, 3), [recentCareMessages]);
  const compactStatus = useMemo(() => {
    if (!latest) return "同步中";
    if ((latest.stress_score ?? 0) >= 7 || (latest.energy_score ?? 10) <= 3) {
      return "需关注";
    }
    return "正常";
  }, [latest]);

  const selectDate = async (date: string) => {
    setSelectedDate(date);
    setDayDetail(data?.details[date] ?? null);
    setDetailLoading(true);
    try {
      setDayDetail(await jarvisCareApi.getCareDayDetail(date));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "当天解释加载失败");
    } finally {
      setDetailLoading(false);
    }
  };

  const toggleTracking = async () => {
    setSaving(true);
    try {
      const next = !trackingEnabled;
      const result = await jarvisCareApi.setPsychologicalTracking(next);
      setTrackingEnabled(result.psychological_tracking_enabled);
      await load(range);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "隐私设置保存失败");
    } finally {
      setSaving(false);
    }
  };

  const clearData = async () => {
    if (!window.confirm("确认清除心理中心数据？这会删除情绪、行为、压力信号和每日快照。")) return;
    setSaving(true);
    try {
      await jarvisCareApi.clearCareData();
      await load(range);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "心理数据清除失败");
    } finally {
      setSaving(false);
    }
  };

  if (variant === "compact") {
    return (
      <section className="rounded-[28px] border border-emerald-100 bg-[linear-gradient(180deg,#ffffff,rgba(240,253,250,0.92))] p-5 shadow-sm shadow-emerald-100/70">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-2xl">💗</span>
            <div>
              <h3 className="text-base font-semibold text-slate-800">心理中心</h3>
              <p className="mt-1 text-xs text-slate-400">
                今日状态与最近关怀
              </p>
            </div>
          </div>
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-medium ${
              compactStatus === "正常"
                ? "bg-emerald-100 text-emerald-700"
                : "bg-amber-100 text-amber-700"
            }`}
          >
            {compactStatus}
          </span>
        </div>

        {error ? (
          <div className="mt-4 rounded-2xl bg-red-50 px-3 py-2 text-xs text-red-700">
            {error}
          </div>
        ) : null}

        <div className="mt-4 grid grid-cols-3 gap-3">
          {[
            {
              label: "心情",
              value: scoreText(latest?.mood_score),
              tone: "bg-emerald-50 text-emerald-700",
            },
            {
              label: "压力",
              value: scoreText(latest?.stress_score),
              tone: "bg-amber-50 text-amber-700",
            },
            {
              label: "能量",
              value: scoreText(latest?.energy_score),
              tone: "bg-sky-50 text-sky-700",
            },
          ].map((item) => (
            <div key={item.label} className={`rounded-2xl p-3 ${item.tone}`}>
              <div className="text-[11px] opacity-70">{item.label}</div>
              <div className="mt-1 text-[1.7rem] font-semibold leading-none">
                {item.value}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 rounded-2xl border border-emerald-100 bg-emerald-50/60 p-4 text-sm text-emerald-950">
          <div className="mb-2 font-semibold">最近关怀</div>
          {careMessages.length > 0 ? (
            <div className="space-y-2">
              {careMessages.slice(0, 1).map((message) => (
                <div key={message.id} className="leading-7">
                  • {message.content}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-emerald-700/75">
              当前还没有新的关怀提醒，继续保持现在的节奏就很好。
            </div>
          )}
        </div>

        <div className="mt-4 flex items-center justify-center">
          {onOpenDetails ? (
            <button
              type="button"
              onClick={onOpenDetails}
              className="flex w-full items-center justify-center rounded-2xl border border-indigo-100 bg-indigo-50 px-4 py-3 text-sm font-medium text-indigo-700 transition hover:bg-indigo-100"
            >
              查看详情
            </button>
          ) : null}
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-emerald-100 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-gray-800">心理中心</h3>
          <p className="mt-0.5 text-[11px] text-gray-500">今日状态、趋势、关怀提醒和来源解释</p>
        </div>
        <select value={range} onChange={(event) => setRange(event.target.value as TrendRange)} className="rounded-lg border border-emerald-100 bg-emerald-50 px-2 py-1 text-xs text-emerald-800">
          <option value="week">本周</option>
          <option value="month">本月</option>
          <option value="year">全年</option>
        </select>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {METRICS.map((item) => (
          <button key={item.key} type="button" onClick={() => setMetric(item.key)} className={`rounded-full px-2 py-1 text-[11px] ${metric === item.key ? item.bg : "bg-gray-100 text-gray-600"}`}>{item.label}</button>
        ))}
      </div>

      {latest ? (
        <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
          <div className="rounded-xl bg-emerald-50 p-2 text-emerald-800"><div className="text-[11px] opacity-70">心情</div><div className="text-lg font-semibold">{scoreText(latest.mood_score)}</div></div>
          <div className="rounded-xl bg-amber-50 p-2 text-amber-800"><div className="text-[11px] opacity-70">压力</div><div className="text-lg font-semibold">{scoreText(latest.stress_score)}</div></div>
          <div className="rounded-xl bg-sky-50 p-2 text-sky-800"><div className="text-[11px] opacity-70">能量</div><div className="text-lg font-semibold">{scoreText(latest.energy_score)}</div></div>
        </div>
      ) : <div className="mt-3 rounded-xl bg-gray-50 p-3 text-xs text-gray-500">今天还没有足够信号，正常聊天或完成计划后会自动形成状态。</div>}

      <div className="mt-3 flex items-center gap-2 text-[11px]">
        <button type="button" disabled={saving} onClick={toggleTracking} className={`rounded-lg px-2 py-1 ${trackingEnabled ? "bg-emerald-100 text-emerald-700" : "bg-gray-200 text-gray-600"}`}>{trackingEnabled ? "心理追踪已开启" : "心理追踪已关闭"}</button>
        <button type="button" disabled={saving} onClick={clearData} className="rounded-lg bg-red-50 px-2 py-1 text-red-700">清除心理数据</button>
        {onOpenMira ? <button type="button" onClick={onOpenMira} className="rounded-lg bg-indigo-50 px-2 py-1 text-indigo-700">找 Mira 聊聊</button> : null}
        {loading ? <span className="text-gray-400">加载中...</span> : null}
      </div>

      {!trackingEnabled ? <div className="mt-3 rounded-xl bg-gray-50 p-2 text-xs text-gray-600">心理追踪已关闭：不会继续写入新的情绪、行为和压力信号。</div> : null}
      {error ? <div className="mt-3 rounded-xl bg-red-50 p-2 text-xs text-red-700">{error}</div> : null}

      {careMessages.length > 0 ? (
        <div className="mt-3 rounded-xl border border-emerald-100 bg-emerald-50/60 p-3 text-xs text-emerald-900">
          <div className="mb-1 font-semibold">最近关怀</div>
          <div className="space-y-1.5">
            {careMessages.map((message) => <div key={message.id} className="line-clamp-2">• {message.content}</div>)}
          </div>
        </div>
      ) : null}

      {range === "year" ? (
        <div className="mt-3 grid max-h-40 grid-cols-26 gap-1 overflow-y-auto rounded-xl border border-gray-100 bg-gray-50 p-2">
          {(data?.series ?? []).map((item) => {
            const active = item.date === selectedDate;
            return <button key={item.date} type="button" title={`${item.date} ${selectedMetric.label} ${scoreText(scoreValue(item, metric))}`} onClick={() => void selectDate(item.date)} className={`h-3 w-3 rounded-sm ${active ? "ring-2 ring-emerald-500" : ""} ${selectedMetric.color}`} style={{ opacity: heatOpacity(scoreValue(item, metric)) }} />;
          })}
        </div>
      ) : (
        <div className="mt-3 flex h-28 items-end gap-1 overflow-x-auto rounded-xl border border-gray-100 bg-gray-50 px-2 py-2">
          {(data?.series ?? []).map((item) => {
            const active = item.date === selectedDate;
            const value = scoreValue(item, metric);
            return (
              <button key={item.date} type="button" title={`${item.date} ${selectedMetric.label} ${scoreText(value)}`} onClick={() => void selectDate(item.date)} className={`flex min-w-[20px] flex-col items-center justify-end gap-1 rounded-md px-0.5 pb-1 ${active ? "bg-emerald-100" : "hover:bg-white"}`}>
                <span className={`w-3 rounded-full ${selectedMetric.color}`} style={{ height: barHeight(value), opacity: typeof value === "number" ? 0.85 : 0.18 }} />
                {range === "week" ? <span className="text-[9px] text-gray-400">{dayLabel(item.date).slice(3)}</span> : null}
              </button>
            );
          })}
        </div>
      )}
      <div className="mt-1 text-[11px] text-gray-500">当前指标：{selectedMetric.label}；点击日期查看来源解释。</div>

      {selectedDetail ? (
        <div className="mt-3 max-h-56 overflow-y-auto rounded-xl border border-gray-100 bg-gray-50 p-3 text-xs text-gray-700">
          <div className="flex items-center justify-between">
            <div className="font-semibold text-gray-800">{dayLabel(selectedDetail.snapshot.date)} 来源解释</div>
            <div className="text-gray-500">{selectedMetric.label} {scoreText(scoreValue(selectedDetail.snapshot, metric))}</div>
          </div>
          <div className="mt-2 space-y-1.5">
            {(selectedDetail.explanations.length ? selectedDetail.explanations : [selectedDetail.snapshot.summary || "暂无解释数据。"]).slice(0, 6).map((item, index) => <div key={index}>• {item}</div>)}
          </div>
          {detailLoading ? <div className="mt-2 text-[11px] text-gray-400">正在刷新当天解释...</div> : null}
          {selectedDetail.stress_signals.length > 0 ? <div className="mt-2 text-[11px] text-gray-500">压力信号：{selectedDetail.stress_signals.map((item) => item.signal_type).join("、")}</div> : null}
          {selectedDetail.behavior_observations.length > 0 ? <div className="mt-1 text-[11px] text-gray-500">行为信号：{selectedDetail.behavior_observations.slice(0, 5).map((item) => item.observation_type).join("、")}</div> : null}
          {selectedDetail.emotion_observations?.length > 0 ? <div className="mt-1 text-[11px] text-gray-500">情绪证据：{selectedDetail.emotion_observations.slice(0, 5).map((item) => item.primary_emotion).join("、")}</div> : null}
          {selectedDetail.care_triggers?.length > 0 ? <div className="mt-1 text-[11px] text-gray-500">关怀触发：{selectedDetail.care_triggers.slice(0, 5).map((item) => `${item.trigger_type}/${item.severity}`).join("、")}</div> : null}
          {selectedDetail.positive_events?.length > 0 ? <div className="mt-1 text-[11px] text-emerald-700">正向事件：{selectedDetail.positive_events.slice(0, 3).join("、")}</div> : null}
          {selectedDetail.negative_events?.length > 0 ? <div className="mt-1 text-[11px] text-amber-700">负向事件：{selectedDetail.negative_events.slice(0, 3).join("、")}</div> : null}
          {selectedDetail.snapshot.risk_flags.length > 0 ? <div className="mt-2 flex flex-wrap gap-1">{selectedDetail.snapshot.risk_flags.slice(0, 8).map((flag) => <span key={flag} className="rounded-full bg-white px-2 py-0.5 text-[11px] text-gray-600">{flag}</span>)}</div> : null}
        </div>
      ) : null}
    </section>
  );
};
