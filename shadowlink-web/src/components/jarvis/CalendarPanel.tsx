import React, { useEffect, useMemo, useState } from "react";
import { useJarvisStore } from "@/stores/jarvisStore";
import { jarvisScheduleApi, type BackgroundTask, type BackgroundTaskDay, type CalendarEvent, type JarvisPlan, type JarvisPlanDay, type MaxwellWorkbenchItem, type PlannerCalendarItem, type PlannerTaskItem, type AgentEvent } from "@/services/jarvisScheduleApi";

interface Props { open: boolean; onClose: () => void }
type ViewMode = "day" | "week" | "month";
type PanelTab = "calendar" | "tasks" | "workbench";

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

interface PlanForm {
  title: string;
  goal: string;
  originalUserRequest: string;
  targetDate: string;
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
const sameDay = (a: Date, b: Date) => startOfDay(a).getTime() === startOfDay(b).getTime();
const localDateFromKey = (value: string) => {
  const [year, month, day] = value.slice(0, 10).split("-").map(Number);
  if (!year || !month || !day) return new Date(value);
  return new Date(year, month - 1, day);
};
const errorMessage = (error: unknown) => error instanceof Error ? error.message : String(error || "未知错误");
const emptyPlanForm = (): PlanForm => ({ title: "", goal: "", originalUserRequest: "", targetDate: "" });
const loadStep = async <T,>(label: string, run: () => Promise<T>): Promise<T> => {
  try {
    return await run();
  } catch (error) {
    throw new Error(`${label}：${errorMessage(error)}`);
  }
};

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
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value) ? localDateFromKey(value) : new Date(value);
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

function workbenchLiveStateLabel(item: MaxwellWorkbenchItem): string {
  const state = item.live_state;
  if (!state) return "实时状态：未返回";
  if (state.is_completed) return "实时状态：来源任务已完成";
  if (state.is_cancelled) return "实时状态：来源任务已取消";
  if (state.is_overdue) return "实时状态：已超时仍未完成";
  if (typeof state.minutes_until_due === "number" && state.minutes_until_due >= 0) return `实时状态：距截止约 ${state.minutes_until_due} 分钟`;
  return `实时状态：${taskDayStatusLabel(state.source_status || state.workbench_status || item.status)}`;
}

function workbenchBasisLabel(value?: string | null): string {
  if (value === "jarvis_plan_days") return "计划日实时查询";
  if (value === "background_task_days") return "长期任务日实时查询";
  return "仅工作台记录";
}

function taskDayDate(day: BackgroundTaskDay): Date {
  const startTime = day.start_time ? day.start_time.slice(0, 5) : "23:59";
  return new Date(`${day.plan_date.slice(0, 10)}T${startTime}:00`);
}

function eventFromPlannerItem(item: PlannerCalendarItem): CalendarEvent | null {
  if (item.item_type !== "calendar_event") return null;
  const payload = item.payload as unknown as CalendarEvent;
  return payload?.title && payload?.start && payload?.end ? payload : null;
}


function taskDayFromPlannerItem(item: PlannerCalendarItem): BackgroundTaskDay | null {
  if (item.item_type !== "background_task_day") return null;
  const payload = item.payload as unknown as BackgroundTaskDay;
  return payload?.id && payload?.task_id ? payload : null;
}

function planDayDate(day: JarvisPlanDay): Date {
  const startTime = day.start_time ? day.start_time.slice(0, 5) : "23:58";
  return new Date(`${day.plan_date.slice(0, 10)}T${startTime}:00`);
}

function taskDaysForDay(days: BackgroundTaskDay[], date: Date): BackgroundTaskDay[] {
  return days
    .filter((day) => sameDay(taskDayDate(day), date))
    .sort((a, b) => +taskDayDate(a) - +taskDayDate(b));
}

function planDaysForDay(days: JarvisPlanDay[], date: Date): JarvisPlanDay[] {
  return days
    .filter((day) => sameDay(planDayDate(day), date))
    .sort((a, b) => +planDayDate(a) - +planDayDate(b));
}

function calendarVisibleTaskDays(days: BackgroundTaskDay[], planDays: JarvisPlanDay[]): BackgroundTaskDay[] {
  const projectedSourceTaskDayIds = new Set(
    planDays
      .filter((day) => Boolean(day.calendar_event_id) && Boolean(day.source_task_day_id))
      .map((day) => day.source_task_day_id),
  );
  return days.filter((day) => !projectedSourceTaskDayIds.has(day.id));
}

