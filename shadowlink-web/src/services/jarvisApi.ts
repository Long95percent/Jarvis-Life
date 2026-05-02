// shadowlink-web/src/services/jarvisApi.ts
const BASE = "/api/v1/jarvis";

export type BehaviorEventType =
  | "heartbeat"
  | "closed"
  | "visibility_hidden"
  | "visibility_visible"
  | "idle_start"
  | "idle_end"
  | "sleep"
  | "resume"
  | "app_opened"
  | "app_closed"
  | "app_minimized"
  | "app_activated"
  | "app_restored";

export interface CalendarEvent {
  id?: string;
  title: string;
  start: string;
  end: string;
  stress_weight?: number;
  location?: string | null;
  notes?: string | null;
  source?: string;
  source_agent?: string | null;
  created_reason?: string | null;
  status?: "pending_confirmation" | "confirmed" | "completed" | "postponed" | "conflict" | string;
  route_required?: boolean;
}

export interface TimeWindow {
  start: string;
  end: string;
  label?: string;
}

export interface LifeContext {
  stress_level: number;
  schedule_density: number;
  sleep_quality: number;
  mood_trend: "positive" | "neutral" | "negative" | "unknown";
  last_updated: string;
  active_events?: CalendarEvent[];
  free_windows?: TimeWindow[];
  source_agent?: string;
}

export interface JarvisTimeContext {
  timezone: string;
  timezone_abbr: string;
  utc_offset: string;
  local_iso: string;
  local_date: string;
  local_time: string;
  weekday: string;
  location_label: string;
}

export interface JarvisAgent {
  id: string;
  name: string;
  role: string;
  color: string;
  icon: string;
}

export interface ProactiveMessage {
  id: string;
  agent_id: string;
  agent_name: string;
  content: string;
  trigger: string;
  priority?: string;
  status?: "pending" | "delivered" | "read" | "dismissed" | string;
  created_at: string;
  delivered_at?: string | null;
  read_at?: string | null;
  dismissed_at?: string | null;
  read: boolean;
}

export interface EscalationHint {
  scenario_id: string;
  severity: "info" | "suggest" | "urgent";
  reason: string;
  countdown_seconds: number;
}

export interface TeamCollaborationRequest {
  goal: string;
  user_message?: string;
  agents?: string[];
  source_agent?: string;
  session_id?: string;
}

export interface TeamCollaborationResponse {
  type: "team.collaboration";
  ok: boolean;
  goal: string;
  participants: string[];
  specialists: Array<Record<string, unknown>>;
  summary: string;
  aligned_actions: string[];
  conflicts: string[];
  followups: string[];
  memory_saved?: boolean;
  error?: string;
}

export interface ActionResult {
  type: string;            // e.g. "calendar.add" | "context.set"
  ok: boolean;
  error?: string;
  pending_confirmation?: boolean;
  confirmation_id?: string;
  pending_action_id?: string;
  tool_name?: string;
  arguments?: Record<string, unknown>;
  description?: string;
  // calendar.add returns:
  event_id?: string;
  title?: string;
  start?: string;
  end?: string;
  new_schedule_density?: number;
  // context.set returns:
  fields?: Record<string, unknown>;
}

export interface BackgroundTask {
  id: string;
  title: string;
  task_type: string;
  status: string;
  source_agent?: string | null;
  original_user_request: string;
  goal?: string | null;
  time_horizon: Record<string, unknown>;
  milestones: Array<Record<string, unknown>>;
  subtasks: Array<Record<string, unknown>>;
  calendar_candidates: Array<Record<string, unknown>>;
  notes?: string | null;
  created_at: number;
  updated_at: number;
}

export interface BackgroundTaskDay {
  id: string;
  task_id: string;
  plan_date: string;
  title: string;
  description?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  estimated_minutes?: number | null;
  status: "pending" | "pushed" | "completed" | "missed" | "rescheduled" | "cancelled" | string;
  calendar_event_id?: string | null;
  workbench_item_id?: string | null;
  sort_order: number;
  llm_payload: Record<string, unknown>;
  created_at: number;
  updated_at: number;
}

export interface MaxwellWorkbenchItem {
  id: string;
  task_day_id?: string | null;
  plan_day_id?: string | null;
  plan_id?: string | null;
  agent_id: string;
  title: string;
  description?: string | null;
  plan_date?: string | null;
  due_at?: string | null;
  status: "todo" | "doing" | "done" | "cancelled" | string;
  pushed_at?: number | null;
  created_at: number;
  updated_at: number;
}

export interface ChatResponse {
  agent_id: string;
  agent_name: string;
  content: string;
  escalation?: EscalationHint | null;
  actions?: ActionResult[] | null;
  routing?: Record<string, unknown> | null;
  timing?: Record<string, unknown> | null;
}

function parseSSEFrames(buffer: string): { frames: Array<{ event: string; data: string }>; remainder: string } {
  const frames: Array<{ event: string; data: string }> = [];
  const parts = buffer.split(/\n\n/);
  const remainder = parts.pop() ?? "";
  for (const part of parts) {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of part.split(/\n/)) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (dataLines.length > 0) frames.push({ event, data: dataLines.join("\n") });
  }
  return { frames, remainder };
}

export interface JarvisPlan {
  id: string;
  title: string;
  plan_type: "short_term" | "long_term" | string;
  status: string;
  source_agent?: string | null;
  source_pending_id?: string | null;
  source_background_task_id?: string | null;
  original_user_request: string;
  goal?: string | null;
  time_horizon: Record<string, unknown>;
  raw_payload: Record<string, unknown>;
  created_at: number;
  updated_at: number;
}

