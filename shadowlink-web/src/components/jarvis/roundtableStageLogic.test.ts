import {
  initialRoundtableModeForScenario,
  pendingActionCount,
  routeButtonsFromScenarioState,
} from "./roundtableStageLogic";

function assert(condition: unknown, message: string): void {
  if (!condition) throw new Error(message);
}

function assertEqual<T>(actual: T, expected: T, message: string): void {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${String(expected)}, got ${String(actual)}`);
  }
}

assertEqual(initialRoundtableModeForScenario("local_lifestyle"), "brainstorm", "local lifestyle starts as brainstorm");
assertEqual(initialRoundtableModeForScenario("emotional_care"), "brainstorm", "emotional care starts as brainstorm");
assertEqual(initialRoundtableModeForScenario("schedule_coord"), "decision", "schedule coord starts as decision");

assertEqual(
  pendingActionCount([
    { pending_confirmation: true },
    { pending_confirmation: false },
    { ok: true },
    { pending_confirmation: true },
  ]),
  2,
  "only pending confirmations count as pending actions",
);

const buttons = routeButtonsFromScenarioState({
  next_routes: [
    { label: "压缩范围", target_stage: "critic_review", prompt: "这个太大了，帮我压缩范围。" },
    { label: "", prompt: "   " },
    { target_stage: "validation_plan", prompt: "选一个方向，给我最小验证步骤。" },
  ],
});

assertEqual(buttons.length, 2, "route buttons skip empty prompts");
assertEqual(buttons[0]?.label, "压缩范围", "route button prefers explicit label");
assertEqual(buttons[1]?.label, "validation_plan", "route button falls back to target stage");
assert(buttons[0]?.prompt.includes("压缩范围"), "route button keeps backend prompt");
