import { buildLocalErrorLogRows, buildWorkflowDiagnosticText, getDeveloperLogEntryLabel, getWorkflowLogRows, getWorkflowStepRows, shouldRefreshWorkflowDiagnostics } from "./workflowDiagnostics";
import type { WorkflowEvent, WorkflowStatus } from "./types";

const failedEvents: WorkflowEvent[] = [
  {
    id: 1,
    workflow_id: "wf_test",
    step_index: 1,
    step_name: "生成剧情分镜",
    event_type: "succeeded",
    message: "Step1 succeeded",
    duration_ms: 2100,
    error_type: "",
    error_traceback: "",
    input_summary: "",
    output_summary: "",
    created_at: "2026-07-02 10:00:00",
  },
  {
    id: 2,
    workflow_id: "wf_test",
    step_index: 3,
    step_name: "gpt-image-2 生图",
    event_type: "failed",
    message: "Step3 四宫格图生成失败: Image API returned 401",
    duration_ms: 3800,
    error_type: "RuntimeError",
    error_traceback: "traceback",
    input_summary: "",
    output_summary: "",
    created_at: "2026-07-02 10:00:04",
  },
];

const failedStatus: WorkflowStatus = {
  id: "wf_test",
  status: "failed",
  current_step: "gpt-image-2 生成图片",
  step_index: 3,
  total_steps: 6,
  error_message: "Step3 四宫格图生成失败: Image API returned 401",
};

const rows = getWorkflowStepRows({
  activeStep: 3,
  events: failedEvents,
  failedEvent: failedEvents[1],
  isCompleted: false,
  running: false,
});

if (rows[2].state !== "failed") {
  throw new Error("Step 3 should be marked as failed");
}

const diagnosticText = buildWorkflowDiagnosticText({
  events: failedEvents,
  failedEvent: failedEvents[1],
  result: null,
  status: failedStatus,
});

if (!diagnosticText.includes("失败步骤: 第 3 步 gpt-image-2 生图")) {
  throw new Error("Diagnostic text should include the failed step");
}

if (shouldRefreshWorkflowDiagnostics(false, "wf_test")) {
  throw new Error("Diagnostics should not refresh while the panel is closed");
}

if (shouldRefreshWorkflowDiagnostics(true, null)) {
  throw new Error("Diagnostics should not refresh without a workflow id");
}

if (!shouldRefreshWorkflowDiagnostics(true, "wf_test")) {
  throw new Error("Diagnostics should refresh only when opened with a workflow id");
}

const logRows = getWorkflowLogRows(failedEvents);

if (logRows[1].tone !== "error") {
  throw new Error("Failed events should render as error log rows");
}

if (!logRows[1].text.includes("Image API returned 401")) {
  throw new Error("Log rows should preserve the original error message");
}

if (getDeveloperLogEntryLabel(false) !== "dev log") {
  throw new Error("Closed developer log entry should stay low-profile");
}

if (getDeveloperLogEntryLabel(true) !== "hide log") {
  throw new Error("Open developer log entry should expose a compact hide action");
}

const localErrorRows = buildLocalErrorLogRows("取物失败");

if (localErrorRows.length !== 1) {
  throw new Error("Local UI errors should be visible in the developer log even without a workflow id");
}

if (localErrorRows[0].tone !== "error" || !localErrorRows[0].text.includes("取物失败")) {
  throw new Error("Local UI errors should render as error log rows");
}

// ═══════════════════════════════════════════════════════════════════
//  Critical regression test: even when the caller (handleStart)
//  incorrectly passes status="completed", the diagnostic text MUST
//  show "failed" when a failedEvent exists.
// ═══════════════════════════════════════════════════════════════════
const wrongCallerStatus: WorkflowStatus = {
  id: "wf_test",
  status: "completed",        // <-- the bug: caller hardcoded "completed"
  current_step: "完成",
  step_index: 6,
  total_steps: 6,
  error_message: "",
};

const sslerrorEvent: WorkflowEvent = {
  id: 99,
  workflow_id: "wf_test",
  step_index: 3,
  step_name: "gpt-image-2 生成图片",
  event_type: "failed",
  message: "Step3 四宫格图生成失败: HTTPSConnectionPool(host='yunwu.ai', port=443): Max retries exceeded (Caused by SSLError)",
  duration_ms: 15000,
  error_type: "SSLError",
  error_traceback: "traceback...",
  input_summary: "",
  output_summary: "",
  created_at: "2026-07-02 12:00:00",
};

const diagnosticWithBuggyCaller = buildWorkflowDiagnosticText({
  events: [...failedEvents, sslerrorEvent],
  failedEvent: sslerrorEvent,
  result: null,
  status: wrongCallerStatus,  // caller says "completed"
});

if (!diagnosticWithBuggyCaller.includes("运行状态: failed")) {
  throw new Error(
    "REGRESSION: diagnostic must show 'failed' when a failedEvent exists, " +
    "even if the caller passes status='completed'. " +
    `Got: ${diagnosticWithBuggyCaller.substring(0, 200)}`
  );
}

if (!diagnosticWithBuggyCaller.includes("当前步骤: 3 / 6 gpt-image-2 生成图片")) {
  throw new Error(
    "REGRESSION: diagnostic must show the real failed step (step 3), " +
    "not the caller's step (step 6)."
  );
}

if (!diagnosticWithBuggyCaller.includes("yunwu.ai")) {
  throw new Error("REGRESSION: diagnostic must preserve the original SSLError host name.");
}