export interface JarvisPlanDay {
  id: string;
  plan_id: string;
  plan_date: string;
  title: string;
  description?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  estimated_minutes?: number | null;
  status: "pending" | "scheduled" | "pushed" | "completed" | "missed" | "rescheduled" | "cancelled" | string;
  calendar_event_id?: string | null;
  workbench_item_id?: string | null;
  source_task_day_id?: string | null;
  sort_order: number;
  raw_payload: Record<string, unknown>;
  reschedule_reason?: string | null;
  created_at: number;
  updated_at: number;
}

export interface PlanWritePayload {
  title: string;
  plan_type?: string;
  status?: string;
  original_user_request?: string;
  goal?: string | null;
  time_horizon?: Record<string, unknown>;
  raw_payload?: Record<string, unknown>;
}

export interface PlannerTaskItem {
  item_type: "plan" | "background_task" | string;
  id: string;
  title: string;
  status: string;
  task_type: string;
  source_agent?: string | null;
  source_background_task_id?: string | null;
  original_user_request: string;
  goal?: string | null;
  time_horizon: Record<string, unknown>;
  created_at?: number | null;
  updated_at?: number | null;
  payload: Record<string, unknown>;
}

export interface PlannerTaskCleanupResult {
  execute: boolean;
  duplicate_group_count: number;
  duplicate_task_count: number;
  deleted_tasks: number;
  groups: Array<Record<string, unknown>>;
  deleted_task_ids?: string[];
}

export interface ProjectPlanCalendarResult {
  projected_count: number;
  projected: Array<{ plan_day: JarvisPlanDay; calendar_event: CalendarEvent }>;
  skipped?: Array<{ id?: string; reason?: string }>;
}

export interface PlanRescheduleResult {
  plan_id: string;
  changed_count: number;
  changed: Array<Record<string, unknown>>;
}

export interface PlanMergeResult {
  source_plan: JarvisPlan;
  target_plan: JarvisPlan;
  moved_day_count: number;
  moved_day_ids: string[];
}

export interface PlanSplitResult {
  source_plan: JarvisPlan;
  new_plan: JarvisPlan;
  moved_day_count: number;
  moved_day_ids: string[];
}

export interface PlanDayBulkUpdateResult {
  changed_count: number;
  changed: JarvisPlanDay[];
  calendar_events: unknown[];
}

export interface SecretaryPlanRequest {
  intent: "short_schedule" | "long_plan" | "reschedule_plan" | string;
  message: string;
  today?: string | null;
  plan_id?: string | null;
  plan_day_ids?: string[];
  timezone?: string | null;
  auto_project_calendar?: boolean;
}

export interface SecretaryPlanResult {
  intent: string;
  summary?: string | null;
  plan?: JarvisPlan | null;
  plan_days?: JarvisPlan[] | JarvisPlanDay[];
  changed_count?: number;
  calendar_events?: unknown[];
  warnings?: string[];
}

export interface PlannerDailyMaintenanceResult {
  routine_id?: string;
  skipped?: boolean;
  already_ran?: boolean;
  today?: string;
  missed?: {
    background_task_days?: unknown[];
    plan_days?: unknown[];
  };
  reschedule?: {
    changed_count?: number;
    changed?: unknown[];
    plan_id?: string;
  } | null;
  pushed?: unknown[];
  pushed_count?: number;
  message?: string;
}

export interface PlannerOverdueMissedResult {
  today: string;
  missed_count: number;
  background_task_days: BackgroundTaskDay[];
  plan_days: JarvisPlanDay[];
}

export interface PlannerCalendarItem {
  item_type: "calendar_event" | "plan_day" | "background_task_day" | string;
  id: string;
  date: string;
  title: string;
  status: string;
  start?: string;
  end?: string;
  start_time?: string | null;
  end_time?: string | null;
  plan_id?: string;
  task_id?: string;
  calendar_event_id?: string | null;
  payload: Record<string, unknown>;
}

export interface PlannerConflict {
  start: string;
  end: string;
  items: PlannerCalendarItem[];
  reason: string;
}

export interface PlannerFreeWindow {
  start: string;
  end: string;
  minutes: number;
}

export interface PlannerCalendarResponse {
  items: PlannerCalendarItem[];
  conflicts: PlannerConflict[];
  free_windows: PlannerFreeWindow[];
}

export interface AgentEvent {
  id: string;
  event_type: string;
  agent_id?: string | null;
  plan_id?: string | null;
  plan_day_id?: string | null;
  payload: Record<string, unknown>;
  created_at: number;
}

export interface ChatHistoryTurn {
  role: "user" | "agent";
  content: string;
  actions?: ActionResult[];
  timestamp: number;
}

export interface RoundtableTurn {
  role: string;
  speaker_name: string;
  content: string;
  timestamp: number;
}

export interface JarvisMemory {
  id: number;
  memory_kind: string;
  content: string;
  source_agent: string;
  session_id?: string | null;
  source_text?: string | null;
  structured_payload: Record<string, unknown>;
  sensitivity: "normal" | "private" | "sensitive" | string;
  confidence: number;
  importance: number;
  created_at: number;
  updated_at: number;
  last_used_at?: number | null;
  status: string;
}

export interface ConversationHistoryItem {
  id: string;
  conversation_type: "private_chat" | "roundtable" | "brainstorm" | string;
  title: string;
  agent_id?: string | null;
  scenario_id?: string | null;
  session_id: string;
  route_payload: Record<string, unknown>;
  status: string;
  created_at: number;
  updated_at: number;
  last_opened_at?: number | null;
}

export interface BehaviorObservation {
  id: string;
  date: string;
  session_id?: string | null;
  agent_id: string;
  observation_type: string;
  expected_bedtime?: string | null;
  expected_wake?: string | null;
  actual_first_active_at?: number | null;
  actual_last_active_at?: number | null;
  deviation_minutes?: number | null;
  duration_minutes?: number | null;
  source: string;
  created_at: number;
}

export interface StressSignal {
  id: string;
  date: string;
  signal_type: string;
  severity: string;
  score: number;
  reason: string;
  source_refs: Array<Record<string, unknown>>;
  source: string;
  created_at: number;
}