function calendarVisiblePlanDays(days: JarvisPlanDay[]): JarvisPlanDay[] {
  return days.filter((day) => !day.calendar_event_id);
}
export const CalendarPanel: React.FC<Props> = ({ open, onClose }) => {
  const addCalendarEvent = useJarvisStore((s) => s.addCalendarEvent);
  const updateCalendarEvent = useJarvisStore((s) => s.updateCalendarEvent);
  const deleteCalendarEvent = useJarvisStore((s) => s.deleteCalendarEvent);

  const [tab, setTab] = useState<PanelTab>("calendar");
  const [mode, setMode] = useState<ViewMode>("day");
  const [currentDate, setCurrentDate] = useState(() => startOfDay(new Date()));
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [tasks, setTasks] = useState<BackgroundTask[]>([]);
  const [taskDays, setTaskDays] = useState<BackgroundTaskDay[]>([]);
  const [plans, setPlans] = useState<JarvisPlan[]>([]);
  const [planDays, setPlanDays] = useState<JarvisPlanDay[]>([]);
  const [plannerTasks, setPlannerTasks] = useState<PlannerTaskItem[]>([]);
  const [workbenchItems, setWorkbenchItems] = useState<MaxwellWorkbenchItem[]>([]);
  const [workbenchPushLoading, setWorkbenchPushLoading] = useState(false);
  const [workbenchMessage, setWorkbenchMessage] = useState<string | null>(null);
  const [planFormSaving, setPlanFormSaving] = useState(false);
  const [planEvents, setPlanEvents] = useState<AgentEvent[]>([]);
  const [editingPlanDay, setEditingPlanDay] = useState<JarvisPlanDay | null>(null);
  const [planDayForm, setPlanDayForm] = useState({ date: "", startTime: "", endTime: "", title: "", description: "" });
  const [selectedTask, setSelectedTask] = useState<BackgroundTask | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<JarvisPlan | null>(null);
  const [editingPlan, setEditingPlan] = useState<JarvisPlan | null | "new">(null);
  const [planForm, setPlanForm] = useState<PlanForm>(() => emptyPlanForm());
  const [planFormMessage, setPlanFormMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedPlanDay, setSelectedPlanDay] = useState<JarvisPlanDay | null>(null);
  const [backgroundTaskMessage, setBackgroundTaskMessage] = useState<string | null>(null);
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const [selectedTaskDay, setSelectedTaskDay] = useState<BackgroundTaskDay | null>(null);
  const [backgroundTaskActionLoading, setBackgroundTaskActionLoading] = useState<string | null>(null);
  const [editing, setEditing] = useState<CalendarEvent | null>(null);
  const [form, setForm] = useState<EventForm>(() => emptyForm(new Date()));
  const [loadError, setLoadError] = useState<string | null>(null);

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
    setLoadError(null);
    try {
      const [calendarItems, plannerTaskItems, backgroundTasks, backgroundTaskDays, jarvisPlans, jarvisPlanDays, maxwellWorkbenchItems] = await Promise.all([
        loadStep("日历项", () => jarvisScheduleApi.getPlannerCalendar({ start: range.start.toISOString(), end: range.end.toISOString() })),
        loadStep("统一任务清单", () => jarvisScheduleApi.listPlannerTasks()),
        loadStep("后台任务", () => jarvisScheduleApi.listBackgroundTasks()),
        loadStep("后台任务日", () => jarvisScheduleApi.listBackgroundTaskDays({ limit: 1000 })),
        loadStep("长期计划", () => jarvisScheduleApi.listPlans()),
        loadStep("计划日", () => jarvisScheduleApi.listPlanDays({ limit: 2000 })),
        loadStep("Maxwell 工作台", () => jarvisScheduleApi.listMaxwellWorkbenchItems({ limit: 200 })),
      ]);
      const plannerItems = calendarItems.items;
      setEvents(plannerItems.map(eventFromPlannerItem).filter((item): item is CalendarEvent => Boolean(item)));
      setPlannerTasks(plannerTaskItems);
      setTasks(backgroundTasks);
      setWorkbenchItems(maxwellWorkbenchItems);
      setTaskDays(plannerItems.map(taskDayFromPlannerItem).filter((item): item is BackgroundTaskDay => Boolean(item)).concat(backgroundTaskDays.filter((day) => !plannerItems.some((item) => item.item_type === "background_task_day" && item.id === day.id))));
      setPlans(jarvisPlans);
      setPlanDays(jarvisPlanDays);
      setSelectedTask((current) => current ? backgroundTasks.find((item) => item.id === current.id) ?? current : backgroundTasks[0] ?? null);
      setSelectedPlan((current) => current ? jarvisPlans.find((item) => item.id === current.id) ?? current : jarvisPlans[0] ?? null);
    } catch (error) {
      setLoadError(`日程数据加载失败：${errorMessage(error)}`);
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
    setSelectedPlanDay(null);
    setEditing(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, range.start.getTime(), range.end.getTime()]);

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
    if (editing?.id) {
      await updateCalendarEvent(editing.id, { ...payload, source: "user_ui", source_agent: null, created_reason: "用户手动修改日程", status: editing.status ?? "confirmed" });
      setEditing(null);
      setSelected(null);
    } else {
      await addCalendarEvent({ ...payload, source: "user_ui", source_agent: null, created_reason: "用户手动创建日程", status: "confirmed" });
    }
    setForm(emptyForm(currentDate));
    await loadAll();
  };

  const startEdit = (event: CalendarEvent) => { setEditing(event); setSelected(event); setForm(formFromEvent(event)); };
  const selectEventForDetail = (event: CalendarEvent) => { setSelected(event); setSelectedTaskDay(null); setSelectedPlanDay(null); setEditing(null); };
  const markCompleted = async (event: CalendarEvent) => { if (!event.id) return; await updateCalendarEvent(event.id, { status: event.status === "completed" ? "confirmed" : "completed" }); await loadAll(); setSelected(null); };
  const removeEvent = async (event: CalendarEvent) => { if (!event.id) return; setEvents((current) => current.filter((item) => item.id !== event.id)); setSelected((current) => current?.id === event.id ? null : current); setEditing((current) => current?.id === event.id ? null : current); await deleteCalendarEvent(event.id); };
  const completeTaskDay = async (day: BackgroundTaskDay) => { await jarvisScheduleApi.completeBackgroundTaskDay(day.id); await loadAll(); setSelectedTaskDay(null); };
  const completePlanDay = async (day: JarvisPlanDay) => { await jarvisScheduleApi.completePlanDay(day.id); await loadAll(); setSelectedPlanDay(null); };
  const removeTaskDay = async (day: BackgroundTaskDay) => { setTaskDays((current) => current.filter((item) => item.id !== day.id)); setSelectedTaskDay((current) => current?.id === day.id ? null : current); await jarvisScheduleApi.deleteBackgroundTaskDay(day.id); };
  const removePlanDay = async (day: JarvisPlanDay) => { setPlanDays((current) => current.filter((item) => item.id !== day.id)); setSelectedPlanDay((current) => current?.id === day.id ? null : current); await jarvisScheduleApi.deletePlanDay(day.id); };
  const handleDeleteKey = (event: React.KeyboardEvent, remove: () => void) => {
    if (event.key !== "Delete" && event.key !== "Backspace") return;
    event.preventDefault();
    void remove();
  };
  const handleContextDelete = (event: React.MouseEvent, remove: () => void) => {
    event.preventDefault();
    void remove();
  };

  const deletePlan = async (plan: JarvisPlan) => {
    setPlans((current) => current.filter((item) => item.id !== plan.id));
    setPlanDays((current) => current.filter((item) => item.plan_id !== plan.id));
    setSelectedPlan((current) => current?.id === plan.id ? null : current);
    setSelectedPlanDay((current) => current?.plan_id === plan.id ? null : current);
    await jarvisScheduleApi.deletePlan(plan.id);
  };

  const pushTodayTasksToWorkbench = async () => {
    setWorkbenchPushLoading(true);
    setWorkbenchMessage(null);
    try {
      const result = await jarvisScheduleApi.pushDailyTasksToMaxwellWorkbench(toDateInput(new Date()));
      setWorkbenchMessage(`推送今日任务完成：新增/更新 ${result.pushed_count} 个工作台项`);
      await loadAll();
    } catch (error) {
      setWorkbenchMessage(`推送失败：${errorMessage(error)}`);
    } finally {
      setWorkbenchPushLoading(false);
    }
  };

  const startNewPlan = () => {
    setEditingPlan("new");
    setPlanForm(emptyPlanForm());
    setPlanFormMessage(null);
  };

  const startEditPlan = (plan: JarvisPlan) => {
    const targetDate = typeof plan.time_horizon?.target_date === "string" ? plan.time_horizon.target_date : "";
    setEditingPlan(plan);
    setPlanForm({
      title: plan.title,
      goal: plan.goal ?? "",
      originalUserRequest: plan.original_user_request ?? "",
      targetDate,
    });
    setPlanFormMessage(null);
  };

  const savePlanForm = async () => {
    const title = planForm.title.trim();
    if (!title) { setPlanFormMessage("计划标题不能为空"); return; }
    setPlanFormSaving(true);
    setPlanFormMessage(null);
    const payload = {
      title,
      plan_type: "long_term",
      status: "active",
      goal: planForm.goal.trim() || null,
      original_user_request: planForm.originalUserRequest.trim() || title,
      time_horizon: planForm.targetDate ? { target_date: planForm.targetDate } : {},
      raw_payload: { source: "manual_plan_form" },
    };
    try {
      const saved = editingPlan === "new" ? await jarvisScheduleApi.createPlan(payload) : await jarvisScheduleApi.updatePlan(editingPlan!.id, payload);
      setSelectedPlan(saved);
      setSelectedTask(null);
      setEditingPlan(null);
      setPlanFormMessage(editingPlan === "new" ? "长期计划已创建" : "计划信息已更新");
      await loadAll();
    } catch (error) {
      setPlanFormMessage(`保存失败：${errorMessage(error)}`);
    } finally {
      setPlanFormSaving(false);
    }
  };

  const selectPlanDayForDetail = (day: JarvisPlanDay) => {
    setSelectedPlanDay(day);
    setSelectedTaskDay(null);
    setSelected(null);
  };

  const updateSelectedBackgroundTaskStatus = async (task: BackgroundTask, status: "archived" | "deleted") => {
    const label = status === "archived" ? "归档历史任务" : "删除历史任务";
    setBackgroundTaskActionLoading(status);
    setBackgroundTaskMessage(null);
    try {
      await jarvisScheduleApi.updateBackgroundTask(task.id, { status });
      setBackgroundTaskMessage(`${label}完成`);
      setTasks((current) => current.filter((item) => item.id !== task.id));
      setTaskDays((current) => current.filter((day) => day.task_id !== task.id));
      setSelectedTask((current) => current?.id === task.id ? null : current);
    } catch (error) {
      setBackgroundTaskMessage(`${label}失败：${errorMessage(error)}`);
    } finally {
      setBackgroundTaskActionLoading(null);
    }
  };
  const renderDeleteButton = (label: string, remove: () => void, compact = false) => (
    <button
      type="button"
      aria-label={label}
      className={`ml-auto inline-flex shrink-0 items-center justify-center rounded text-red-500 hover:bg-red-100 hover:text-red-700 ${compact ? "h-4 w-4 text-[10px]" : "h-5 w-5 text-xs"}`}
      onClick={(event) => { event.stopPropagation(); void remove(); }}
      onKeyDown={(event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        event.stopPropagation();
        void remove();
      }}
    >
      ×
    </button>
  );

  const renderEventButton = (event: CalendarEvent, compact = false) => (
    <div
      key={event.id ?? `${event.title}-${event.start}`}
      className={`flex w-full items-start gap-1 rounded-lg px-2 py-1 text-left ${compact ? "text-[10px]" : "text-xs"} ${event.status === "completed" ? "bg-gray-100 text-gray-400 line-through" : "bg-blue-50 text-blue-800 hover:bg-blue-100"}`}
      title={`${event.title}，按 Delete 删除，右键选择删除`}
      onKeyDown={(keyEvent) => handleDeleteKey(keyEvent, () => removeEvent(event))}
      onContextMenu={(mouseEvent) => handleContextDelete(mouseEvent, () => removeEvent(event))}
    >
      <button type="button" className="min-w-0 flex-1 text-left" onClick={() => selectEventForDetail(event)}>
        <span className="block truncate font-medium">{compact ? event.title : `${formatTime(event.start)} ${event.title}`}</span>
        {!compact ? <span className="text-[10px] opacity-60">{event.title}</span> : null}
      </button>
      {renderDeleteButton(`删除日程「${event.title}」`, () => removeEvent(event), compact)}
    </div>
  );

  const renderTaskDayButton = (day: BackgroundTaskDay, compact = false) => (
    <div
      key={day.id}
      className={`flex w-full items-start gap-1 rounded-lg px-2 py-1 text-left ${compact ? "text-[10px]" : "text-xs"} ${day.status === "completed" ? "bg-gray-100 text-gray-400 line-through" : day.status === "missed" ? "bg-red-50 text-red-700 hover:bg-red-100" : "bg-emerald-50 text-emerald-800 hover:bg-emerald-100"}`}
      title={`${day.description ?? day.title}，按 Delete 删除，右键选择删除`}
      onKeyDown={(keyEvent) => handleDeleteKey(keyEvent, () => removeTaskDay(day))}
      onContextMenu={(mouseEvent) => handleContextDelete(mouseEvent, () => removeTaskDay(day))}
    >
      <button type="button" className="min-w-0 flex-1 text-left" onClick={() => { setSelectedTaskDay(day); setSelected(null); }}>
        <span className="block truncate font-medium">{compact ? day.title : `${day.start_time ? day.start_time.slice(0, 5) : "任务"} ${day.title}`}</span>
        {!compact ? <span className="text-[10px] opacity-60">{day.title}</span> : null}
      </button>
      {renderDeleteButton(`删除任务日「${day.title}」`, () => removeTaskDay(day), compact)}
    </div>
  );

  const renderPlanDayButton = (day: JarvisPlanDay, compact = false) => (
    <div
      key={day.id}
      className={`flex w-full items-start gap-1 rounded-lg px-2 py-1 text-left ${compact ? "text-[10px]" : "text-xs"} ${day.status === "completed" ? "bg-gray-100 text-gray-400 line-through" : day.status === "missed" ? "bg-red-50 text-red-700 hover:bg-red-100" : "bg-purple-50 text-purple-800 hover:bg-purple-100"}`}
      title={`${day.description ?? day.title}，按 Delete 删除，右键选择删除`}
      onKeyDown={(keyEvent) => handleDeleteKey(keyEvent, () => removePlanDay(day))}
      onContextMenu={(mouseEvent) => handleContextDelete(mouseEvent, () => removePlanDay(day))}
    >
      <button type="button" className="min-w-0 flex-1 text-left" onClick={() => { setSelectedPlanDay(day); setSelectedTaskDay(null); setSelected(null); }}>
        <span className="block truncate font-medium">{compact ? day.title : `${day.start_time ? day.start_time.slice(0, 5) : "计划"} ${day.title}`}</span>
        {!compact ? <span className="text-[10px] opacity-60">{day.title}</span> : null}
      </button>
      {renderDeleteButton(`删除计划日「${day.title}」`, () => removePlanDay(day), compact)}
    </div>
  );

  const weekDays = Array.from({ length: 7 }, (_, index) => addDays(startOfWeek(currentDate), index));
  const monthDays = Array.from({ length: Math.round((range.end.getTime() - range.start.getTime()) / 86400000) }, (_, index) => addDays(range.start, index));
  const selectedMilestones = asList(selectedTask?.milestones);
  const selectedSubtasks = asList(selectedTask?.subtasks);
  const selectedCandidates = asList(selectedTask?.calendar_candidates);
  const selectedTaskDays = selectedTask ? taskDays.filter((day) => day.task_id === selectedTask.id) : [];
  const selectedPlanDays = selectedPlan ? planDays.filter((day) => day.plan_id === selectedPlan.id) : [];
  const selectedPlannerTaskId = selectedPlan ? selectedPlan.id : selectedTask?.id ?? null;
  const visibleTaskDays = calendarVisibleTaskDays(taskDays, planDays);
  const visiblePlanDays = calendarVisiblePlanDays(planDays);

  useEffect(() => {
    if (!open || !selectedPlan) { setPlanEvents([]); return; }
    jarvisScheduleApi.listPlanEvents(selectedPlan.id).then(setPlanEvents).catch(() => setPlanEvents([]));
  }, [open, selectedPlan?.id]);

  if (!open) return null;

  const startEditPlanDay = (day: JarvisPlanDay) => {
    setEditingPlanDay(day);
    setPlanDayForm({
      date: day.plan_date.slice(0, 10),
      startTime: day.start_time ? day.start_time.slice(0, 5) : "",
      endTime: day.end_time ? day.end_time.slice(0, 5) : "",
      title: day.title,
      description: day.description ?? "",
    });
  };
  const savePlanDayEdit = async () => {
    if (!editingPlanDay) return;
    await jarvisScheduleApi.updatePlanDay(editingPlanDay.id, {
      plan_date: planDayForm.date,
      start_time: planDayForm.startTime || null,
      end_time: planDayForm.endTime || null,
      title: planDayForm.title.trim() || editingPlanDay.title,
      description: planDayForm.description.trim() || null,
      reschedule_reason: "manual plan day edit",
    });
    setEditingPlanDay(null);
    await loadAll();
  };

  return (
    <div className="fixed inset-0 z-40 flex">
      <button type="button" aria-label="关闭日历遮罩" className="flex-1 bg-black/20" onClick={onClose} />
      <aside className="w-full max-w-[min(100vw,880px)] h-full bg-white shadow-2xl border-l border-gray-200 flex flex-col overflow-hidden">
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
          <button className={`px-3 py-1.5 rounded-lg text-xs border ${tab === "workbench" ? "bg-[var(--color-primary)] text-white border-transparent" : "border-gray-200 text-gray-600"}`} onClick={() => setTab("workbench")}>Maxwell 工作台</button>
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
            <div className="grid grid-cols-[minmax(0,1fr)_minmax(220px,260px)] min-h-0 flex-1 overflow-hidden">
              <main className="min-w-0 overflow-y-auto px-5 py-4 bg-gray-50/60">
                {loading ? <div className="py-10 text-center text-sm text-gray-400">正在加载日程…</div> : null}
                {loadError ? <div className="mb-3 rounded-xl border border-red-100 bg-red-50 p-3 text-xs text-red-700">{loadError}</div> : null}
                {!loading && mode === "day" && (
                  <div className="space-y-2">
                    {eventsForDay(events, currentDate).length === 0 && taskDaysForDay(visibleTaskDays, currentDate).length === 0 && planDaysForDay(visiblePlanDays, currentDate).length === 0 ? <div className="rounded-2xl border border-dashed border-gray-200 bg-white p-8 text-center text-sm text-gray-400">今天暂无日程</div> : null}
                    {eventsForDay(events, currentDate).map((event) => renderEventButton(event))}
                    {planDaysForDay(visiblePlanDays, currentDate).map((day) => renderPlanDayButton(day))}
                    {taskDaysForDay(visibleTaskDays, currentDate).map((day) => renderTaskDayButton(day))}
                  </div>
                )}
                {!loading && mode === "week" && (
                  <div className="grid grid-cols-7 gap-2">
                    {weekDays.map((day) => (
                      <div key={day.toISOString()} className={`rounded-2xl border bg-white p-2 min-h-72 ${sameDay(day, new Date()) ? "border-blue-300" : "border-gray-200"}`}>
                        <button className="text-xs font-semibold text-gray-700 mb-2" onClick={() => { setCurrentDate(day); setMode("day"); }}>{WEEKDAY_LABELS[day.getDay()]} {day.getMonth() + 1}/{day.getDate()}</button>
                        <div className="space-y-1">{eventsForDay(events, day).map((event) => renderEventButton(event))}{planDaysForDay(visiblePlanDays, day).map((planDay) => renderPlanDayButton(planDay))}{taskDaysForDay(visibleTaskDays, day).map((taskDay) => renderTaskDayButton(taskDay))}</div>
                      </div>
                    ))}
                  </div>
                )}
                {!loading && mode === "month" && (
                  <div className="grid grid-cols-7 gap-2">
                    {WEEKDAY_LABELS.map((label) => <div key={label} className="text-center text-xs font-semibold text-gray-400">{label}</div>)}
                    {monthDays.map((day) => {
                      const dayItems = [...eventsForDay(events, day), ...planDaysForDay(visiblePlanDays, day), ...taskDaysForDay(visibleTaskDays, day)];
                      const inMonth = day.getMonth() === currentDate.getMonth();
                      return (
                        <div key={day.toISOString()} className={`rounded-2xl border bg-white p-2 min-h-28 ${sameDay(day, new Date()) ? "border-blue-300" : "border-gray-200"} ${inMonth ? "" : "opacity-45"}`}>
                          <button className="text-xs font-semibold text-gray-700" onClick={() => { setCurrentDate(day); setMode("day"); }}>{day.getDate()}</button>
                          <div className="mt-1 space-y-1">{eventsForDay(events, day).slice(0, 3).map((event) => renderEventButton(event, true))}{planDaysForDay(visiblePlanDays, day).slice(0, Math.max(0, 3 - eventsForDay(events, day).length)).map((planDay) => renderPlanDayButton(planDay, true))}{taskDaysForDay(visibleTaskDays, day).slice(0, Math.max(0, 3 - eventsForDay(events, day).length - planDaysForDay(visiblePlanDays, day).length)).map((taskDay) => renderTaskDayButton(taskDay, true))}{dayItems.length > 3 && <div className="text-[10px] text-gray-400">+{dayItems.length - 3} 项</div>}</div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </main>
              <aside className="min-w-0 border-l border-gray-100 p-4 overflow-y-auto">
                <h3 className="text-sm font-semibold text-gray-800 mb-3">{editing ? "修改日程" : "新增日程"}</h3>
                <div className="space-y-2 text-xs">
                  <input className="w-full rounded-lg border border-gray-200 px-3 py-2" placeholder="日程标题" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
                  <input className="w-full rounded-lg border border-gray-200 px-3 py-2" type="date" value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} />
                  <div className="grid grid-cols-2 gap-2"><input className="rounded-lg border border-gray-200 px-3 py-2" type="time" value={form.startTime} onChange={(event) => setForm({ ...form, startTime: event.target.value })} /><input className="rounded-lg border border-gray-200 px-3 py-2" type="time" value={form.endTime} onChange={(event) => setForm({ ...form, endTime: event.target.value })} /></div>
                  <input className="w-full rounded-lg border border-gray-200 px-3 py-2" placeholder="地点（可选）" value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} />
                  <textarea className="w-full rounded-lg border border-gray-200 px-3 py-2 min-h-16" placeholder="备注（可选）" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
                  <label className="flex items-center gap-2 text-gray-600"><input type="checkbox" checked={form.route_required} onChange={(event) => setForm({ ...form, route_required: event.target.checked })} />需要路线规划</label>
                  <button className="w-full rounded-lg bg-[var(--color-primary)] px-3 py-2 text-white font-medium" onClick={saveForm}>{editing ? "保存修改" : "添加日程"}</button>
                  {editing && <button className="w-full rounded-lg border border-gray-200 px-3 py-2 text-gray-600" onClick={() => { setEditing(null); setForm(emptyForm(currentDate)); }}>取消修改</button>}
                </div>
                {selected && <section className="mt-5 rounded-2xl border border-blue-100 bg-blue-50/40 p-3 text-xs text-gray-700"><div className="flex items-start justify-between gap-3"><div><h3 className={`text-sm font-semibold text-gray-900 ${selected.status === "completed" ? "line-through text-gray-400" : ""}`}>{selected.title}</h3><p className="mt-1">{formatTime(selected.start)} - {formatTime(selected.end)} · {selected.status ?? "confirmed"}</p><p className="mt-1">来源：{eventSource(selected)}</p></div><button className="rounded-lg border border-blue-200 bg-white px-2 py-1 text-xs text-blue-700" onClick={() => startEdit(selected)}>编辑</button></div>{selected.created_reason && <p className="mt-2">原因：{selected.created_reason}</p>}{selected.location && <p className="mt-1">地点：{selected.location}</p>}{selected.notes && <p className="mt-1">备注：{selected.notes}</p>}<div className="mt-3 grid grid-cols-2 gap-2"><button className="rounded-lg border border-gray-200 px-2 py-1.5" onClick={() => markCompleted(selected)}>{selected.status === "completed" ? "恢复" : "划掉"}</button><button className="rounded-lg border border-red-200 px-2 py-1.5 text-red-600" onClick={() => removeEvent(selected)}>删除</button></div></section>}
                {selectedPlanDay && <div className="mt-5 border-t border-gray-100 pt-4 text-xs text-gray-600"><h3 className={`text-sm font-semibold text-gray-900 ${selectedPlanDay.status === "completed" ? "line-through text-gray-400" : ""}`}>{selectedPlanDay.title}</h3><p className="mt-1">{formatDate(selectedPlanDay.plan_date)} · {selectedPlanDay.start_time ? selectedPlanDay.start_time.slice(0, 5) : "未设时间"} · {taskDayStatusLabel(selectedPlanDay.status)}</p>{selectedPlanDay.description && <p className="mt-2">{selectedPlanDay.description}</p>}<div className="mt-3 grid grid-cols-3 gap-2"><button className="rounded-lg border border-purple-200 px-2 py-1.5 text-purple-700 disabled:text-gray-400 disabled:border-gray-200" disabled={selectedPlanDay.status === "completed"} onClick={() => completePlanDay(selectedPlanDay)}>标记完成</button><button className="rounded-lg border border-gray-200 px-2 py-1.5 text-gray-700" onClick={() => startEditPlanDay(selectedPlanDay)}>修改</button><button className="rounded-lg border border-red-200 px-2 py-1.5 text-red-600" onClick={() => removePlanDay(selectedPlanDay)}>删除</button></div></div>}
                {selectedPlanDay && <button className="mt-2 w-full rounded-lg border border-gray-200 px-2 py-1.5 text-xs text-gray-700" onClick={() => startEditPlanDay(selectedPlanDay)}>Edit selected plan day</button>}
                {selectedTaskDay && <div className="mt-5 border-t border-gray-100 pt-4 text-xs text-gray-600"><h3 className={`text-sm font-semibold text-gray-900 ${selectedTaskDay.status === "completed" ? "line-through text-gray-400" : ""}`}>{selectedTaskDay.title}</h3><p className="mt-1">{formatDate(selectedTaskDay.plan_date)} · {selectedTaskDay.start_time ? selectedTaskDay.start_time.slice(0, 5) : "未设时间"} · {taskDayStatusLabel(selectedTaskDay.status)}</p>{selectedTaskDay.description && <p className="mt-2">{selectedTaskDay.description}</p>}<div className="mt-3 grid grid-cols-2 gap-2"><button className="rounded-lg border border-emerald-200 px-2 py-1.5 text-emerald-700 disabled:text-gray-400 disabled:border-gray-200" disabled={selectedTaskDay.status === "completed"} onClick={() => completeTaskDay(selectedTaskDay)}>标记完成</button><button className="rounded-lg border border-red-200 px-2 py-1.5 text-red-600" onClick={() => removeTaskDay(selectedTaskDay)}>删除</button></div></div>}
              </aside>
            </div>
          </>
        ) : tab === "workbench" ? (
          <div className="min-h-0 flex-1 overflow-y-auto bg-gray-50/60 p-5">
            <section className="rounded-2xl border border-gray-200 bg-white p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-base font-semibold text-gray-900">Maxwell 工作台</h3>
                  <p className="mt-1 text-xs text-gray-500">集中查看已推送给 Maxwell 的今日执行项。</p>
                  {workbenchMessage ? <p className={`mt-2 text-xs ${workbenchMessage.startsWith("推送失败") ? "text-red-600" : "text-emerald-600"}`}>{workbenchMessage}</p> : null}
                </div>
                <button className="rounded-lg border border-purple-200 bg-white px-3 py-1.5 text-xs text-purple-700 disabled:text-gray-400" disabled={workbenchPushLoading} onClick={() => void pushTodayTasksToWorkbench()}>{workbenchPushLoading ? "推送中…" : "推送今日任务"}</button>
              </div>
            </section>
            {loading ? <div className="py-8 text-center text-sm text-gray-400">正在加载工作台…</div> : null}
            {loadError ? <div className="mt-3 rounded-xl border border-red-100 bg-red-50 p-3 text-xs text-red-700">{loadError}</div> : null}
            {!loading && workbenchItems.length === 0 ? <div className="mt-3 rounded-2xl border border-dashed border-gray-200 bg-white p-8 text-center text-sm text-gray-400">暂无工作台任务。可先运行“推送今日任务”。</div> : null}
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {workbenchItems.map((item) => <article key={item.id} className="rounded-2xl border border-gray-200 bg-white p-4 text-sm">
                <div className="flex items-start justify-between gap-3"><h4 className="font-medium text-gray-900">{item.title}</h4><span className="shrink-0 rounded-full bg-purple-50 px-2 py-0.5 text-xs text-purple-600">{taskDayStatusLabel(item.status)}</span></div>
                {item.description ? <p className="mt-2 text-xs text-gray-500">{item.description}</p> : null}
                <div className={`mt-3 rounded-xl p-2 text-xs ${item.live_state?.is_overdue ? "bg-amber-50 text-amber-700" : "bg-blue-50 text-blue-700"}`}>
                  <div className="font-medium">{workbenchLiveStateLabel(item)}</div>
                  <div className="mt-1 opacity-80">依据：{workbenchBasisLabel(item.live_state?.basis)}{item.live_state?.checked_at ? ` · ${formatDateTime(item.live_state.checked_at)}` : ""}</div>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-gray-500">
                  <div className="rounded-xl bg-gray-50 p-2"><div className="text-gray-400">计划日期</div><div className="mt-1 text-gray-700">{formatDate(item.plan_date ?? item.due_at)}</div></div>
                  <div className="rounded-xl bg-gray-50 p-2"><div className="text-gray-400">截止时间</div><div className="mt-1 text-gray-700">{formatDateTime(item.due_at)}</div></div>
                  <div className="rounded-xl bg-gray-50 p-2"><div className="text-gray-400">来源</div><div className="mt-1 text-gray-700">{item.plan_day_id ? "计划日" : item.task_day_id ? "长期任务日" : "未记录"}</div></div>
                  <div className="rounded-xl bg-gray-50 p-2"><div className="text-gray-400">Agent</div><div className="mt-1 text-gray-700">{item.agent_id || "maxwell"}</div></div>
                </div>
                {item.work_logs?.length ? <div className="mt-3 rounded-xl border border-gray-100 bg-gray-50 p-3 text-xs">
                  <div className="font-medium text-gray-700">Maxwell 工作记录</div>
                  <div className="mt-2 space-y-2">
                    {item.work_logs.slice(-4).map((log, index) => <div key={`${log.at}-${index}`} className="border-l-2 border-purple-200 pl-2">
                      <div className="text-gray-700">{log.event}</div>
                      {log.detail ? <div className="mt-0.5 text-gray-500">{log.detail}</div> : null}
                      <div className="mt-0.5 text-[10px] text-gray-400">{formatDateTime(log.at)} · {log.actor || "maxwell"}</div>
                    </div>)}
                  </div>
                </div> : null}
              </article>)}
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-[minmax(260px,300px)_minmax(0,1fr)] min-h-0 flex-1 overflow-hidden">
            <aside className="min-w-0 border-r border-gray-100 p-4 overflow-y-auto bg-gray-50/60">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-800">任务清单</h3>
                <div className="flex items-center gap-2"><span className="text-xs text-gray-400">{plannerTasks.length} 个</span><button className="rounded-lg border border-purple-200 bg-white px-2 py-1 text-xs text-purple-700" onClick={startNewPlan}>新建长期计划</button></div>
              </div>
              {loading ? <div className="py-8 text-center text-sm text-gray-400">正在加载任务…</div> : null}
              {loadError ? <div className="mb-3 rounded-xl border border-red-100 bg-red-50 p-3 text-xs text-red-700">{loadError}</div> : null}
              {editingPlan ? <div className="mb-3 rounded-2xl border border-purple-200 bg-white p-3 text-xs text-gray-600">
                <div className="mb-2 font-medium text-gray-800">{editingPlan === "new" ? "新建长期计划" : "编辑计划信息"}</div>
                <div className="space-y-2">
                  <input className="w-full rounded-lg border border-gray-200 px-2 py-1.5" placeholder="计划标题，例如：雅思备考" value={planForm.title} onChange={(event) => setPlanForm((current) => ({ ...current, title: event.target.value }))} />
                  <textarea className="w-full rounded-lg border border-gray-200 px-2 py-1.5" rows={2} placeholder="目标说明" value={planForm.goal} onChange={(event) => setPlanForm((current) => ({ ...current, goal: event.target.value }))} />
                  <input className="w-full rounded-lg border border-gray-200 px-2 py-1.5" placeholder="原始需求，例如：我要考雅思" value={planForm.originalUserRequest} onChange={(event) => setPlanForm((current) => ({ ...current, originalUserRequest: event.target.value }))} />
                  <input className="w-full rounded-lg border border-gray-200 px-2 py-1.5" type="date" value={planForm.targetDate} onChange={(event) => setPlanForm((current) => ({ ...current, targetDate: event.target.value }))} />
                </div>
                {planFormMessage ? <div className={`mt-2 ${planFormMessage.startsWith("保存失败") || planFormMessage.includes("不能为空") ? "text-red-600" : "text-emerald-600"}`}>{planFormMessage}</div> : null}
                <div className="mt-3 flex gap-2"><button className="rounded-lg bg-purple-600 px-3 py-1.5 text-white disabled:bg-gray-300" disabled={planFormSaving} onClick={() => void savePlanForm()}>{planFormSaving ? "保存中…" : "保存"}</button><button className="rounded-lg border border-gray-200 px-3 py-1.5 text-gray-600" onClick={() => setEditingPlan(null)}>取消</button></div>
              </div> : planFormMessage ? <div className="mb-3 rounded-xl bg-emerald-50 p-3 text-xs text-emerald-700">{planFormMessage}</div> : null}
              {!loading && plannerTasks.length === 0 ? <div className="rounded-2xl border border-dashed border-gray-200 bg-white p-4 text-sm text-gray-400">暂无计划。和 Maxwell 说一个长期目标后，会在这里看到计划清单。</div> : null}
              <div className="space-y-2">
                {plannerTasks.map((item) => {
                  const isPlan = item.item_type === "plan";
                  const plan = isPlan ? plans.find((candidate) => candidate.id === item.id) ?? item.payload as unknown as JarvisPlan : null;
                  const task = !isPlan ? tasks.find((candidate) => candidate.id === item.id) ?? item.payload as unknown as BackgroundTask : null;
                  return <button key={`${item.item_type}-${item.id}`} className={`w-full rounded-2xl border p-3 text-left ${selectedPlannerTaskId === item.id ? (isPlan ? "border-purple-300 bg-purple-50" : "border-blue-300 bg-blue-50") : "border-gray-200 bg-white hover:bg-gray-50"}`} onClick={() => { setSelectedPlan(plan); setSelectedTask(task); }}>
                    <div className="font-medium text-sm text-gray-800 line-clamp-2">{item.title}</div>
                    <div className="mt-1 text-xs text-gray-500">{item.goal || item.original_user_request || (task ? taskDateSummary(task) : "")}</div>
                    <div className="mt-2 flex items-center justify-between text-[11px]"><span className={`rounded-full px-2 py-0.5 ${isPlan ? "bg-purple-100 text-purple-600" : "bg-gray-100 text-gray-500"}`}>{item.task_type}</span><span className={isPlan ? "text-purple-600" : "text-blue-600"}>{taskStatusLabel(item.status)}</span></div>
                  </button>;
                })}
              </div>
            </aside>
            <main className="overflow-y-auto p-5">
              {selectedPlan ? (
                <div className="space-y-5">
                  <section className="rounded-2xl border border-purple-200 bg-purple-50/40 p-4">
                    <div className="flex items-start justify-between gap-4"><div><h3 className="text-lg font-semibold text-gray-900">{selectedPlan.title}</h3><p className="mt-1 text-sm text-gray-500">{selectedPlan.goal || selectedPlan.original_user_request}</p></div><div className="flex shrink-0 items-center gap-2"><span className="rounded-full bg-purple-100 px-3 py-1 text-xs text-purple-600">{taskStatusLabel(selectedPlan.status)}</span><button className="rounded-lg border border-purple-200 bg-white px-2 py-1 text-xs text-purple-700" onClick={() => startEditPlan(selectedPlan)}>编辑计划信息</button><button className="rounded-lg border border-red-200 bg-white px-2 py-1 text-xs text-red-600 disabled:text-gray-400 disabled:border-gray-200" disabled={selectedPlan.status === "deleted"} onClick={() => deletePlan(selectedPlan)}>删除任务</button></div></div>
                  </section>
                  <section className="rounded-2xl border border-gray-200 p-4">
                    <div className="mb-3">
                      <h4 className="text-sm font-semibold text-gray-800">每日计划</h4>
                      <div className="mt-1 text-xs text-gray-400">点击计划日查看详情，可修改或删除。</div>
                    </div>
                    <div className="space-y-2">{selectedPlanDays.length === 0 ? <p className="text-sm text-gray-400">暂无每日计划</p> : selectedPlanDays.map((day) => <div key={day.id} className={`rounded-xl p-3 text-sm ${selectedPlanDay?.id === day.id ? "bg-purple-100" : "bg-purple-50"} text-purple-950`} onClick={() => selectPlanDayForDetail(day)}><div className="flex items-start justify-between gap-3"><div><div className={`font-medium ${day.status === "completed" ? "line-through text-gray-400" : ""}`}>{day.title}</div><div className="mt-1 text-xs text-purple-700">{formatDate(day.plan_date)} {day.start_time ? `· ${day.start_time.slice(0, 5)}` : ""} · {taskDayStatusLabel(day.status)}</div>{day.description && <p className="mt-1 text-xs text-purple-800">{day.description}</p>}</div><div className="flex shrink-0 gap-1"><button className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs text-gray-600" onClick={(event) => { event.stopPropagation(); startEditPlanDay(day); }}>修改</button><button className="rounded-lg border border-red-200 bg-white px-2 py-1 text-xs text-red-600" onClick={(event) => { event.stopPropagation(); void removePlanDay(day); }}>删除</button></div></div></div>)}</div>
                  </section>
                  {editingPlanDay && <section className="rounded-2xl border border-purple-200 bg-white p-4"><h4 className="text-sm font-semibold text-gray-800 mb-3">Edit plan day</h4><div className="grid grid-cols-2 gap-2 text-xs"><input className="rounded-lg border px-2 py-1.5" value={planDayForm.title} onChange={(e) => setPlanDayForm((v) => ({ ...v, title: e.target.value }))} /><input type="date" className="rounded-lg border px-2 py-1.5" value={planDayForm.date} onChange={(e) => setPlanDayForm((v) => ({ ...v, date: e.target.value }))} /><input type="time" className="rounded-lg border px-2 py-1.5" value={planDayForm.startTime} onChange={(e) => setPlanDayForm((v) => ({ ...v, startTime: e.target.value }))} /><input type="time" className="rounded-lg border px-2 py-1.5" value={planDayForm.endTime} onChange={(e) => setPlanDayForm((v) => ({ ...v, endTime: e.target.value }))} /></div><div className="mt-3 flex gap-2"><button className="rounded-lg bg-purple-600 px-3 py-1.5 text-xs text-white" onClick={savePlanDayEdit}>Save</button><button className="rounded-lg border px-3 py-1.5 text-xs text-gray-600" onClick={() => setEditingPlanDay(null)}>Cancel</button></div></section>}
                  <section className="rounded-2xl border border-gray-200 p-4"><h4 className="text-sm font-semibold text-gray-800 mb-3">Plan change history</h4><div className="space-y-2">{planEvents.length === 0 ? <p className="text-sm text-gray-400">No changes yet</p> : planEvents.slice(0, 8).map((event) => <div key={event.id} className="rounded-xl bg-gray-50 p-3 text-xs text-gray-600"><div className="font-medium text-gray-800">{event.event_type}</div><div className="mt-1">{formatDateTime(new Date(event.created_at * 1000).toISOString())}</div></div>)}</div></section>
                </div>
              ) : !selectedTask ? <div className="rounded-2xl border border-dashed border-gray-200 p-8 text-center text-sm text-gray-400">选择一个计划或任务查看每日安排。</div> : (
                <div className="space-y-5">
                  <section className="rounded-2xl border border-gray-200 p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h3 className="text-lg font-semibold text-gray-900">{selectedTask.title}</h3>
                        <p className="mt-1 text-sm text-gray-500">{selectedTask.goal || selectedTask.original_user_request}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2"><span className="rounded-full bg-blue-50 px-3 py-1 text-xs text-blue-600">{taskStatusLabel(selectedTask.status)}</span><button className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs text-gray-600 disabled:text-gray-400" disabled={backgroundTaskActionLoading === "archived"} onClick={() => void updateSelectedBackgroundTaskStatus(selectedTask, "archived")}>{backgroundTaskActionLoading === "archived" ? "归档中…" : "归档历史任务"}</button><button className="rounded-lg border border-red-200 bg-white px-2 py-1 text-xs text-red-600 disabled:text-gray-400" disabled={backgroundTaskActionLoading === "deleted"} onClick={() => void updateSelectedBackgroundTaskStatus(selectedTask, "deleted")}>{backgroundTaskActionLoading === "deleted" ? "删除中…" : "删除历史任务"}</button></div>
                    </div>
                    {backgroundTaskMessage ? <div className={`mt-2 text-xs ${backgroundTaskMessage.includes("失败") ? "text-red-600" : "text-emerald-600"}`}>{backgroundTaskMessage}</div> : null}
                    <div className="mt-4 grid grid-cols-3 gap-3 text-xs">
                      <div className="rounded-xl bg-gray-50 p-3"><div className="text-gray-400">日期范围</div><div className="mt-1 font-medium text-gray-700">{taskDateSummary(selectedTask)}</div></div>
                      <div className="rounded-xl bg-gray-50 p-3"><div className="text-gray-400">来源 Agent</div><div className="mt-1 font-medium text-gray-700">{selectedTask.source_agent || "未记录"}</div></div>
                      <div className="rounded-xl bg-gray-50 p-3"><div className="text-gray-400">任务类型</div><div className="mt-1 font-medium text-gray-700">{selectedTask.task_type}</div></div>
                    </div>
                  </section>

                  <section className="rounded-2xl border border-gray-200 p-4">
                    <h4 className="text-sm font-semibold text-gray-800 mb-3">每日计划</h4>
                    <div className="space-y-2">{selectedTaskDays.length === 0 ? <p className="text-sm text-gray-400">暂无每日计划</p> : selectedTaskDays.map((day) => <div key={day.id} className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-950"><div className="flex items-start justify-between gap-3"><div><div className={`font-medium ${day.status === "completed" ? "line-through text-gray-400" : ""}`}>{day.title}</div><div className="mt-1 text-xs text-emerald-700">{formatDate(day.plan_date)} {day.start_time ? `· ${day.start_time.slice(0, 5)}` : ""} · {taskDayStatusLabel(day.status)}</div>{day.description && <p className="mt-1 text-xs text-emerald-800">{day.description}</p>}</div><div className="flex shrink-0 gap-1"><button className="rounded-lg border border-emerald-200 bg-white px-2 py-1 text-xs text-emerald-700 disabled:text-gray-400" disabled={day.status === "completed"} onClick={() => completeTaskDay(day)}>完成</button><button className="rounded-lg border border-red-200 bg-white px-2 py-1 text-xs text-red-600" onClick={() => removeTaskDay(day)}>删除</button></div></div></div>)}</div>
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
