# Agent Chat Mainline Decoupling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `AgentChatPanel.tsx` 从“同时处理私聊、日程确认、圆桌升级、关怀反馈、历史保存”的巨型面板，拆成更清晰的私聊主链路与可复用 service/hook 边界，同时不破坏现有功能。

**Architecture:** 先按业务职责把聊天相关能力分成几个薄层：私聊发送与 history、pending action 确认/取消、日程/关怀副作用、圆桌升级入口。UI 先保持不变，只把接口调用和副作用抽走，保证每一步都可单独回滚和验证。

**Tech Stack:** React, TypeScript, existing `jarvisApi.ts`, new focused service facades, existing Zustand store, Vite/tsc.

---

### Task 1: Map Chat Responsibilities

**Files:**
- Modify: `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`
- Modify: `shadowlink-web/src/stores/jarvisStore.ts`
- Modify: `shadowlink-web/src/services/jarvisApi.ts` only for reading signatures if needed

- [ ] **Step 1: Identify every chat-side effect**

List the current call sites that `AgentChatPanel.tsx` owns today:
- `sendMessage` / chat stream
- `saveConversationHistory`
- `recordBehaviorEvent` / beacon
- `confirmPendingAction` / `cancelPendingAction`
- `addCalendarEvent`
- `sendCareFeedback`
- history / open conversation related store calls

- [ ] **Step 2: Record the responsibility split**

Write a short note in the plan for which responsibilities stay in `AgentChatPanel.tsx` and which ones move to store/service helpers.

Expected split:
- UI state, input box, send button, streaming feedback stay in component
- reusable business actions move behind helpers/services

---

### Task 2: Extract Conversation History Service Boundary

**Files:**
- Create: `shadowlink-web/src/services/jarvisConversationApi.ts`
- Modify: `shadowlink-web/src/stores/jarvisStore.ts`
- Modify: `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`
- Modify: `shadowlink-web/src/services/index.ts`

- [ ] **Step 1: Add a focused conversation service**

Use this shape:

```ts
import { jarvisApi, type ConversationHistoryItem } from './jarvisApi'

export type { ConversationHistoryItem } from './jarvisApi'

export const jarvisConversationApi = {
  listConversationHistory(limit = 30): Promise<ConversationHistoryItem[]> {
    return jarvisApi.listConversationHistory(limit)
  },

  deleteConversationHistory(conversationId: string): Promise<void> {
    return jarvisApi.deleteConversationHistory(conversationId)
  },

  saveConversationHistory(payload: Parameters<typeof jarvisApi.saveConversationHistory>[0]) {
    return jarvisApi.saveConversationHistory(payload)
  },

  openConversationHistory(conversationId: string) {
    return jarvisApi.openConversationHistory(conversationId)
  },
}
```

- [ ] **Step 2: Replace store calls with the new service**

Update `jarvisStore.ts` so the conversation history methods use `jarvisConversationApi` instead of `jarvisApi` directly.

- [ ] **Step 3: Replace component imports**

Change `AgentChatPanel.tsx` to call the new conversation service only for history persistence/opening, not raw `jarvisApi`.

- [ ] **Step 4: Verify no behavior change**

Run:

```powershell
Push-Location shadowlink-web
npm.cmd run type-check
Pop-Location
```

Expected: pass.

---

### Task 3: Extract Pending Action Helper Boundary

**Files:**
- Create: `shadowlink-web/src/services/jarvisPendingActionApi.ts`
- Modify: `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`
- Modify: `shadowlink-web/src/services/index.ts`

- [ ] **Step 1: Create a thin pending action wrapper**

Expose only:

```ts
jarvisPendingActionApi.listPendingActions(status?: string)
jarvisPendingActionApi.confirmPendingAction(id: string, payload?: { title?: string; arguments?: Record<string, unknown> })
jarvisPendingActionApi.cancelPendingAction(id: string)
jarvisPendingActionApi.updatePendingAction(id: string, payload: { title?: string; arguments?: Record<string, unknown> })
```

- [ ] **Step 2: Replace direct pending action calls in chat panel**

Update the confirm/cancel paths in `AgentChatPanel.tsx` to use the new helper.

- [ ] **Step 3: Verify the pending action flow**

Run `npm.cmd run type-check` and make sure the panel still compiles.

---

### Task 4: Extract Calendar and Care Side-Effect Helpers

**Files:**
- Modify: `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`
- Optionally modify: `shadowlink-web/src/services/jarvisScheduleApi.ts`
- Optionally modify: `shadowlink-web/src/services/jarvisCareApi.ts`

- [ ] **Step 1: Move calendar side effects behind the schedule service**

`addCalendarEvent` should come from `jarvisScheduleApi` or a small chat helper that delegates to it.

- [ ] **Step 2: Move care side effects behind the care service**

`sendCareFeedback` should come from `jarvisCareApi` or a small chat helper that delegates to it.

- [ ] **Step 3: Keep UI behavior unchanged**

Do not change confirmation copy, toast copy, or visibility rules.

- [ ] **Step 4: Verify the send/confirm flows still pass type-check**

Run `npm.cmd run type-check`.

---

### Task 5: Isolate Chat Stream and History Save Flow

**Files:**
- Modify: `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`
- Modify: `shadowlink-web/src/stores/jarvisStore.ts`

- [ ] **Step 1: Keep only chat-stream orchestration in the component**

The component should retain input handling and display state, but the actual chat persistence and stream handling should be delegated to the store or a helper.

- [ ] **Step 2: Extract a small helper for stream result mapping**

Create a helper only if it simplifies the component without moving business logic back into the UI.

- [ ] **Step 3: Verify no regression in save/open history**

Run `npm.cmd run type-check`.

---

### Task 6: Final Validation and Documentation

**Files:**
- Modify: `docs/解耦接口说明/frontend-decoupling-developer-guide.md`
- Modify: any touched service files if needed for export cleanup

- [ ] **Step 1: Re-run type-check**

```powershell
Push-Location shadowlink-web
npm.cmd run type-check
Pop-Location
```

- [ ] **Step 2: Scan for leftover direct calls**

Check `AgentChatPanel.tsx` for direct `jarvisApi` calls that should have moved.

- [ ] **Step 3: Append completed steps to the living guide**

Record exactly which calls moved and what remains intentionally in the component.

---

## Self-Review Checklist

- Every task has exact file paths.
- Every code-changing task shows actual code shape or exact methods.
- The plan does not ask for broad UI refactors in the same step as service extraction.
- The plan keeps roundtable boundary decisions separate from chat mainline cleanup.
- The plan is small enough that each task can be verified by type-check.