export interface EmotionObservation {
  id: string;
  session_id?: string | null;
  turn_id?: number | null;
  agent_id: string;
  primary_emotion: string;
  secondary_emotions: string[];
  valence: number;
  arousal: number;
  stress_score: number;
  fatigue_score: number;
  risk_level: string;
  confidence: number;
  evidence_summary: string;
  signals_json: string[];
  source: string;
  created_at: number;
}

export interface CareTrigger {
  id: string;
  trigger_type: string;
  severity: string;
  reason: string;
  evidence_ids: Array<Record<string, unknown>>;
  status: string;
  message_id?: string | null;
  created_at: string | number;
}

export interface CareTrendPoint {
  date: string;
  mood_score: number | null;
  stress_score: number | null;
  energy_score: number | null;
  sleep_risk_score: number | null;
  schedule_pressure_score: number | null;
  dominant_emotions: string[];
  risk_flags: string[];
  summary?: string | null;
  confidence: number;
}

export interface CareTrendDetail {
  date?: string;
  snapshot: CareTrendPoint;
  emotion_observations: EmotionObservation[];
  stress_signals: StressSignal[];
  behavior_observations: BehaviorObservation[];
  care_triggers: CareTrigger[];
  positive_events: string[];
  negative_events: string[];
  explanations: string[];
}

export interface CareTrendsResponse {
  range: "week" | "month" | "year" | string;
  start: string;
  end: string;
  tracking_enabled?: boolean;
  series: CareTrendPoint[];
  details: Record<string, CareTrendDetail>;
}


async function errorFromResponse(res: Response, fallback: string): Promise<Error> {
  let detail = fallback;
  try {
    const data = await res.json();
    if (data?.detail?.code === "duplicate_calendar_event") {
      const duplicates = Array.isArray(data.detail.duplicates) ? data.detail.duplicates : [];
      const duplicateTitles = duplicates
        .map((item: Record<string, unknown>) => typeof item.title === "string" ? item.title : "")
        .filter(Boolean)
        .slice(0, 3);
      detail = duplicateTitles.length > 0
        ? `已存在同名日程：${duplicateTitles.join("、")}。为避免重复安排，本次没有写入。`
        : "已存在同名日程。为避免重复安排，本次没有写入。";
    } else if (typeof data?.detail?.message === "string") {
      detail = data.detail.message;
      if (typeof data.detail.suggestion === "string") detail += `\n建议：${data.detail.suggestion}`;
      if (typeof data.detail.stage === "string") detail += `\n阶段：${data.detail.stage}`;
    } else if (typeof data?.detail === "string") detail = data.detail;
    else if (typeof data?.message === "string") detail = data.message;
    else if (typeof data?.error === "string") detail = data.error;
  } catch {
    const text = await res.text().catch(() => "");
    if (text) detail = text;
  }
  const error = new Error(detail) as Error & { status?: number };
  error.status = res.status;
  return error;
}

export interface PendingAction {
  id: string;
  action_type: string;
  tool_name: string;
  agent_id: string;
  session_id?: string | null;
  title: string;
  arguments: Record<string, unknown>;
  status: "pending" | "confirmed" | "cancelled" | string;
  created_at: number;
  updated_at: number;
}

export interface RoundtableDecisionResult {
  id: string;
  session_id: string;
  mode: "decision" | string;
  status: "draft" | "accepted" | string;
  summary: string;
  options: Array<{ id?: string; title?: string; description?: string }>;
  recommended_option: string;
  tradeoffs: Array<{ option?: string; pros?: string[]; cons?: string[] }>;
  actions: Array<Record<string, unknown>>;
  context?: Record<string, unknown>;
  handoff_target: string;
  result_json?: Record<string, unknown>;
  user_choice?: string | null;
  handoff_status?: string;
  source_session_id?: string | null;
  source_agent_id?: string | null;
  pending_action_id?: string | null;
}

export interface RoundtableBrainstormResult {
  id: string;
  session_id: string;
  mode: "brainstorm" | string;
  status: "draft" | "saved" | "handoff_pending" | string;
  summary: string;
  themes: Array<{ title?: string; summary?: string }>;
  ideas: Array<{ id?: string; title?: string; source_agent?: string; round?: number }>;
  tensions: Array<{ title?: string; description?: string }>;
  followup_questions: string[];
  c_artifacts?: Record<string, unknown> | null;
  ranked_activities?: Array<Record<string, unknown>>;
  risks?: Array<Record<string, unknown>>;
  minimum_validation_steps?: string[];
  context?: Record<string, unknown>;
  save_as_memory: boolean;
  handoff_target: string;
  result_json?: Record<string, unknown>;
  user_choice?: string | null;
  handoff_status?: string;
  source_session_id?: string | null;
  source_agent_id?: string | null;
  pending_action_id?: string | null;
}

export interface RoundtableReturnResponse {
  source_session_id: string;
  source_agent_id: string;
  return_turn_id?: number | null;
  summary: string;
  result?: RoundtableDecisionResult | RoundtableBrainstormResult | null;
}

