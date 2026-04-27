// shadowlink-web/src/services/jarvisApi.ts
const BASE = "/api/v1/jarvis";

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
  agent_id: string;
  title: string;
  description?: string | null;
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


async function errorFromResponse(res: Response, fallback: string): Promise<Error> {
  let detail = fallback;
  try {
    const data = await res.json();
    if (typeof data?.detail?.message === "string") {
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

export const jarvisApi = {
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

  async chat(agentId: string, message: string, sessionId: string): Promise<ChatResponse> {
    const res = await fetch(`${BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agent_id: agentId, message, session_id: sessionId }),
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
      } catch {
        const text = await res.text().catch(() => "");
        if (text) detail = text;
      }
      throw new Error(detail);
    }
    return res.json();
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
    if (!res.ok) throw new Error(`delete event HTTP ${res.status}`);
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
    if (!res.ok) throw new Error(`update event HTTP ${res.status}`);
    return res.json();
  },

  async listPendingActions(status = "pending"): Promise<PendingAction[]> {
    const res = await fetch(`${BASE}/pending-actions?status=${encodeURIComponent(status)}`);
    if (!res.ok) return [];
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
    if (!res.ok) return [];
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
      if (!res.ok) return [];
      return res.json();
    }
    const suffix = query.toString() ? `?${query.toString()}` : "";
    const res = await fetch(`${BASE}/background-task-days${suffix}`);
    if (!res.ok) return [];
    return res.json();
  },

  async completeBackgroundTaskDay(dayId: string): Promise<BackgroundTaskDay> {
    const res = await fetch(`${BASE}/background-task-days/${dayId}/complete`, { method: "POST" });
    if (!res.ok) throw await errorFromResponse(res, `complete background task day HTTP ${res.status}`);
    const data = await res.json();
    return data.task_day;
  },

  async listMaxwellWorkbenchItems(params?: { status?: string; planDate?: string; limit?: number }): Promise<MaxwellWorkbenchItem[]> {
    const query = new URLSearchParams();
    if (params?.status) query.set("status", params.status);
    if (params?.planDate) query.set("plan_date", params.planDate);
    if (params?.limit) query.set("limit", String(params.limit));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    const res = await fetch(`${BASE}/maxwell/workbench-items${suffix}`);
    if (!res.ok) return [];
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

  async markOverdueBackgroundTaskDaysMissed(today?: string): Promise<{ today: string; missed_count: number; task_days: BackgroundTaskDay[] }> {
    const query = new URLSearchParams();
    if (today) query.set("today", today);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    const res = await fetch(`${BASE}/background-task-days/mark-overdue-missed${suffix}`, { method: "POST" });
    if (!res.ok) throw await errorFromResponse(res, `mark overdue task days HTTP ${res.status}`);
    return res.json();
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
