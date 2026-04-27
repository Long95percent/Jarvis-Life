import React, { useEffect, useMemo, useState } from "react";
import { useJarvisStore } from "@/stores/jarvisStore";
import { jarvisApi, type BackgroundTask, type BackgroundTaskDay, type CalendarEvent, type PendingAction } from "@/services/jarvisApi";

interface Props { open: boolean; onClose: () => void }
type ViewMode = "day" | "week" | "month";
type PanelTab = "calendar" | "tasks";

interface EventForm {
  title: string;
  date: string;
  startTime: string;
  endTime: string;
  location: string;
  notes: string;
  stress_weight: number;
  route_required: boolean;
}

const WEEKDAY_LABELS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
const pad = (value: number) => String(value).padStart(2, "0");
const startOfDay = (date: Date) => { const copy = new Date(date); copy.setHours(0, 0, 0, 0); return copy; };
const addDays = (date: Date, days: number) => { const copy = new Date(date); copy.setDate(copy.getDate() + days); return copy; };
const addMonths = (date: Date, months: number) => { const copy = new Date(date); copy.setMonth(copy.getMonth() + months); return copy; };
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
    const start = startOfWeek(date);
    const end = addDays(start, 6);
    return `${start.toLocaleDateString("zh-CN", { month: "short", day: "numeric" })} - ${end.toLocaleDateString("zh-CN", { month: "short", day: "numeric" })}`;
  }
  return date.toLocaleDateString("zh-CN", { year: "numeric", month: "long" });
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function formatDateTime(value: unknown): string {
  if (typeof value !== "string" || !value) return "未设置";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function formatDate(value: unknown): string {
  if (typeof value !== "string" || !value) return "未设置日期";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
}

function hasValue(value: unknown): boolean {
  return value !== undefined && value !== null && value !== "";
}

function emptyForm(date: Date): EventForm {
  const now = new Date();
  const selectedToday = sameDay(date, now);
  const start = selectedToday ? new Date(now) : new Date(date);
  start.setMinutes(0, 0, 0);
  if (selectedToday) start.setHours(now.getHours() + 1);
  const end = new Date(start);
  end.setHours(start.getHours() + 1);
  return {
    title: "",
    date: toDateInput(date),
    startTime: toTimeInput(start),
    endTime: toTimeInput(end),
    location: "",
    notes: "",
    stress_weight: 1,
    route_required: false,
  };
}

function formFromEvent(event: CalendarEvent): EventForm {
  const start = new Date(event.start);
  const end = new Date(event.end);
  return {
    title: event.title,
    date: toDateInput(start),
    startTime: toTimeInput(start),
    endTime: toTimeInput(end),
    location: event.location ?? "",
    notes: event.notes ?? "",
    stress_weight: event.stress_weight ?? 1,
    route_required: Boolean(event.route_required),
  };
}

function formFromPending(item: PendingAction): EventForm {
  const args = item.arguments ?? {};
  const start = textArg(args.start) ? new Date(textArg(args.start)) : new Date();
  const end = textArg(args.end) ? new Date(textArg(args.end)) : new Date(start);
  if (!textArg(args.end)) end.setHours(start.getHours() + 1);
  return {
    title: textArg(args.title, item.title),
    date: toDateInput(start),
    startTime: toTimeInput(start),
    endTime: toTimeInput(end),
    location: textArg(args.location),
    notes: textArg(args.notes),
    stress_weight: Number(args.stress_weight ?? 1),
    route_required: Boolean(args.route_required),
  };
}

function eventSource(event: CalendarEvent): string {
  if (event.source_agent) return `来自 ${event.source_agent}`;
  if (event.source === "agent_pending_confirmation") return "Agent 建议，用户确认";
  if (event.source === "user_ui") return "用户创建";
  return event.source ?? "未知来源";
}

function eventsForDay(events: CalendarEvent[], date: Date): CalendarEvent[] {
  return events
    .filter((event) => sameDay(new Date(event.start), date))
    .sort((a, b) => +new Date(a.start) - +new Date(b.start));
}

function asList(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null) : [];
}

