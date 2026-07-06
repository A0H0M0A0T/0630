import type { WorkflowEvent, WorkflowResult, WorkflowStatus } from "./types";

export type WorkflowStepState = "completed" | "running" | "failed" | "pending";

export interface WorkflowStepRow {
  step: number;
  label: string;
  state: WorkflowStepState;
  duration: string;
  message: string;
  event?: WorkflowEvent;
}

export interface WorkflowLogRow {
  id: number;
  time: string;
  text: string;
  meta: string;
  tone: "error" | "normal";
}

const STEP_LABELS: Record<number, string> = {
  1: "生成剧情分镜",
  2: "提取生图提示词",
  3: "gpt-image-2 生图",
  4: "AI 评分",
  5: "生成口播文案",
  6: "汇总视频提示词",
  7: "提交视频生成任务",
  8: "生成发布标签",
};

export function formatDuration(durationMs: number | null | undefined): string {
  if (durationMs == null) return "";
  if (durationMs < 1000) return `${durationMs}ms`;
  const seconds = durationMs / 1000;
  return `${seconds < 10 ? seconds.toFixed(1) : Math.round(seconds)}s`;
}

export function shouldRefreshWorkflowDiagnostics(isOpen: boolean, workflowId: string | null): boolean {
  return isOpen && Boolean(workflowId);
}

export function getDeveloperLogEntryLabel(isOpen: boolean): string {
  return isOpen ? "hide log" : "dev log";
}

export function getWorkflowLogRows(events: WorkflowEvent[]): WorkflowLogRow[] {
  return events.map((event) => ({
    id: event.id,
    time: event.created_at,
    text: event.message || event.output_summary || event.input_summary || "无日志内容",
    meta: `Step ${event.step_index} · ${event.step_name} · ${event.event_type}`,
    tone: event.event_type === "failed" ? "error" : "normal",
  }));
}

let _localErrorSeq = 0;

export function buildLocalErrorLogRows(message: string): WorkflowLogRow[] {
  if (!message) return [];
  const now = new Date();
  const time = [
    String(now.getHours()).padStart(2, "0"),
    String(now.getMinutes()).padStart(2, "0"),
    String(now.getSeconds()).padStart(2, "0"),
  ].join(":");
  _localErrorSeq += 1;
  return [
    {
      id: -_localErrorSeq, // negative ids never collide with real event ids
      time,
      text: message,
      meta: "UI 错误",
      tone: "error",
    },
  ];
}

export function getWorkflowStepRows({
  activeStep,
  events,
  failedEvent,
  isCompleted,
  running,
}: {
  activeStep: number;
  events: WorkflowEvent[];
  failedEvent?: WorkflowEvent;
  isCompleted: boolean;
  running: boolean;
}): WorkflowStepRow[] {
  return [1, 2, 3, 4, 5, 6, 7, 8].map((step) => {
    const stepEvents = events.filter((event) => event.step_index === step);
    const latestEvent = stepEvents.at(-1);
    const succeededEvent = [...stepEvents].reverse().find((event) => event.event_type === "succeeded");
    const isFailed = failedEvent?.step_index === step;
    const isRunning = running && activeStep === step && !isFailed;
    const isDone = isCompleted || Boolean(succeededEvent) || activeStep > step;

    let state: WorkflowStepState = "pending";
    if (isFailed) state = "failed";
    else if (isRunning) state = "running";
    else if (isDone) state = "completed";

    const sourceEvent = isFailed ? failedEvent : succeededEvent || latestEvent;
    const message =
      sourceEvent?.output_summary ||
      sourceEvent?.message ||
      (state === "running" ? "正在处理" : state === "pending" ? "等待执行" : "已完成");

    return {
      step,
      label: STEP_LABELS[step],
      state,
      duration: formatDuration(sourceEvent?.duration_ms),
      message,
      event: sourceEvent,
    };
  });
}

export function buildWorkflowDiagnosticText({
  events,
  failedEvent,
  result,
  status,
}: {
  events: WorkflowEvent[];
  failedEvent?: WorkflowEvent;
  result: WorkflowResult | null;
  status: WorkflowStatus | null;
}): string {
  // ── When a failed event exists, the status and current step MUST reflect
  //     the failure, even if the caller incorrectly passes status="completed". ──
  const effectiveStatus = failedEvent
    ? "failed"
    : (status?.status || result?.status || "idle");

  let stepLine: string;
  if (failedEvent) {
    stepLine = `当前步骤: ${failedEvent.step_index} / ${status?.total_steps ?? 8} ${failedEvent.step_name}`;
  } else {
    stepLine = `当前步骤: ${status?.step_index ?? 0} / ${status?.total_steps ?? 8} ${status?.current_step || ""}`;
  }

  const failedReason = failedEvent
    ? failedEvent.message
    : (status?.error_message || result?.error_message || "");

  return [
    `任务: ${status?.id || result?.id || "未开始"}`,
    `运行状态: ${effectiveStatus}`,
    stepLine,
    failedEvent ? `失败步骤: 第 ${failedEvent.step_index} 步 ${failedEvent.step_name}` : "",
    failedEvent && failedEvent.error_type ? `错误类型: ${failedEvent.error_type}` : "",
    failedReason ? `错误原因: ${failedReason}` : "",
    "",
    ...events.map((event) => {
      const duration = event.duration_ms == null ? "" : ` (${formatDuration(event.duration_ms)})`;
      return `[${event.created_at}] Step${event.step_index} ${event.step_name} ${event.event_type}${duration}: ${event.message}`;
    }),
  ].filter(Boolean).join("\n");
}
