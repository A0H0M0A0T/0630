
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

export type ActiveTab = "hand-drawn" | "recognition" | "lyrics" | "copywriting";