function taskDateSummary(task: BackgroundTask): string {
  const horizon = task.time_horizon ?? {};
  const start = horizon.start_date ?? horizon.start ?? horizon.from;
  const end = horizon.end_date ?? horizon.end ?? horizon.to;
  if (start || end) return `${formatDate(start)} - ${formatDate(end)}`;
  const candidates = asList(task.calendar_candidates);
  const first = candidates.find((item) => item.start || item.start_time || item.date);
  if (first) return `${formatDateTime(first.start ?? first.start_time ?? first.date)}`;
  return "暂无明确日期";
}

function taskStatusLabel(status: string): string {
  if (status === "active") return "进行中";
  if (status === "completed") return "已完成";
  if (status === "paused") return "暂停";
  return status;
}

function taskDayStatusLabel(status: string): string {
  if (status === "pending") return "待执行";
  if (status === "pushed") return "已进工作台";
  if (status === "completed") return "已完成";
  if (status === "missed") return "已逾期";
  if (status === "rescheduled") return "已重排";
  if (status === "cancelled") return "已取消";
  return status;
}

function taskDayDate(day: BackgroundTaskDay): Date {
  const startTime = day.start_time ? day.start_time.slice(0, 5) : "23:59";
  return new Date(`${day.plan_date}T${startTime}:00`);
}

function taskDaysForDay(days: BackgroundTaskDay[], date: Date): BackgroundTaskDay[] {
  return days
    .filter((day) => sameDay(taskDayDate(day), date))
    .sort((a, b) => +taskDayDate(a) - +taskDayDate(b));
}

