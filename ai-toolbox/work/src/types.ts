/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export interface CreativeFactors {
  subject: string;
  scene: string;
  lighting: string;
  style: string;
  posture: string;
  helper: string;
}

export interface PairedPromptResult {
  title: string;
  englishPrompt: string;
  chinesePrompt: string;
}

export interface ColorSwatch {
  hex: string;
  name: string;
  role: string;
}

export interface DeconstructedVisual {
  colors: ColorSwatch[];
  composition: string;
  lighting: string;
  depth: string;
  vibe: string;
  recognizedFactors?: {
    subject: string;
    scene: string;
    lighting: string;
    style: string;
    posture: string;
    helper: string;
  };
}

export interface PipelineData {
  factors: CreativeFactors;
  promptResult: PairedPromptResult | null;
  imageUrl: string | null;
  deconstructed: DeconstructedVisual | null;
  isFallback: boolean;
}

export type PipelineStatus =
  | "idle"
  | "generating_prompt"
  | "generating_image"
  | "deconstructing_visual"
  | "completed"
  | "failed";

export interface RecognizedImageResult {
  subject: string;
  scene: string;
  lighting: string;
  style: string;
  posture: string;
  helper: string;
  matchedPreset: string;
}

export interface LyricsResult {
  titles: string[];
  mainVerse: string;
  prose: string;
  tags: string[];
}

export interface CopywritingResult {
  headline: string;
  body: string;
  hashtags: string[];
}

export type ActiveTab = "hand-drawn" | "recognition" | "copywriting" | "workflow";

// ── Workflow types ──

export interface WorkflowStartResponse {
  success: boolean;
  workflow_id: string;
}

export interface WorkflowStatus {
  id: string;
  status: string;
  current_step: string;
  step_index: number;
  total_steps: number;
  error_message: string;
}

export type WorkflowEventType = "started" | "succeeded" | "failed" | "warning" | "cancelled";

export interface WorkflowEvent {
  id: number;
  workflow_id: string;
  step_index: number;
  step_name: string;
  event_type: WorkflowEventType;
  message: string;
  duration_ms: number | null;
  error_type: string;
  error_traceback: string;
  input_summary: string;
  output_summary: string;
  created_at: string;
}

export interface WorkflowLogsResponse {
  workflow_id: string;
  items: WorkflowEvent[];
}

export interface KeyframeData {
  index: number;
  description: string;
  camera: string;
  composition: string;
}

export interface ScoreData {
  index: number;
  score: string;
  reason: string;
  dimensions: Record<string, number>;
}

export interface WorkflowResult {
  id: string;
  story_type: string;
  gender: string;
  scene: string;
  status: string;
  storyboard_text: string;
  keyframes: KeyframeData[];
  image_prompts: string[];
  image_urls: string[];
  scores: ScoreData[];
  copy_text: string;
  video_prompt: string;
  video_status: string;
  video_job_id: string;
  video_url: string;
  video_error: string;
  error_message: string;
  hashtags: {
    tags_list: string[];
    tags_string: string;
    tag_count: number;
    platform: string;
    generated_at: string;
    model: string;
    detected_language: string;
    source: string;
  } | null;
}

// Prompt generation config & status
export interface PromptConfig {
  current_model: string;
  current_model_name: string;
  available_models: Record<string, string>;
  scene_options: string[];
  weather_options: string[];
  style_options: string[];
  action_options: string[];
  audience_options: string[];
  generating: boolean;
}

export interface PromptStatus {
  running: boolean;
  progress: number;
  total: number;
  message: string;
  elapsed: number;
  success_count?: number;
  last_error?: string;
}

export interface PromptHistoryItem {
  id: number;
  prompt: string;
  created_at?: string;
  params?: string;
  copy_count?: number;
}

export interface PromptHistoryResponse {
  items: PromptHistoryItem[];
  total: number;
  total_copies: number;
  page: number;
}

export interface ImageGenResult {
  success: boolean;
  imageUrl: string;
  originalImageUrl: string;
  saved: boolean;
  localPath: string;
  metaUrl: string;
  saveError: string;
  raw?: unknown;
}

export interface WorkflowHistoryItem {
  id: string;
  story_type: string;
  scene: string;
  gender: string;
  status: string;
  image_urls: string[];
  image_prompt: string;
  copy_text: string;
  video_prompt: string;
  error_message: string;
  created_at: string;
}

export interface WorkflowHistoryResponse {
  items: WorkflowHistoryItem[];
}

export interface VideoStatusResult {
  workflow_id: string;
  video_status: string;
  video_job_id: string;
  video_url: string;
  video_error: string;
}

export interface ScenePoolResponse {
  scenes: string[];
}

export interface ReviewActionResponse {
  success: boolean;
  workflow_id: string;
  message: string;
}

export interface PromptGenParams {
  model: string;
  audience: string;
  scene: string;
  weather: string;
  style: string;
  action: string;
  min_product: number;
  max_product: number;
  batch: number;
  tolerance: number;
  extra: string;
}
