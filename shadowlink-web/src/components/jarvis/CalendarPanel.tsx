import React, { useEffect, useMemo, useState } from "react";
import { useJarvisStore } from "@/stores/jarvisStore";
import { jarvisApi, type CalendarEvent, type PendingAction } from "@/services/jarvisApi";

interface Props { open: boolean; onClose: () => void }
type ViewMode = "day" | "week" | "month";

interface EventForm {
  title: string; date: string; startTime: string; endTime: string;
  location: string; notes: string; stress_weight: number; route_required: boolean;
}

const HOUR_ROWS = Array.from({ length: 24 }, (_, hour) => hour);
const WEEKDAY_LABELS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

const pad = (value: number) => String(value).padStart(2, "0");
const startOfDay = (date: Date) => { const d = new Date(date); d.setHours(0, 0, 0, 0); return d; };
const addDays = (date: Date, days: number) => { const d = new Date(date); d.setDate(d.getDate() + days); return d; };
const addMonths = (date: Date, months: number) => { const d = new Date(date); d.setMonth(d.getMonth() + months); return d; };
const startOfWeek = (date: Date) => addDays(startOfDay(date), -startOfDay(date).getDay());
const startOfMonth = (date: Date) => new Date(date.getFullYear(), date.getMonth(), 1);
const endOfMonthGrid = (date: Date) => addDays(startOfWeek(new Date(date.getFullYear(), date.getMonth() + 1, 0)), 7);
const toDateInput = (date: Date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
const toTimeInput = (date: Date) => `${pad(date.getHours())}:${pad(date.getMinutes())}`;
const isoFromLocal = (date: string, time: string) => new Date(`${date}T${time}:00`).toISOString();
const textArg = (value: unknown, fallback = "") => typeof value === "string" ? value : fallback;
const sameDay = (a: Date, b: Date) => startOfDay(a).getTime() === startOfDay(b).getTime();

function formatRangeTitle(date: Date, mode: ViewMode): string {
  if (mode === "day") return date.toLocaleDateString("zh-CN", { year: "numeric", month: "long", day: "numeric", weekday: "long" });
  if (mode === "week") {
    const start = startOfWeek(date); const end = addDays(start, 6);
    return `${start.toLocaleDateString("zh-CN", { month: "short", day: "numeric" })} - ${end.toLocaleDateString("zh-CN", { month: "short", day: "numeric" })}`;
  }
  return date.toLocaleDateString("zh-CN", { year: "numeric", month: "long" });
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function minutesFromStart(iso: string, dayStart: Date): number {
  const value = new Date(iso).getTime() - dayStart.getTime();
  return Math.max(0, Math.min(24 * 60, Math.round(value / 60000)));
}

function emptyForm(date: Date): EventForm {
  const now = new Date(); const selectedToday = sameDay(date, now);
  const start = selectedToday ? new Date(now) : new Date(date);
  start.setMinutes(0, 0, 0); if (selectedToday) start.setHours(now.getHours() + 1);
  const end = new Date(start); end.setHours(start.getHours() + 1);
  return { title: "", date: toDateInput(date), startTime: toTimeInput(start), endTime: toTimeInput(end), location: "", notes: "", stress_weight: 1, route_required: false };
}

function formFromEvent(event: CalendarEvent): EventForm {
  const start = new Date(event.start); const end = new Date(event.end);
  return { title: event.title, date: toDateInput(start), startTime: toTimeInput(start), endTime: toTimeInput(end), location: event.location ?? "", notes: event.notes ?? "", stress_weight: event.stress_weight ?? 1, route_required: Boolean(event.route_required) };
}

function formFromPending(item: PendingAction): EventForm {
  const args = item.arguments ?? {}; const start = textArg(args.start) ? new Date(textArg(args.start)) : new Date(); const end = textArg(args.end) ? new Date(textArg(args.end)) : addDays(start, 0);
  if (!textArg(args.end)) end.setHours(start.getHours() + 1);
  return { title: textArg(args.title, item.title), date: toDateInput(start), startTime: toTimeInput(start), endTime: toTimeInput(end), location: textArg(args.location), notes: textArg(args.notes), stress_weight: Number(args.stress_weight ?? 1), route_required: Boolean(args.route_required) };
}

function eventSource(event: CalendarEvent): string {
  if (event.source_agent) return `来自 ${event.source_agent}`;
  if (event.source === "agent_pending_confirmation") return "Agent 建议，用户确认";
  if (event.source === "user_ui") return "用户创建";
  return event.source ?? "未知来源";
}

function eventsForDay(events: CalendarEvent[], date: Date): CalendarEvent[] {
  return events.filter((event) => sameDay(new Date(event.start), date)).sort((a, b) => +new Date(a.start) - +new Date(b.start));
}

export const CalendarPanel: React.FC<Props> = ({ open, onClose }) => {
  const addCalendarEvent = useJarvisStore((s) => s.addCalendarEvent);
  const updateCalendarEvent = useJarvisStore((s) => s.updateCalendarEvent);
  const deleteCalendarEvent = useJarvisStore((s) => s.deleteCalendarEvent);

  const [mode, setMode] = useState<ViewMode>("day");
  const [currentDate, setCurrentDate] = useState(() => startOfDay(new Date()));
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [pendingActions, setPendingActions] = useState<PendingAction[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const [editing, setEditing] = useState<CalendarEvent | null>(null);
  const [editingPending, setEditingPending] = useState<PendingAction | null>(null);
  const [form, setForm] = useState<EventForm>(() => emptyForm(new Date()));

  const range = useMemo(() => {
    if (mode === "day") { const start = startOfDay(currentDate); return { start, end: addDays(start, 1) }; }
    if (mode === "week") { const start = startOfWeek(currentDate); return { start, end: addDays(start, 7) }; }
    const start = startOfWeek(startOfMonth(currentDate)); return { start, end: endOfMonthGrid(currentDate) };
  }, [currentDate, mode]);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [items, pending] = await Promise.all([
        jarvisApi.listCalendarEvents(24, { start: range.start.toISOString(), end: range.end.toISOString() }),
        jarvisApi.listPendingActions("pending"),
      ]);
      setEvents(items); setPendingActions(pending);
    } finally { setLoading(false); }
  };

  useEffect(() => {
    if (!open) return;
    loadAll(); setForm(emptyForm(currentDate)); setSelected(null); setEditing(null); setEditingPending(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, range.start.getTime(), range.end.getTime()]);

  if (!open) return null;

  const shiftRange = (delta: number) => {
    if (mode === "day") setCurrentDate((d) => addDays(d, delta));
    else if (mode === "week") setCurrentDate((d) => addDays(d, delta * 7));
    else setCurrentDate((d) => addMonths(d, delta));
  };

  const payloadFromForm = () => ({ title: form.title.trim(), start: isoFromLocal(form.date, form.startTime), end: isoFromLocal(form.date, form.endTime), stress_weight: form.stress_weight, location: form.location.trim() || null, notes: form.notes.trim() || null, route_required: form.route_required });
  const saveForm = async () => {
    const payload = payloadFromForm(); if (!payload.title) return;
    if (editingPending) { await jarvisApi.updatePendingAction(editingPending.id, { title: payload.title, arguments: { ...editingPending.arguments, ...payload } }); setEditingPending(null); }
    else if (editing?.id) { await updateCalendarEvent(editing.id, { ...payload, source: "user_ui", source_agent: null, created_reason: "用户手动修改日程", status: editing.status ?? "confirmed" }); setEditing(null); setSelected(null); }
    else await addCalendarEvent({ ...payload, source: "user_ui", source_agent: null, created_reason: "用户手动创建日程", status: "confirmed" });
    setForm(emptyForm(currentDate)); await loadAll();
  };
  const confirmPending = async (item: PendingAction) => { await jarvisApi.confirmPendingAction(item.id); await loadAll(); };
  const cancelPending = async (item: PendingAction) => { await jarvisApi.cancelPendingAction(item.id); await loadAll(); };
  const editPending = (item: PendingAction) => { setEditingPending(item); setEditing(null); setSelected(null); setForm(formFromPending(item)); };
  const startEdit = (event: CalendarEvent) => { setEditing(event); setEditingPending(null); setSelected(event); setForm(formFromEvent(event)); };
  const markCompleted = async (event: CalendarEvent) => { if (!event.id) return; await updateCalendarEvent(event.id, { status: event.status === "completed" ? "confirmed" : "completed" }); await loadAll(); setSelected(null); };
  const removeEvent = async (event: CalendarEvent) => { if (!event.id || !confirm(`删除日程「${event.title}」？`)) return; await deleteCalendarEvent(event.id); await loadAll(); setSelected(null); setEditing(null); };

  const renderDayTimeline = (date: Date, dayEvents: CalendarEvent[]) => (
    <div className="relative rounded-2xl border border-gray-200 bg-white overflow-hidden min-h-[1344px]">
      {HOUR_ROWS.map((hour) => <div key={hour} className="h-14 border-b border-gray-100 flex"><div className="w-14 flex-shrink-0 px-2 pt-1 text-[10px] text-gray-400 text-right">{pad(hour)}:00</div><div className="flex-1" /></div>)}
      <div className="absolute left-16 right-3 top-0 bottom-0">{dayEvents.map((event) => { const top = (minutesFromStart(event.start, startOfDay(date)) / 60) * 56; const height = Math.max(34, ((minutesFromStart(event.end, startOfDay(date)) - minutesFromStart(event.start, startOfDay(date))) / 60) * 56); const done = event.status === "completed"; return <button key={event.id ?? `${event.title}-${event.start}`} className={`absolute left-0 right-0 rounded-xl border px-3 py-2 text-left shadow-sm ${done ? "border-gray-200 bg-gray-100 text-gray-400 line-through" : "border-blue-200 bg-blue-50 hover:bg-blue-100"}`} style={{ top, height }} onClick={() => setSelected(event)}><div className="text-xs font-semibold truncate">{event.title}</div><div className="text-[11px] mt-0.5">{formatTime(event.start)} - {formatTime(event.end)}</div><div className="text-[10px] truncate">{eventSource(event)}</div></button>; })}</div>
    </div>
  );

  const weekDays = Array.from({ length: 7 }, (_, index) => addDays(startOfWeek(currentDate), index));
  const monthDays = Array.from({ length: Math.round((range.end.getTime() - range.start.getTime()) / 86400000) }, (_, index) => addDays(range.start, index));

  return (
    <div className="fixed inset-0 z-40 flex"><button type="button" aria-label="关闭日历遮罩" className="flex-1 bg-black/20" onClick={onClose} />
      <aside className="w-full max-w-[860px] h-full bg-white shadow-2xl border-l border-gray-200 flex flex-col">
        <header className="px-5 py-4 border-b border-gray-100 flex items-center justify-between"><div><h2 className="text-base font-semibold text-gray-900">日程日历</h2><p className="text-xs text-gray-500 mt-0.5">日/周/月视图，支持增删改、划掉完成和待确认安排。</p></div><button className="text-sm text-gray-500 hover:text-gray-800" onClick={onClose}>关闭</button></header>
        <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between gap-3"><button className="px-3 py-1.5 rounded-lg border border-gray-200 text-sm hover:bg-gray-50" onClick={() => shiftRange(-1)}>上一{mode === "day" ? "天" : mode === "week" ? "周" : "月"}</button><div className="text-center"><div className="text-sm font-semibold text-gray-800">{formatRangeTitle(currentDate, mode)}</div><button className="text-xs text-[var(--color-primary)]" onClick={() => setCurrentDate(startOfDay(new Date()))}>回到今天</button></div><button className="px-3 py-1.5 rounded-lg border border-gray-200 text-sm hover:bg-gray-50" onClick={() => shiftRange(1)}>下一{mode === "day" ? "天" : mode === "week" ? "周" : "月"}</button></div>
        <div className="px-5 py-2 border-b border-gray-100 flex gap-2">{(["day", "week", "month"] as ViewMode[]).map((item) => <button key={item} className={`px-3 py-1.5 rounded-lg text-xs border ${mode === item ? "bg-[var(--color-primary)] text-white border-transparent" : "border-gray-200 text-gray-600"}`} onClick={() => setMode(item)}>{item === "day" ? "日视图" : item === "week" ? "周视图" : "月视图"}</button>)}</div>
        <div className="grid grid-cols-[1fr_280px] min-h-0 flex-1"><main className="overflow-y-auto px-5 py-4 bg-gray-50/60">{loading ? <div className="py-10 text-center text-sm text-gray-400">正在加载日程…</div> : mode === "day" ? renderDayTimeline(currentDate, eventsForDay(events, currentDate)) : mode === "week" ? <div className="grid grid-cols-7 gap-2">{weekDays.map((day) => <div key={day.toISOString()} className={`rounded-2xl border bg-white p-2 min-h-72 ${sameDay(day, new Date()) ? "border-blue-300" : "border-gray-200"}`}><button className="text-xs font-semibold text-gray-700 mb-2" onClick={() => { setCurrentDate(day); setMode("day"); }}>{WEEKDAY_LABELS[day.getDay()]} {day.getMonth() + 1}/{day.getDate()}</button><div className="space-y-1">{eventsForDay(events, day).map((event) => <button key={event.id ?? event.start} className={`w-full rounded-lg px-2 py-1 text-left text-[11px] ${event.status === "completed" ? "bg-gray-100 text-gray-400 line-through" : "bg-blue-50 text-blue-800"}`} onClick={() => setSelected(event)}>{formatTime(event.start)} {event.title}</button>)}</div></div>)}</div> : <div className="grid grid-cols-7 gap-2">{WEEKDAY_LABELS.map((label) => <div key={label} className="text-center text-xs font-semibold text-gray-400">{label}</div>)}{monthDays.map((day) => { const dayEvents = eventsForDay(events, day); const inMonth = day.getMonth() === currentDate.getMonth(); return <div key={day.toISOString()} className={`rounded-2xl border bg-white p-2 min-h-28 ${sameDay(day, new Date()) ? "border-blue-300" : "border-gray-200"} ${inMonth ? "" : "opacity-45"}`}><button className="text-xs font-semibold text-gray-700" onClick={() => { setCurrentDate(day); setMode("day"); }}>{day.getDate()}</button><div className="mt-1 space-y-1">{dayEvents.slice(0, 3).map((event) => <button key={event.id ?? event.start} className={`block w-full truncate rounded px-1.5 py-0.5 text-left text-[10px] ${event.status === "completed" ? "bg-gray-100 text-gray-400 line-through" : "bg-blue-50 text-blue-800"}`} onClick={() => setSelected(event)}>{event.title}</button>)}{dayEvents.length > 3 && <div className="text-[10px] text-gray-400">+{dayEvents.length - 3} 项</div>}</div></div>; })}</div>}</main>
          <aside className="border-l border-gray-100 p-4 overflow-y-auto">{pendingActions.length > 0 && <div className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 p-3"><h3 className="text-sm font-semibold text-amber-900 mb-2">待确认安排</h3><div className="space-y-2">{pendingActions.map((item) => <div key={item.id} className="rounded-xl bg-white/80 p-2 text-xs text-amber-900"><div className="font-medium truncate">{textArg(item.arguments.title, item.title)}</div><div className="text-amber-700 mt-0.5">{textArg(item.arguments.start) ? formatTime(textArg(item.arguments.start)) : "未设置"} - {textArg(item.arguments.end) ? formatTime(textArg(item.arguments.end)) : "未设置"}</div><div className="mt-2 grid grid-cols-3 gap-1"><button className="rounded-lg bg-amber-600 px-2 py-1 text-white" onClick={() => confirmPending(item)}>确认</button><button className="rounded-lg border border-amber-200 px-2 py-1" onClick={() => { editPending(item); }}>修改</button><button className="rounded-lg border border-amber-200 px-2 py-1" onClick={() => cancelPending(item)}>取消</button></div></div>)}</div></div>}
            <h3 className="text-sm font-semibold text-gray-800 mb-3">{editingPending ? "修改待确认" : editing ? "修改日程" : "新增日程"}</h3><div className="space-y-2 text-xs"><input className="w-full rounded-lg border border-gray-200 px-3 py-2" placeholder="日程标题" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /><input className="w-full rounded-lg border border-gray-200 px-3 py-2" type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} /><div className="grid grid-cols-2 gap-2"><input className="rounded-lg border border-gray-200 px-3 py-2" type="time" value={form.startTime} onChange={(e) => setForm({ ...form, startTime: e.target.value })} /><input className="rounded-lg border border-gray-200 px-3 py-2" type="time" value={form.endTime} onChange={(e) => setForm({ ...form, endTime: e.target.value })} /></div><input className="w-full rounded-lg border border-gray-200 px-3 py-2" placeholder="地点（可选）" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} /><textarea className="w-full rounded-lg border border-gray-200 px-3 py-2 min-h-16" placeholder="备注（可选）" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /><label className="flex items-center gap-2 text-gray-600"><input type="checkbox" checked={form.route_required} onChange={(e) => setForm({ ...form, route_required: e.target.checked })} />需要路线规划</label><button className="w-full rounded-lg bg-[var(--color-primary)] px-3 py-2 text-white font-medium" onClick={saveForm}>{editingPending ? "保存待确认修改" : editing ? "保存修改" : "添加日程"}</button>{(editing || editingPending) && <button className="w-full rounded-lg border border-gray-200 px-3 py-2 text-gray-600" onClick={() => { setEditing(null); setEditingPending(null); setForm(emptyForm(currentDate)); }}>取消修改</button>}</div>
            {selected && <div className="mt-5 border-t border-gray-100 pt-4 text-xs text-gray-600"><h3 className={`text-sm font-semibold text-gray-900 ${selected.status === "completed" ? "line-through text-gray-400" : ""}`}>{selected.title}</h3><p className="mt-1">{formatTime(selected.start)} - {formatTime(selected.end)} · {selected.status ?? "confirmed"}</p><p className="mt-1">来源：{eventSource(selected)}</p>{selected.created_reason && <p className="mt-1">原因：{selected.created_reason}</p>}{selected.location && <p className="mt-1">地点：{selected.location}</p>}{selected.notes && <p className="mt-1">备注：{selected.notes}</p>}{selected.route_required && <p className="mt-1">路线：需要路线规划，后续版本展示路线图。</p>}<div className="mt-3 grid grid-cols-3 gap-2"><button className="rounded-lg border border-gray-200 px-2 py-1.5" onClick={() => startEdit(selected)}>修改</button><button className="rounded-lg border border-gray-200 px-2 py-1.5" onClick={() => markCompleted(selected)}>{selected.status === "completed" ? "恢复" : "划掉"}</button><button className="rounded-lg border border-red-200 px-2 py-1.5 text-red-600" onClick={() => removeEvent(selected)}>删除</button></div></div>}</aside>
        </div>
      </aside>
    </div>
  );
};