export const CalendarPanel: React.FC<Props> = ({ open, onClose }) => {
  const addCalendarEvent = useJarvisStore((s) => s.addCalendarEvent);
  const updateCalendarEvent = useJarvisStore((s) => s.updateCalendarEvent);
  const deleteCalendarEvent = useJarvisStore((s) => s.deleteCalendarEvent);

  const [tab, setTab] = useState<PanelTab>("calendar");
  const [mode, setMode] = useState<ViewMode>("day");
  const [currentDate, setCurrentDate] = useState(() => startOfDay(new Date()));
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [pendingActions, setPendingActions] = useState<PendingAction[]>([]);
  const [tasks, setTasks] = useState<BackgroundTask[]>([]);
  const [taskDays, setTaskDays] = useState<BackgroundTaskDay[]>([]);
  const [selectedTask, setSelectedTask] = useState<BackgroundTask | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const [selectedTaskDay, setSelectedTaskDay] = useState<BackgroundTaskDay | null>(null);
  const [editing, setEditing] = useState<CalendarEvent | null>(null);
  const [editingPending, setEditingPending] = useState<PendingAction | null>(null);
  const [form, setForm] = useState<EventForm>(() => emptyForm(new Date()));

  const range = useMemo(() => {
    if (mode === "day") {
      const start = startOfDay(currentDate);
      return { start, end: addDays(start, 1) };
    }
    if (mode === "week") {
      const start = startOfWeek(currentDate);
      return { start, end: addDays(start, 7) };
    }
    const start = startOfWeek(startOfMonth(currentDate));
    return { start, end: endOfMonthGrid(currentDate) };
  }, [currentDate, mode]);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [items, pending, backgroundTasks, backgroundTaskDays] = await Promise.all([
        jarvisApi.listCalendarEvents(24, { start: range.start.toISOString(), end: range.end.toISOString() }),
        jarvisApi.listPendingActions("pending"),
        jarvisApi.listBackgroundTasks(),
        jarvisApi.listBackgroundTaskDays({ limit: 500 }),
      ]);
      setEvents(items);
      setPendingActions(pending);
      setTasks(backgroundTasks);
      setTaskDays(backgroundTaskDays);
      setSelectedTask((current) => current ? backgroundTasks.find((item) => item.id === current.id) ?? current : backgroundTasks[0] ?? null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    loadAll();
    setForm(emptyForm(currentDate));
    setSelected(null);
    setSelectedTaskDay(null);
    setEditing(null);
    setEditingPending(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, range.start.getTime(), range.end.getTime()]);

  if (!open) return null;

  const shiftRange = (delta: number) => {
    if (mode === "day") setCurrentDate((date) => addDays(date, delta));
    else if (mode === "week") setCurrentDate((date) => addDays(date, delta * 7));
    else setCurrentDate((date) => addMonths(date, delta));
  };

  const payloadFromForm = () => ({
    title: form.title.trim(),
    start: isoFromLocal(form.date, form.startTime),
    end: isoFromLocal(form.date, form.endTime),
    stress_weight: form.stress_weight,
    location: form.location.trim() || null,
    notes: form.notes.trim() || null,
    route_required: form.route_required,
  });

  const saveForm = async () => {
    const payload = payloadFromForm();
    if (!payload.title) return;
    if (editingPending) {
      await jarvisApi.updatePendingAction(editingPending.id, { title: payload.title, arguments: { ...editingPending.arguments, ...payload } });
      setEditingPending(null);
    } else if (editing?.id) {
      await updateCalendarEvent(editing.id, { ...payload, source: "user_ui", source_agent: null, created_reason: "用户手动修改日程", status: editing.status ?? "confirmed" });
      setEditing(null);
      setSelected(null);
    } else {
      await addCalendarEvent({ ...payload, source: "user_ui", source_agent: null, created_reason: "用户手动创建日程", status: "confirmed" });
    }
    setForm(emptyForm(currentDate));
    await loadAll();
  };

  const confirmPending = async (item: PendingAction) => { await jarvisApi.confirmPendingAction(item.id); await loadAll(); };
  const cancelPending = async (item: PendingAction) => { await jarvisApi.cancelPendingAction(item.id); await loadAll(); };
  const editPending = (item: PendingAction) => { setEditingPending(item); setEditing(null); setSelected(null); setForm(formFromPending(item)); setTab("calendar"); };
  const startEdit = (event: CalendarEvent) => { setEditing(event); setEditingPending(null); setSelected(event); setForm(formFromEvent(event)); };
  const markCompleted = async (event: CalendarEvent) => { if (!event.id) return; await updateCalendarEvent(event.id, { status: event.status === "completed" ? "confirmed" : "completed" }); await loadAll(); setSelected(null); };
  const removeEvent = async (event: CalendarEvent) => { if (!event.id || !confirm(`删除日程「${event.title}」？`)) return; await deleteCalendarEvent(event.id); await loadAll(); setSelected(null); setEditing(null); };
  const completeTaskDay = async (day: BackgroundTaskDay) => { await jarvisApi.completeBackgroundTaskDay(day.id); await loadAll(); setSelectedTaskDay(null); };

  const renderEventButton = (event: CalendarEvent, compact = false) => (
    <button
      key={event.id ?? `${event.title}-${event.start}`}
      className={`w-full rounded-lg px-2 py-1 text-left ${compact ? "text-[10px]" : "text-xs"} ${event.status === "completed" ? "bg-gray-100 text-gray-400 line-through" : "bg-blue-50 text-blue-800 hover:bg-blue-100"}`}
      onClick={() => setSelected(event)}
    >
      <span className="font-medium">{compact ? event.title : `${formatTime(event.start)} ${event.title}`}</span>
    </button>
  );

  const renderTaskDayButton = (day: BackgroundTaskDay, compact = false) => (
    <button
      key={day.id}
      className={`w-full rounded-lg px-2 py-1 text-left ${compact ? "text-[10px]" : "text-xs"} ${day.status === "completed" ? "bg-gray-100 text-gray-400 line-through" : day.status === "missed" ? "bg-red-50 text-red-700 hover:bg-red-100" : "bg-emerald-50 text-emerald-800 hover:bg-emerald-100"}`}
      title={day.description ?? ""}
      onClick={() => { setSelectedTaskDay(day); setSelected(null); }}
    >
      <span className="font-medium">{compact ? day.title : `${day.start_time ? day.start_time.slice(0, 5) : "任务"} ${day.title}`}</span>
    </button>
  );

  const weekDays = Array.from({ length: 7 }, (_, index) => addDays(startOfWeek(currentDate), index));
  const monthDays = Array.from({ length: Math.round((range.end.getTime() - range.start.getTime()) / 86400000) }, (_, index) => addDays(range.start, index));
  const selectedMilestones = asList(selectedTask?.milestones);
  const selectedSubtasks = asList(selectedTask?.subtasks);
  const selectedCandidates = asList(selectedTask?.calendar_candidates);
  const selectedTaskDays = selectedTask ? taskDays.filter((day) => day.task_id === selectedTask.id) : [];

  return (
    <div className="fixed inset-0 z-40 flex">
      <button type="button" aria-label="关闭日历遮罩" className="flex-1 bg-black/20" onClick={onClose} />
      <aside className="w-full max-w-[920px] h-full bg-white shadow-2xl border-l border-gray-200 flex flex-col">
        <header className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-gray-900">日程日历</h2>
            <p className="text-xs text-gray-500 mt-0.5">查看日程，也可以打开后台任务清单。</p>
          </div>
          <button className="text-sm text-gray-500 hover:text-gray-800" onClick={onClose}>关闭</button>
        </header>

        <div className="px-5 py-2 border-b border-gray-100 flex gap-2">
          <button className={`px-3 py-1.5 rounded-lg text-xs border ${tab === "calendar" ? "bg-[var(--color-primary)] text-white border-transparent" : "border-gray-200 text-gray-600"}`} onClick={() => setTab("calendar")}>日历</button>
          <button className={`px-3 py-1.5 rounded-lg text-xs border ${tab === "tasks" ? "bg-[var(--color-primary)] text-white border-transparent" : "border-gray-200 text-gray-600"}`} onClick={() => setTab("tasks")}>查看所有任务</button>
          <button className="ml-auto px-3 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-50" onClick={() => void loadAll()}>{loading ? "刷新中…" : "刷新"}</button>
        </div>

        {tab === "calendar" ? (
          <>
            <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between gap-3">
              <button className="px-3 py-1.5 rounded-lg border border-gray-200 text-sm hover:bg-gray-50" onClick={() => shiftRange(-1)}>上一{mode === "day" ? "天" : mode === "week" ? "周" : "月"}</button>
              <div className="text-center">
                <div className="text-sm font-semibold text-gray-800">{formatRangeTitle(currentDate, mode)}</div>
                <button className="text-xs text-[var(--color-primary)]" onClick={() => setCurrentDate(startOfDay(new Date()))}>回到今天</button>
              </div>
              <button className="px-3 py-1.5 rounded-lg border border-gray-200 text-sm hover:bg-gray-50" onClick={() => shiftRange(1)}>下一{mode === "day" ? "天" : mode === "week" ? "周" : "月"}</button>
            </div>
            <div className="px-5 py-2 border-b border-gray-100 flex gap-2">
              {(["day", "week", "month"] as ViewMode[]).map((item) => (
                <button key={item} className={`px-3 py-1.5 rounded-lg text-xs border ${mode === item ? "bg-gray-900 text-white border-transparent" : "border-gray-200 text-gray-600"}`} onClick={() => setMode(item)}>
                  {item === "day" ? "日视图" : item === "week" ? "周视图" : "月视图"}
                </button>
              ))}
            </div>
            <div className="grid grid-cols-[1fr_280px] min-h-0 flex-1">
              <main className="overflow-y-auto px-5 py-4 bg-gray-50/60">
                {loading ? <div className="py-10 text-center text-sm text-gray-400">正在加载日程…</div> : null}
                {!loading && mode === "day" && (
                  <div className="space-y-2">
                    {eventsForDay(events, currentDate).length === 0 && taskDaysForDay(taskDays, currentDate).length === 0 ? <div className="rounded-2xl border border-dashed border-gray-200 bg-white p-8 text-center text-sm text-gray-400">今天暂无日程</div> : null}
                    {eventsForDay(events, currentDate).map((event) => renderEventButton(event))}
                    {taskDaysForDay(taskDays, currentDate).map((day) => renderTaskDayButton(day))}
                  </div>
                )}
                {!loading && mode === "week" && (
                  <div className="grid grid-cols-7 gap-2">
                    {weekDays.map((day) => (
                      <div key={day.toISOString()} className={`rounded-2xl border bg-white p-2 min-h-72 ${sameDay(day, new Date()) ? "border-blue-300" : "border-gray-200"}`}>
                        <button className="text-xs font-semibold text-gray-700 mb-2" onClick={() => { setCurrentDate(day); setMode("day"); }}>{WEEKDAY_LABELS[day.getDay()]} {day.getMonth() + 1}/{day.getDate()}</button>
                        <div className="space-y-1">{eventsForDay(events, day).map((event) => renderEventButton(event))}{taskDaysForDay(taskDays, day).map((taskDay) => renderTaskDayButton(taskDay))}</div>
                      </div>
                    ))}
                  </div>
                )}
                {!loading && mode === "month" && (
                  <div className="grid grid-cols-7 gap-2">
                    {WEEKDAY_LABELS.map((label) => <div key={label} className="text-center text-xs font-semibold text-gray-400">{label}</div>)}
                    {monthDays.map((day) => {
                      const dayItems = [...eventsForDay(events, day), ...taskDaysForDay(taskDays, day)];
                      const inMonth = day.getMonth() === currentDate.getMonth();
                      return (
                        <div key={day.toISOString()} className={`rounded-2xl border bg-white p-2 min-h-28 ${sameDay(day, new Date()) ? "border-blue-300" : "border-gray-200"} ${inMonth ? "" : "opacity-45"}`}>
                          <button className="text-xs font-semibold text-gray-700" onClick={() => { setCurrentDate(day); setMode("day"); }}>{day.getDate()}</button>
                          <div className="mt-1 space-y-1">{eventsForDay(events, day).slice(0, 3).map((event) => renderEventButton(event, true))}{taskDaysForDay(taskDays, day).slice(0, Math.max(0, 3 - eventsForDay(events, day).length)).map((taskDay) => renderTaskDayButton(taskDay, true))}{dayItems.length > 3 && <div className="text-[10px] text-gray-400">+{dayItems.length - 3} 项</div>}</div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </main>
              <aside className="border-l border-gray-100 p-4 overflow-y-auto">
                {pendingActions.length > 0 && (
                  <div className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 p-3">
                    <h3 className="text-sm font-semibold text-amber-900 mb-2">待确认安排</h3>
                    <div className="space-y-2">{pendingActions.map((item) => <div key={item.id} className="rounded-xl bg-white/80 p-2 text-xs text-amber-900"><div className="font-medium truncate">{textArg(item.arguments.title, item.title)}</div><div className="text-amber-700 mt-0.5">{textArg(item.arguments.start) ? formatTime(textArg(item.arguments.start)) : "未设置"} - {textArg(item.arguments.end) ? formatTime(textArg(item.arguments.end)) : "未设置"}</div><div className="mt-2 grid grid-cols-3 gap-1"><button className="rounded-lg bg-amber-600 px-2 py-1 text-white" onClick={() => confirmPending(item)}>确认</button><button className="rounded-lg border border-amber-200 px-2 py-1" onClick={() => editPending(item)}>修改</button><button className="rounded-lg border border-amber-200 px-2 py-1" onClick={() => cancelPending(item)}>取消</button></div></div>)}</div>
                  </div>
                )}
                <h3 className="text-sm font-semibold text-gray-800 mb-3">{editingPending ? "修改待确认" : editing ? "修改日程" : "新增日程"}</h3>
                <div className="space-y-2 text-xs">
                  <input className="w-full rounded-lg border border-gray-200 px-3 py-2" placeholder="日程标题" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
                  <input className="w-full rounded-lg border border-gray-200 px-3 py-2" type="date" value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} />
                  <div className="grid grid-cols-2 gap-2"><input className="rounded-lg border border-gray-200 px-3 py-2" type="time" value={form.startTime} onChange={(event) => setForm({ ...form, startTime: event.target.value })} /><input className="rounded-lg border border-gray-200 px-3 py-2" type="time" value={form.endTime} onChange={(event) => setForm({ ...form, endTime: event.target.value })} /></div>
                  <input className="w-full rounded-lg border border-gray-200 px-3 py-2" placeholder="地点（可选）" value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} />
                  <textarea className="w-full rounded-lg border border-gray-200 px-3 py-2 min-h-16" placeholder="备注（可选）" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
                  <label className="flex items-center gap-2 text-gray-600"><input type="checkbox" checked={form.route_required} onChange={(event) => setForm({ ...form, route_required: event.target.checked })} />需要路线规划</label>
                  <button className="w-full rounded-lg bg-[var(--color-primary)] px-3 py-2 text-white font-medium" onClick={saveForm}>{editingPending ? "保存待确认修改" : editing ? "保存修改" : "添加日程"}</button>
                  {(editing || editingPending) && <button className="w-full rounded-lg border border-gray-200 px-3 py-2 text-gray-600" onClick={() => { setEditing(null); setEditingPending(null); setForm(emptyForm(currentDate)); }}>取消修改</button>}
                </div>
                {selected && <div className="mt-5 border-t border-gray-100 pt-4 text-xs text-gray-600"><h3 className={`text-sm font-semibold text-gray-900 ${selected.status === "completed" ? "line-through text-gray-400" : ""}`}>{selected.title}</h3><p className="mt-1">{formatTime(selected.start)} - {formatTime(selected.end)} · {selected.status ?? "confirmed"}</p><p className="mt-1">来源：{eventSource(selected)}</p>{selected.created_reason && <p className="mt-1">原因：{selected.created_reason}</p>}{selected.location && <p className="mt-1">地点：{selected.location}</p>}{selected.notes && <p className="mt-1">备注：{selected.notes}</p>}<div className="mt-3 grid grid-cols-3 gap-2"><button className="rounded-lg border border-gray-200 px-2 py-1.5" onClick={() => startEdit(selected)}>修改</button><button className="rounded-lg border border-gray-200 px-2 py-1.5" onClick={() => markCompleted(selected)}>{selected.status === "completed" ? "恢复" : "划掉"}</button><button className="rounded-lg border border-red-200 px-2 py-1.5 text-red-600" onClick={() => removeEvent(selected)}>删除</button></div></div>}
                {selectedTaskDay && <div className="mt-5 border-t border-gray-100 pt-4 text-xs text-gray-600"><h3 className={`text-sm font-semibold text-gray-900 ${selectedTaskDay.status === "completed" ? "line-through text-gray-400" : ""}`}>{selectedTaskDay.title}</h3><p className="mt-1">{formatDate(selectedTaskDay.plan_date)} · {selectedTaskDay.start_time ? selectedTaskDay.start_time.slice(0, 5) : "未设时间"} · {taskDayStatusLabel(selectedTaskDay.status)}</p>{selectedTaskDay.description && <p className="mt-2">{selectedTaskDay.description}</p>}<button className="mt-3 w-full rounded-lg border border-emerald-200 px-2 py-1.5 text-emerald-700 disabled:text-gray-400 disabled:border-gray-200" disabled={selectedTaskDay.status === "completed"} onClick={() => completeTaskDay(selectedTaskDay)}>标记完成</button></div>}
              </aside>
            </div>
          </>
        ) : (
          <div className="grid grid-cols-[320px_1fr] min-h-0 flex-1">
            <aside className="border-r border-gray-100 p-4 overflow-y-auto bg-gray-50/60">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-800">任务清单</h3>
                <span className="text-xs text-gray-400">{tasks.length} 个</span>
              </div>
              {loading ? <div className="py-8 text-center text-sm text-gray-400">正在加载任务…</div> : null}
              {!loading && tasks.length === 0 ? <div className="rounded-2xl border border-dashed border-gray-200 bg-white p-4 text-sm text-gray-400">暂无后台任务。和 Maxwell 说一个长期目标后，会在这里看到任务清单。</div> : null}
              <div className="space-y-2">
                {tasks.map((task) => (
                  <button key={task.id} className={`w-full rounded-2xl border p-3 text-left ${selectedTask?.id === task.id ? "border-blue-300 bg-blue-50" : "border-gray-200 bg-white hover:bg-gray-50"}`} onClick={() => setSelectedTask(task)}>
                    <div className="font-medium text-sm text-gray-800 line-clamp-2">{task.title}</div>
                    <div className="mt-1 text-xs text-gray-500">{taskDateSummary(task)}</div>
                    <div className="mt-2 flex items-center justify-between text-[11px]"><span className="rounded-full bg-gray-100 px-2 py-0.5 text-gray-500">{task.task_type}</span><span className="text-blue-600">{taskStatusLabel(task.status)}</span></div>
                  </button>
                ))}
              </div>
            </aside>
            <main className="overflow-y-auto p-5">
              {!selectedTask ? <div className="rounded-2xl border border-dashed border-gray-200 p-8 text-center text-sm text-gray-400">选择一个任务查看详细日期与子任务。</div> : (
                <div className="space-y-5">
                  <section className="rounded-2xl border border-gray-200 p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h3 className="text-lg font-semibold text-gray-900">{selectedTask.title}</h3>
                        <p className="mt-1 text-sm text-gray-500">{selectedTask.goal || selectedTask.original_user_request}</p>
                      </div>
                      <span className="rounded-full bg-blue-50 px-3 py-1 text-xs text-blue-600">{taskStatusLabel(selectedTask.status)}</span>
                    </div>
                    <div className="mt-4 grid grid-cols-3 gap-3 text-xs">
                      <div className="rounded-xl bg-gray-50 p-3"><div className="text-gray-400">日期范围</div><div className="mt-1 font-medium text-gray-700">{taskDateSummary(selectedTask)}</div></div>
                      <div className="rounded-xl bg-gray-50 p-3"><div className="text-gray-400">来源 Agent</div><div className="mt-1 font-medium text-gray-700">{selectedTask.source_agent || "未记录"}</div></div>
                      <div className="rounded-xl bg-gray-50 p-3"><div className="text-gray-400">任务类型</div><div className="mt-1 font-medium text-gray-700">{selectedTask.task_type}</div></div>
                    </div>
                  </section>

                  <section className="rounded-2xl border border-gray-200 p-4">
                    <h4 className="text-sm font-semibold text-gray-800 mb-3">每日计划</h4>
                    <div className="space-y-2">{selectedTaskDays.length === 0 ? <p className="text-sm text-gray-400">暂无每日计划</p> : selectedTaskDays.map((day) => <div key={day.id} className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-950"><div className="flex items-start justify-between gap-3"><div><div className={`font-medium ${day.status === "completed" ? "line-through text-gray-400" : ""}`}>{day.title}</div><div className="mt-1 text-xs text-emerald-700">{formatDate(day.plan_date)} {day.start_time ? `· ${day.start_time.slice(0, 5)}` : ""} · {taskDayStatusLabel(day.status)}</div>{day.description && <p className="mt-1 text-xs text-emerald-800">{day.description}</p>}</div><button className="shrink-0 rounded-lg border border-emerald-200 bg-white px-2 py-1 text-xs text-emerald-700 disabled:text-gray-400" disabled={day.status === "completed"} onClick={() => completeTaskDay(day)}>完成</button></div></div>)}</div>
                  </section>

                  <section className="rounded-2xl border border-gray-200 p-4">
                    <h4 className="text-sm font-semibold text-gray-800 mb-3">里程碑</h4>
                    <div className="space-y-2">{selectedMilestones.length === 0 ? <p className="text-sm text-gray-400">暂无里程碑</p> : selectedMilestones.map((item, index) => <div key={index} className="rounded-xl bg-gray-50 p-3 text-sm"><div className="font-medium text-gray-800">{String(item.title ?? item.name ?? `里程碑 ${index + 1}`)}</div><div className="mt-1 text-xs text-gray-500">{formatDateTime(item.date ?? item.due_date ?? item.target_date ?? item.start)}</div>{hasValue(item.description) && <p className="mt-1 text-xs text-gray-500">{String(item.description)}</p>}</div>)}</div>
                  </section>

                  <section className="rounded-2xl border border-gray-200 p-4">
                    <h4 className="text-sm font-semibold text-gray-800 mb-3">子任务</h4>
                    <div className="space-y-2">{selectedSubtasks.length === 0 ? <p className="text-sm text-gray-400">暂无子任务</p> : selectedSubtasks.map((item, index) => <div key={index} className="rounded-xl bg-gray-50 p-3 text-sm"><div className="font-medium text-gray-800">{String(item.title ?? item.name ?? `子任务 ${index + 1}`)}</div><div className="mt-1 text-xs text-gray-500">{formatDateTime(item.due_date ?? item.date ?? item.start ?? item.start_time)}</div>{hasValue(item.notes) && <p className="mt-1 text-xs text-gray-500">{String(item.notes)}</p>}</div>)}</div>
                  </section>

                  <section className="rounded-2xl border border-gray-200 p-4">
                    <h4 className="text-sm font-semibold text-gray-800 mb-3">建议写入日历的时间块</h4>
                    <div className="space-y-2">{selectedCandidates.length === 0 ? <p className="text-sm text-gray-400">暂无候选时间块</p> : selectedCandidates.map((item, index) => <div key={index} className="rounded-xl bg-blue-50 p-3 text-sm text-blue-900"><div className="font-medium">{String(item.title ?? item.name ?? `候选时间 ${index + 1}`)}</div><div className="mt-1 text-xs text-blue-700">{formatDateTime(item.start ?? item.start_time ?? item.date)} - {formatDateTime(item.end ?? item.end_time)}</div>{hasValue(item.reason) && <p className="mt-1 text-xs text-blue-700">{String(item.reason)}</p>}</div>)}</div>
                  </section>
                </div>
              )}
            </main>
          </div>
        )}
      </aside>
    </div>
  );
};
