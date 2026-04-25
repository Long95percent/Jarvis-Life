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
  created_at: string;
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

export interface ChatResponse {
  agent_id: string;
  agent_name: string;
  content: string;
  escalation?: EscalationHint | null;
  actions?: ActionResult[] | null;
}

export interface ChatHistoryTurn {
  role: "user" | "agent";
  content: string;
  timestamp: number;
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

  async getChatHistory(agentId: string, limit = 50): Promise<ChatHistoryTurn[]> {
    const res = await fetch(`${BASE}/chat/${agentId}/history?limit=${limit}`);
    if (!res.ok) return [];
    return res.json();
  },

  async clearChatHistory(agentId: string): Promise<void> {
    await fetch(`${BASE}/chat/${agentId}/history`, { method: "DELETE" });
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
  ): Promise<{ pending_action: PendingAction; result: { event: CalendarEvent } }> {
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

  async startTeamCollaboration(payload: TeamCollaborationRequest): Promise<TeamCollaborationResponse> {
    const res = await fetch(`${BASE}/team/collaborate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await errorFromResponse(res, `team collaborate HTTP ${res.status}`);
    return res.json();
  },

  async getPendingMessages(): Promise<ProactiveMessage[]> {
    const res = await fetch(`${BASE}/messages`);
    if (!res.ok) return [];
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

