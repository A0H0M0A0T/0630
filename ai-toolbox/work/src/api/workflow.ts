import {
  WorkflowStartResponse,
  WorkflowStatus,
  WorkflowResult,
  WorkflowLogsResponse,
  WorkflowHistoryResponse,
  VideoStatusResult,
  ScenePoolResponse,
  ReviewActionResponse,
} from "../types";
import { requestJson } from "./client";

export interface WorkflowParams {
  story_type: string;
  gender: string;
  scene: string;
  product_image?: string;
  // 高级参数
  model?: string;
  audience?: string;
  weather?: string;
  style?: string;
  action?: string;
  extra?: string;
  aspect_ratio?: string;
}

export async function startWorkflow(params: WorkflowParams): Promise<WorkflowStartResponse> {
  return requestJson<WorkflowStartResponse>("/api/workflow/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}

export async function getWorkflowStatus(id: string): Promise<WorkflowStatus> {
  return requestJson<WorkflowStatus>(`/api/workflow/status/${id}`);
}

export async function getWorkflowLogs(id: string, limit = 200): Promise<WorkflowLogsResponse> {
  return requestJson<WorkflowLogsResponse>(`/api/workflow/logs/${id}?limit=${limit}`);
}

export async function getWorkflowHistory(limit = 20): Promise<WorkflowHistoryResponse> {
  return requestJson<WorkflowHistoryResponse>(`/api/workflow/history?limit=${limit}`);
}

export async function getWorkflowResult(id: string): Promise<WorkflowResult> {
  return requestJson<WorkflowResult>(`/api/workflow/result/${id}`);
}

export async function stopWorkflow(id: string): Promise<{ success: boolean }> {
  return requestJson<{ success: boolean }>(`/api/workflow/stop/${id}`, {
    method: "POST",
  });
}

export async function uploadProductImage(file: File): Promise<{ success: boolean; path: string; filename: string }> {
  const form = new FormData();
  form.append("file", file);
  return requestJson<{ success: boolean; path: string; filename: string }>("/api/workflow/upload-product", {
    method: "POST",
    body: form,
  });
}

export async function refreshWorkflowVideoStatus(workflowId: string): Promise<VideoStatusResult> {
  return requestJson<VideoStatusResult>(`/api/workflow/video-status/${workflowId}`, {
    method: "POST",
  });
}

export async function backfillWorkflowVideoUrl(workflowId: string, videoUrl: string): Promise<VideoStatusResult> {
  return requestJson<VideoStatusResult>(`/api/workflow/video-url/${workflowId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_url: videoUrl }),
  });
}

export async function getScenePool(): Promise<ScenePoolResponse> {
  return requestJson<ScenePoolResponse>("/api/scene-pool");
}

export async function continueWorkflow(id: string): Promise<ReviewActionResponse> {
  return requestJson<ReviewActionResponse>(`/api/workflow/continue/${id}`, {
    method: "POST",
  });
}

export async function regenerateWorkflowImage(id: string): Promise<ReviewActionResponse> {
  return requestJson<ReviewActionResponse>(`/api/workflow/regenerate/${id}`, {
    method: "POST",
  });
}

export function pollWorkflowUntilDone(
  workflowId: string,
  onStatus: (status: WorkflowStatus) => void,
  maxAttempts = 300,
  intervalMs = 1500
): Promise<WorkflowResult> {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    let resultRetries = 0;
    const poll = async () => {
      try {
        const status = await getWorkflowStatus(workflowId);
        onStatus(status);
        if (status.status === "completed") {
          // Retry result fetch up to 3 times (handles race conditions)
          const tryGetResult = async (): Promise<WorkflowResult> => {
            try {
              return await getWorkflowResult(workflowId);
            } catch (e: any) {
              if (resultRetries < 3 && e?.status === 409) {
                resultRetries++;
                await new Promise(r => setTimeout(r, 1000));
                return tryGetResult();
              }
              throw e;
            }
          };
          const result = await tryGetResult();
          resolve(result);
          return;
        }
        if (status.status === "needs_review") {
          const partial = await getWorkflowResult(workflowId);
          resolve(partial);
          return;
        }
        if (status.status === "failed" || status.status === "cancelled") {
          // Try to get partial result even on failure
          try {
            const partial = await getWorkflowResult(workflowId);
            resolve(partial);
          } catch {
            reject(new Error(status.error_message || `Workflow ${status.status}`));
          }
          return;
        }
        attempts++;
        if (attempts >= maxAttempts) {
          reject(new Error("工作流执行超时"));
          return;
        }
        setTimeout(poll, intervalMs);
      } catch (e) {
        reject(e);
      }
    };
    poll();
  });
}