export const jarvisApi = {
  async getTimeContext(browserTimezone?: string): Promise<JarvisTimeContext> {
    const query = browserTimezone ? `?browser_timezone=${encodeURIComponent(browserTimezone)}` : "";
    const res = await fetch(`${BASE}/time/context${query}`);
    if (!res.ok) throw new Error("Failed to fetch time context");
    return res.json();
  },

  async getContext(): Promise<LifeContext> {
    const res = await fetch(`${BASE}/context`);
    if (!res.ok) throw new Error("Failed to fetch life context");
    return res.json();
  },

  async updateContext(fields: Partial<LifeContext>): Promise<LifeContext> {
    const res = await fetch(`${BASE}/context`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fields),
    });
    if (!res.ok) throw new Error("Failed to update context");
    return res.json();
  },

  async listAgents(): Promise<JarvisAgent[]> {
    const res = await fetch(`${BASE}/agents`);
    if (!res.ok) throw new Error("Failed to list agents");
    return res.json();
  },

  async chat(agentId: string, message: string, sessionId: string, browserTimezone?: string): Promise<ChatResponse> {
    const res = await fetch(`${BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agent_id: agentId, message, session_id: sessionId, browser_timezone: browserTimezone }),
    });
    if (!res.ok) {
      let detail = `Jarvis chat HTTP ${res.status}`;
      try {
        const data = await res.json();
        if (typeof data?.detail?.message === "string") {
          detail = data.detail.message;
          if (typeof data.detail.suggestion === "string") detail += `\n建议：${data.detail.suggestion}`;
          if (typeof data.detail.stage === "string") detail += `\n阶段：${data.detail.stage}`;
        } else if (typeof data?.detail === "string") detail = data.detail;
        else if (typeof data?.message === "string") detail = data.message;
        else if (typeof data?.error === "string") detail = data.error;
        if (typeof data?.data?.suggestion === "string") detail += `\n建议：${data.data.suggestion}`;
        if (typeof data?.data?.error === "string") detail += `\n原因：${data.data.error}`;
      } catch {
        const text = await res.text().catch(() => "");
        if (text) detail = text;
      }
      throw new Error(detail);
    }
    return res.json();
  },

  async chatStream(agentId: string, message: string, sessionId: string, browserTimezone?: string): Promise<ChatResponse> {
    const res = await fetch(`${BASE}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ agent_id: agentId, message, session_id: sessionId, browser_timezone: browserTimezone }),
    });
    if (!res.ok || !res.body) return this.chat(agentId, message, sessionId, browserTimezone);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let result: ChatResponse | null = null;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parsed = parseSSEFrames(buffer);
      buffer = parsed.remainder;
      for (const frame of parsed.frames) {
        if (frame.event === "chat_result") {
          result = JSON.parse(frame.data) as ChatResponse;
        }
        if (frame.event === "chat_error") {
          const payload = JSON.parse(frame.data) as { error?: string };
          throw new Error(payload.error || "Jarvis stream failed");
        }
      }
    }
    if (!result) return this.chat(agentId, message, sessionId, browserTimezone);
    return result;
  },

  async getChatHistory(agentId: string, limit = 50, sessionId?: string): Promise<ChatHistoryTurn[]> {
    const query = new URLSearchParams({ limit: String(limit) });
    if (sessionId) query.set("session_id", sessionId);
    const res = await fetch(`${BASE}/chat/${agentId}/history?${query.toString()}`);
    if (!res.ok) return [];
    return res.json();
  },

  async clearChatHistory(agentId: string, sessionId?: string): Promise<void> {
    const query = new URLSearchParams();
    if (sessionId) query.set("session_id", sessionId);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    await fetch(`${BASE}/chat/${agentId}/history${suffix}`, { method: "DELETE" });
  },

  async recordBehaviorEvent(payload: {
    agent_id: string;
    session_id?: string | null;
    observation_type: BehaviorEventType;
    duration_minutes?: number | null;
    occurred_at?: number | null;
    session_started_at?: number | null;
  }): Promise<{ observation: BehaviorObservation }> {
    const res = await fetch(`${BASE}/care/behavior-events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await errorFromResponse(res, `behavior event HTTP ${res.status}`);
    return res.json();
  },

  async listBehaviorObservations(params?: {
    date?: string;
    sessionId?: string;
    observationType?: string;
    limit?: number;
  }): Promise<BehaviorObservation[]> {
    const query = new URLSearchParams();
    if (params?.date) query.set("date", params.date);
    if (params?.sessionId) query.set("session_id", params.sessionId);
    if (params?.observationType) query.set("observation_type", params.observationType);
    if (params?.limit) query.set("limit", String(params.limit));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    const res = await fetch(`${BASE}/care/behavior-observations${suffix}`);
    if (!res.ok) return [];
    return res.json();
  },

  async getCareTrends(params?: { range?: "week" | "month" | "year"; end?: string }): Promise<CareTrendsResponse> {
    const query = new URLSearchParams();
    query.set("range", params?.range ?? "week");
    if (params?.end) query.set("end", params.end);
    const res = await fetch(`${BASE}/care/trends?${query.toString()}`);
    if (!res.ok) throw await errorFromResponse(res, `care trends HTTP ${res.status}`);
    return res.json();
  },

  recordBehaviorEventBeacon(payload: {
    agent_id: string;
    session_id?: string | null;
    observation_type: BehaviorEventType;
    duration_minutes?: number | null;
    occurred_at?: number | null;
    session_started_at?: number | null;
  }): boolean {
    const body = JSON.stringify(payload);
    if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
      return navigator.sendBeacon(`${BASE}/care/behavior-events`, new Blob([body], { type: "application/json" }));
    }
    void fetch(`${BASE}/care/behavior-events`, { method: "POST", headers: { "Content-Type": "application/json" }, body, keepalive: true }).catch(() => undefined);
    return true;
  },

  async getCareDayDetail(day: string): Promise<CareTrendDetail> {
    const res = await fetch(`${BASE}/care/days/${encodeURIComponent(day)}`);
    if (!res.ok) throw await errorFromResponse(res, `care day detail HTTP ${res.status}`);
    return res.json();
  },

  async getCareSettings(): Promise<{ psychological_tracking_enabled: boolean }> {
    const res = await fetch(`${BASE}/care/settings`);
    if (!res.ok) throw await errorFromResponse(res, `care settings HTTP ${res.status}`);
    return res.json();
  },

  async setPsychologicalTracking(enabled: boolean): Promise<{ psychological_tracking_enabled: boolean }> {
    const res = await fetch(`${BASE}/care/settings/tracking`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    if (!res.ok) throw await errorFromResponse(res, `care tracking HTTP ${res.status}`);
    return res.json();
  },

  async clearCareData(): Promise<{ deleted: Record<string, number> }> {
    const res = await fetch(`${BASE}/care/data`, { method: "DELETE" });
    if (!res.ok) throw await errorFromResponse(res, `clear care data HTTP ${res.status}`);
    return res.json();
  },

  async listMemories(params?: { memoryKind?: string; limit?: number }): Promise<JarvisMemory[]> {
    const query = new URLSearchParams();
    if (params?.memoryKind) query.set("memory_kind", params.memoryKind);
    if (params?.limit) query.set("limit", String(params.limit));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    const res = await fetch(`${BASE}/memories${suffix}`);
    if (!res.ok) throw await errorFromResponse(res, `list memories HTTP ${res.status}`);
    const data = await res.json();
    return Array.isArray(data?.memories) ? data.memories : [];
  },

  async deleteMemory(memoryId: number): Promise<void> {
    const res = await fetch(`${BASE}/memories/${memoryId}`, { method: "DELETE" });
    if (!res.ok) throw await errorFromResponse(res, `delete memory HTTP ${res.status}`);
  },

  async listConversationHistory(limit = 30): Promise<ConversationHistoryItem[]> {
    const res = await fetch(`${BASE}/conversation-history?limit=${limit}`);
    if (!res.ok) throw await errorFromResponse(res, `conversation history HTTP ${res.status}`);
    const data = await res.json();
    return Array.isArray(data?.conversations) ? data.conversations : [];
  },

  async saveConversationHistory(payload: {
    conversation_id: string;
    conversation_type: "private_chat" | "roundtable" | "brainstorm";
    title: string;
    agent_id?: string | null;
    scenario_id?: string | null;
    session_id: string;
    route_payload: Record<string, unknown>;
  }): Promise<ConversationHistoryItem> {
    const res = await fetch(`${BASE}/conversation-history`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await errorFromResponse(res, `save conversation HTTP ${res.status}`);
    const data = await res.json();
    return data.conversation;
  },

  async openConversationHistory(conversationId: string): Promise<ConversationHistoryItem> {
    const res = await fetch(`${BASE}/conversation-history/${encodeURIComponent(conversationId)}/open`, { method: "POST" });
    if (!res.ok) throw await errorFromResponse(res, `open conversation HTTP ${res.status}`);
    const data = await res.json();
    return data.conversation;
  },

  async deleteConversationHistory(conversationId: string): Promise<void> {
    const res = await fetch(`${BASE}/conversation-history/${encodeURIComponent(conversationId)}`, { method: "DELETE" });
    if (!res.ok) throw await errorFromResponse(res, `delete conversation HTTP ${res.status}`);
  },

  async getRoundtableTurns(sessionId: string): Promise<RoundtableTurn[]> {
    const res = await fetch(`${BASE}/sessions/${encodeURIComponent(sessionId)}/turns`);
    if (!res.ok) return [];
    return res.json();
  },

  async getRoundtableDecisionResult(sessionId: string): Promise<RoundtableDecisionResult> {
    const res = await fetch(`${BASE}/roundtable/${encodeURIComponent(sessionId)}/decision-result`);
    if (!res.ok) throw await errorFromResponse(res, `roundtable decision result HTTP ${res.status}`);
    return res.json();
  },

  async acceptRoundtableDecision(
    sessionId: string,
    resultId?: string,
  ): Promise<{ result: RoundtableDecisionResult; pending_action: PendingAction; direct_calendar_mutation: boolean }> {
    const res = await fetch(`${BASE}/roundtable/${encodeURIComponent(sessionId)}/accept`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ result_id: resultId }),
    });
    if (!res.ok) throw await errorFromResponse(res, `accept roundtable decision HTTP ${res.status}`);
    return res.json();
  },

  async getRoundtableBrainstormResult(sessionId: string): Promise<RoundtableBrainstormResult> {
    const res = await fetch(`${BASE}/roundtable/${encodeURIComponent(sessionId)}/brainstorm-result`);
    if (!res.ok) throw await errorFromResponse(res, `roundtable brainstorm result HTTP ${res.status}`);
    return res.json();
  },

  async saveRoundtableBrainstorm(
    sessionId: string,
    resultId?: string,
  ): Promise<{ result: RoundtableBrainstormResult; memory: JarvisMemory; direct_calendar_mutation: boolean; direct_plan_mutation: boolean }> {
    const res = await fetch(`${BASE}/roundtable/${encodeURIComponent(sessionId)}/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ result_id: resultId }),
    });
    if (!res.ok) throw await errorFromResponse(res, `save brainstorm HTTP ${res.status}`);
    return res.json();
  },

  async convertRoundtableBrainstormToPlan(
    sessionId: string,
    resultId?: string,
  ): Promise<{ result: RoundtableBrainstormResult; pending_action: PendingAction; direct_calendar_mutation: boolean; direct_plan_mutation: boolean }> {
    const res = await fetch(`${BASE}/roundtable/${encodeURIComponent(sessionId)}/plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ result_id: resultId }),
    });
    if (!res.ok) throw await errorFromResponse(res, `brainstorm to plan HTTP ${res.status}`);
    return res.json();
  },

  async returnRoundtableToPrivateChat(
    sessionId: string,
    payload: { result_id?: string; user_choice?: string; note?: string } = {},
  ): Promise<RoundtableReturnResponse> {
    const res = await fetch(`${BASE}/roundtable/${encodeURIComponent(sessionId)}/return`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await errorFromResponse(res, `return roundtable HTTP ${res.status}`);
    return res.json();
  },

  async getLocalLife(force = false): Promise<any> {
    const url = force ? `${BASE}/local-life?force=true` : `${BASE}/local-life`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`local-life HTTP ${res.status}`);
    return res.json();
  },

  async listCalendarEvents(
    hoursAhead = 24,
    range?: { start: string; end: string },
  ): Promise<CalendarEvent[]> {
    const params = new URLSearchParams();
    params.set("hours_ahead", String(hoursAhead));
    if (range) {
      params.set("start", range.start);
      params.set("end", range.end);
    }
    const res = await fetch(`${BASE}/calendar/events?${params.toString()}`);
    if (!res.ok) return [];
    return res.json();
  },

  async addCalendarEvent(payload: {
    title: string;
    start: string;
    end: string;
    stress_weight?: number;
    location?: string | null;
    notes?: string | null;
    source?: string;
    source_agent?: string | null;
    created_reason?: string | null;
    status?: string;
    route_required?: boolean;
  }): Promise<{ event_id: string; new_schedule_density: number; event: CalendarEvent }> {
    const res = await fetch(`${BASE}/calendar/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await errorFromResponse(res, `add event HTTP ${res.status}`);
    return res.json();
  },

  async deleteCalendarEvent(eventId: string): Promise<void> {
    const res = await fetch(`${BASE}/calendar/events/${eventId}`, { method: "DELETE" });
    if (!res.ok) throw await errorFromResponse(res, `delete event HTTP ${res.status}`);
  },

  async updateCalendarEvent(
    eventId: string,
    patch: Partial<{
      title: string;
      start: string;
      end: string;
      stress_weight: number;
      location: string | null;
      notes: string | null;
      source: string;
      source_agent: string | null;
      created_reason: string | null;
      status: string;
      route_required: boolean;
    }>
  ): Promise<{ event: CalendarEvent; new_schedule_density: number }> {
    const res = await fetch(`${BASE}/calendar/events/${eventId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (!res.ok) throw await errorFromResponse(res, `update event HTTP ${res.status}`);
    return res.json();
  },

  async listPendingActions(status = "pending"): Promise<PendingAction[]> {
    const res = await fetch(`${BASE}/pending-actions?status=${encodeURIComponent(status)}`);
    if (!res.ok) throw await errorFromResponse(res, `list pending actions HTTP ${res.status}`);
    return res.json();
  },

  async updatePendingAction(
    pendingId: string,
    payload: { title?: string; arguments?: Record<string, unknown> },
  ): Promise<PendingAction> {
    const res = await fetch(`${BASE}/pending-actions/${pendingId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await errorFromResponse(res, `update pending action HTTP ${res.status}`);
    return res.json();
  },

  async confirmPendingAction(
    pendingId: string,
    payload?: { title?: string; arguments?: Record<string, unknown> },
  ): Promise<{
    pending_action: PendingAction | null;
    result: { event?: CalendarEvent; task?: BackgroundTask } & Record<string, unknown>;
    fallback?: boolean;
  }> {
    const res = await fetch(`${BASE}/pending-actions/${pendingId}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? {}),
    });
    if (!res.ok) throw await errorFromResponse(res, `confirm pending action HTTP ${res.status}`);
    return res.json();
  },

  async cancelPendingAction(pendingId: string): Promise<PendingAction> {
    const res = await fetch(`${BASE}/pending-actions/${pendingId}/cancel`, { method: "POST" });
    if (!res.ok) throw await errorFromResponse(res, `cancel pending action HTTP ${res.status}`);
    return res.json();
  },

  async listBackgroundTasks(status?: string): Promise<BackgroundTask[]> {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    const res = await fetch(`${BASE}/background-tasks${suffix}`);
    if (!res.ok) throw await errorFromResponse(res, `list background tasks HTTP ${res.status}`);
    return res.json();
  },

  async updateBackgroundTask(taskId: string, payload: Partial<Pick<BackgroundTask, "status" | "notes">>): Promise<BackgroundTask> {
    const res = await fetch(`${BASE}/background-tasks/${taskId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await errorFromResponse(res, `update background task HTTP ${res.status}`);
    return res.json();
  },

  async listBackgroundTaskDays(params?: { taskId?: string; status?: string; planDate?: string; limit?: number }): Promise<BackgroundTaskDay[]> {
    const query = new URLSearchParams();
    if (params?.status) query.set("status", params.status);
    if (params?.planDate) query.set("plan_date", params.planDate);
    if (params?.limit) query.set("limit", String(params.limit));
    if (params?.taskId) {
      const suffix = query.toString() ? `?${query.toString()}` : "";
      const res = await fetch(`${BASE}/background-tasks/${params.taskId}/days${suffix}`);
      if (!res.ok) throw await errorFromResponse(res, `list background task days HTTP ${res.status}`);
      return res.json();
    }
    const suffix = query.toString() ? `?${query.toString()}` : "";
    const res = await fetch(`${BASE}/background-task-days${suffix}`);
    if (!res.ok) throw await errorFromResponse(res, `list background task days HTTP ${res.status}`);
    return res.json();
  },

  async completeBackgroundTaskDay(dayId: string): Promise<BackgroundTaskDay> {
    const res = await fetch(`${BASE}/background-task-days/${dayId}/complete`, { method: "POST" });
    if (!res.ok) throw await errorFromResponse(res, `complete background task day HTTP ${res.status}`);
    const data = await res.json();
    return data.task_day;
  },

  async deleteBackgroundTaskDay(dayId: string): Promise<BackgroundTaskDay> {
    const res = await fetch(`${BASE}/background-task-days/${dayId}`, { method: "DELETE" });
    if (!res.ok) throw await errorFromResponse(res, `delete background task day HTTP ${res.status}`);
    const data = await res.json();
    return data.task_day;
  },

  async listPlans(status?: string): Promise<JarvisPlan[]> {
    const query = new URLSearchParams();
    if (status) query.set("status", status);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    const res = await fetch(`${BASE}/plans${suffix}`);
    if (!res.ok) throw await errorFromResponse(res, `list plans HTTP ${res.status}`);
    return res.json();
  },

  async createPlan(payload: PlanWritePayload): Promise<JarvisPlan> {
    const res = await fetch(`${BASE}/plans`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await errorFromResponse(res, `create plan HTTP ${res.status}`);
    return res.json();
  },

  async updatePlan(planId: string, payload: Partial<PlanWritePayload>): Promise<JarvisPlan> {
    const res = await fetch(`${BASE}/plans/${planId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await errorFromResponse(res, `update plan HTTP ${res.status}`);
    return res.json();
  },

  async mergePlans(payload: { source_plan_id: string; target_plan_id: string; reason?: string | null }): Promise<PlanMergeResult> {
    const res = await fetch(`${BASE}/plans/merge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await errorFromResponse(res, `merge plans HTTP ${res.status}`);
    return res.json();
  },

  async splitPlan(planId: string, payload: { title: string; plan_day_ids: string[]; reason?: string | null }): Promise<PlanSplitResult> {
    const res = await fetch(`${BASE}/plans/${planId}/split`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await errorFromResponse(res, `split plan HTTP ${res.status}`);
    return res.json();
  },

  async listPlanDays(params?: { planId?: string; status?: string; start?: string; end?: string; limit?: number }): Promise<JarvisPlanDay[]> {
    const query = new URLSearchParams();
    if (params?.planId) query.set("plan_id", params.planId);
    if (params?.status) query.set("status", params.status);
    if (params?.start) query.set("start", params.start);
    if (params?.end) query.set("end", params.end);
    if (params?.limit) query.set("limit", String(params.limit));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    const res = await fetch(`${BASE}/plan-days${suffix}`);
    if (!res.ok) throw await errorFromResponse(res, `list plan days HTTP ${res.status}`);
    return res.json();
  },

  async listPlannerTasks(status?: string): Promise<PlannerTaskItem[]> {
    const query = new URLSearchParams();
    if (status) query.set("status", status);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    const res = await fetch(`${BASE}/planner/tasks${suffix}`);
    if (!res.ok) throw await errorFromResponse(res, `list planner tasks HTTP ${res.status}`);
    return res.json();
  },

  async cleanupDuplicatePlannerTasks(execute = false): Promise<PlannerTaskCleanupResult> {
    const query = new URLSearchParams({ execute: String(execute) });
    const res = await fetch(`${BASE}/planner/tasks/cleanup-duplicates?${query.toString()}`, { method: "POST" });
    if (!res.ok) throw await errorFromResponse(res, `cleanup duplicate planner tasks HTTP ${res.status}`);
    return res.json();
  },

  async projectPlanToCalendar(planId: string): Promise<ProjectPlanCalendarResult> {
    const res = await fetch(`${BASE}/plans/${planId}/project-calendar`, { method: "POST" });
    if (!res.ok) throw await errorFromResponse(res, `project plan to calendar HTTP ${res.status}`);
    return res.json();
  },

  async reschedulePlan(planId: string, payload: { reason?: string; days: Array<{ plan_date: string; start_time?: string | null; end_time?: string | null; reason?: string | null }> }): Promise<PlanRescheduleResult> {
    const res = await fetch(`${BASE}/plans/${planId}/reschedule`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await errorFromResponse(res, `reschedule plan HTTP ${res.status}`);
    return res.json();
  },

  async createSecretaryPlan(payload: SecretaryPlanRequest): Promise<SecretaryPlanResult> {
    const res = await fetch(`${BASE}/planner/secretary-plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await errorFromResponse(res, `create secretary plan HTTP ${res.status}`);
    return res.json();
  },

  async runPlannerDailyMaintenanceOnce(params?: { today?: string; auto_reschedule?: boolean; push_today?: boolean }): Promise<PlannerDailyMaintenanceResult> {
    const query = new URLSearchParams();
    if (params?.today) query.set("today", params.today);
    if (typeof params?.auto_reschedule === "boolean") query.set("auto_reschedule", String(params.auto_reschedule));
    if (typeof params?.push_today === "boolean") query.set("push_today", String(params.push_today));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    const res = await fetch(`${BASE}/planner/daily-maintenance/once${suffix}`, { method: "POST" });
    if (!res.ok) throw await errorFromResponse(res, `run planner daily maintenance once HTTP ${res.status}`);
    return res.json();
  },

  async getPlannerCalendar(range: { start: string; end: string }): Promise<PlannerCalendarResponse> {
    const query = new URLSearchParams({ start: range.start, end: range.end });
    const res = await fetch(`${BASE}/planner/calendar-items?${query.toString()}`);
    if (!res.ok) throw await errorFromResponse(res, `get planner calendar HTTP ${res.status}`);
    const data = await res.json();
    return {
      items: Array.isArray(data?.items) ? data.items : [],
      conflicts: Array.isArray(data?.conflicts) ? data.conflicts : [],
      free_windows: Array.isArray(data?.free_windows) ? data.free_windows : [],
    };
  },

  async listPlannerCalendarItems(range: { start: string; end: string }): Promise<PlannerCalendarItem[]> {
    return (await this.getPlannerCalendar(range)).items;
  },

  async completePlanDay(dayId: string): Promise<JarvisPlanDay> {
    const res = await fetch(`${BASE}/plan-days/${dayId}/complete`, { method: "POST" });
    if (!res.ok) throw await errorFromResponse(res, `complete plan day HTTP ${res.status}`);
    const data = await res.json();
    return data.plan_day;
  },

  async deletePlanDay(dayId: string): Promise<JarvisPlanDay> {
    const res = await fetch(`${BASE}/plan-days/${dayId}`, { method: "DELETE" });
    if (!res.ok) throw await errorFromResponse(res, `delete plan day HTTP ${res.status}`);
    const data = await res.json();
    return data.plan_day;
  },

  async updatePlanDay(dayId: string, payload: Partial<Pick<JarvisPlanDay, "plan_date" | "title" | "description" | "start_time" | "end_time" | "estimated_minutes" | "status" | "reschedule_reason">>): Promise<JarvisPlanDay> {
    const res = await fetch(`${BASE}/plan-days/${dayId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await errorFromResponse(res, `update plan day HTTP ${res.status}`);
    const data = await res.json();
    return data.plan_day;
  },

  async movePlanDay(dayId: string, payload: { plan_date: string; start_time?: string | null; end_time?: string | null; reason?: string | null }): Promise<JarvisPlanDay> {
    const res = await fetch(`${BASE}/plan-days/${dayId}/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await errorFromResponse(res, `move plan day HTTP ${res.status}`);
    const data = await res.json();
    return data.plan_day;
  },

  async bulkUpdatePlanDays(payload: { day_ids: string[]; status?: string | null; shift_days?: number | null; reason?: string | null }): Promise<PlanDayBulkUpdateResult> {
    const res = await fetch(`${BASE}/plan-days/bulk-update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await errorFromResponse(res, `bulk update plan days HTTP ${res.status}`);
    return res.json();
  },

  async cancelPlan(planId: string): Promise<JarvisPlan> {
    const res = await fetch(`${BASE}/plans/${planId}/cancel`, { method: "POST" });
    if (!res.ok) throw await errorFromResponse(res, `cancel plan HTTP ${res.status}`);
    const data = await res.json();
    return data.plan;
  },

  async deletePlan(planId: string): Promise<JarvisPlan> {
    const res = await fetch(`${BASE}/plans/${planId}`, { method: "DELETE" });
    if (!res.ok) throw await errorFromResponse(res, `delete plan HTTP ${res.status}`);
    const data = await res.json();
    return data.plan;
  },

  async listPlanEvents(planId: string): Promise<AgentEvent[]> {
    const res = await fetch(`${BASE}/plans/${planId}/events`);
    if (!res.ok) return [];
    return res.json();
  },

  async listMaxwellWorkbenchItems(params?: { status?: string; planDate?: string; limit?: number }): Promise<MaxwellWorkbenchItem[]> {
    const query = new URLSearchParams();
    if (params?.status) query.set("status", params.status);
    if (params?.planDate) query.set("plan_date", params.planDate);
    if (params?.limit) query.set("limit", String(params.limit));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    const res = await fetch(`${BASE}/maxwell/workbench-items${suffix}`);
    if (!res.ok) throw await errorFromResponse(res, `list maxwell workbench items HTTP ${res.status}`);
    return res.json();
  },

  async pushDailyTasksToMaxwellWorkbench(planDate?: string): Promise<{ plan_date: string; pushed_count: number; items: MaxwellWorkbenchItem[] }> {
    const query = new URLSearchParams();
    if (planDate) query.set("plan_date", planDate);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    const res = await fetch(`${BASE}/maxwell/workbench/push-daily-tasks${suffix}`, { method: "POST" });
    if (!res.ok) throw await errorFromResponse(res, `push daily tasks HTTP ${res.status}`);
    return res.json();
  },

  async markOverduePlannerDaysMissed(today?: string): Promise<PlannerOverdueMissedResult> {
    const query = new URLSearchParams();
    if (today) query.set("today", today);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    const res = await fetch(`${BASE}/planner/mark-overdue-missed${suffix}`, { method: "POST" });
    if (!res.ok) throw await errorFromResponse(res, `mark overdue planner days HTTP ${res.status}`);
    return res.json();
  },

  async markOverdueBackgroundTaskDaysMissed(today?: string): Promise<PlannerOverdueMissedResult> {
    return this.markOverduePlannerDaysMissed(today);
  },

  async startTeamCollaboration(payload: TeamCollaborationRequest): Promise<TeamCollaborationResponse> {
    const res = await fetch(`${BASE}/team/collaborate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await errorFromResponse(res, `team collaborate HTTP ${res.status}`);
    return res.json();
  },

  async getPendingMessages(includeRead = false): Promise<ProactiveMessage[]> {
    const params = new URLSearchParams();
    if (includeRead) params.set("include_read", "true");
    const qs = params.toString();
    const res = await fetch(`${BASE}/messages${qs ? `?${qs}` : ""}`);
    if (!res.ok) return [];
    return res.json();
  },

  async markProactiveMessageRead(id: string): Promise<ProactiveMessage> {
    const res = await fetch(`${BASE}/messages/${encodeURIComponent(id)}/read`, {
      method: "POST",
    });
    if (!res.ok) throw await errorFromResponse(res, `mark proactive read HTTP ${res.status}`);
    return res.json();
  },

  async dismissProactiveMessage(id: string): Promise<ProactiveMessage> {
    const res = await fetch(`${BASE}/messages/${encodeURIComponent(id)}/dismiss`, {
      method: "POST",
    });
    if (!res.ok) throw await errorFromResponse(res, `dismiss proactive HTTP ${res.status}`);
    return res.json();
  },

  async sendCareFeedback(id: string, payload: { feedback: "helpful" | "too_frequent" | "not_needed" | "snooze" | "handled"; snooze_minutes?: number }): Promise<{ message: ProactiveMessage | null; intervention: Record<string, unknown> | null }> {
    const res = await fetch(`${BASE}/messages/${encodeURIComponent(id)}/care-feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await errorFromResponse(res, `care feedback HTTP ${res.status}`);
    return res.json();
  },

  subscribeToMessages(onMessage: (msg: ProactiveMessage) => void): () => void {
    const sse = new EventSource(`${BASE}/messages/stream`);
    sse.onmessage = (e) => {
      try {
        const msg: ProactiveMessage = JSON.parse(e.data);
        if (msg.content) onMessage(msg);
      } catch {}
    };
    return () => sse.close();
  },
};
