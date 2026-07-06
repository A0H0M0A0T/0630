import express from "express";
import path from "path";
import { createServer as createViteServer } from "vite";
import { GoogleGenAI, Type } from "@google/genai";
import dotenv from "dotenv";

dotenv.config();

const app = express();
const PORT = 3000;

// Body parser limits to support base64 image uploads
app.use(express.json({ limit: "20mb" }));
app.use(express.urlencoded({ limit: "20mb", extended: true }));

let aiClient: GoogleGenAI | null = null;

// Lazy initialization of GoogleGenAI to prevent crash if key is missing on startup
function getGeminiClient(): GoogleGenAI {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    throw new Error("GEMINI_API_KEY environment variable is missing. Please configure it in the Secrets panel.");
  }
  if (!aiClient) {
    aiClient = new GoogleGenAI({
      apiKey,
      httpOptions: {
        headers: {
          'User-Agent': 'aistudio-build',
        }
      }
    });
  }
  return aiClient;
}

// Fallback images matching preset themes and common search queries (Beer advertising focused)
const PRESET_FALLBACKS: Record<string, string[]> = {
  "精酿麦浪风": [
    "https://images.unsplash.com/photo-1567696911980-2eed69a46042?auto=format&fit=crop&w=1000&q=80", // Premium golden lager with white foam head
    "https://images.unsplash.com/photo-1571613316887-6f8d5cbf7ef7?auto=format&fit=crop&w=1000&q=80", // Beautiful amber beer poured into a glass
    "https://images.unsplash.com/photo-1608270586620-248524c67de9?auto=format&fit=crop&w=1000&q=80", // Assorted craft beers back-lit beautifully
    "https://images.unsplash.com/photo-1532635241-17e820aac095?auto=format&fit=crop&w=1000&q=80"  // Fresh beer taps at a brewery
  ],
  "冰爽夏日派对": [
    "https://images.unsplash.com/photo-1568648379691-30cc8127393e?auto=format&fit=crop&w=1000&q=80", // Beer bottles nestled in ice cubes
    "https://images.unsplash.com/photo-1436018626274-89acd67ae29e?auto=format&fit=crop&w=1000&q=80", // Friends toasting with beer mugs at summer BBQ
    "https://images.unsplash.com/photo-1532634922-8fe0b757fb13?auto=format&fit=crop&w=1000&q=80", // Cold glass of beer on beach at sunset
    "https://images.unsplash.com/photo-1551538597-88746b34cd4f?auto=format&fit=crop&w=1000&q=80"  // Chilled gold beer with fresh lemon slice
  ],
  "赛博蒸汽精酿": [
    "https://images.unsplash.com/photo-1584225065152-4a1454aa3d4e?auto=format&fit=crop&w=1000&q=80", // Modern dark beer bottles in dramatic lighting
    "https://images.unsplash.com/photo-1470337458703-46ad1756a187?auto=format&fit=crop&w=1000&q=80", // Cool glowing neon pub bar counter
    "https://images.unsplash.com/photo-1514933651103-005eec06c04b?auto=format&fit=crop&w=1000&q=80", // Trendy artisanal brewpub
    "https://images.unsplash.com/photo-1566633806327-68e152aaf26d?auto=format&fit=crop&w=1000&q=80"  // Dark stout cascading close-up
  ],
  "default": [
    "https://images.unsplash.com/photo-1567696911980-2eed69a46042?auto=format&fit=crop&w=1000&q=80", // Premium gold lager
    "https://images.unsplash.com/photo-1568648379691-30cc8127393e?auto=format&fit=crop&w=1000&q=80", // Beer in ice bucket
    "https://images.unsplash.com/photo-1584225065152-4a1454aa3d4e?auto=format&fit=crop&w=1000&q=80"  // Cool beer bottles
  ]
};

// Help helper to extract fallback based on keywords
function getFallbackImage(theme: string, promptText: string): string {
  let matchedList = PRESET_FALLBACKS.default;
  if (theme && PRESET_FALLBACKS[theme]) {
    matchedList = PRESET_FALLBACKS[theme];
  } else {
    const text = (promptText || "").toLowerCase();
    if (text.includes("精酿") || text.includes("麦浪") || text.includes("原浆") || text.includes("brew") || text.includes("craft")) {
      matchedList = PRESET_FALLBACKS["精酿麦浪风"];
    } else if (text.includes("冰") || text.includes("夏") || text.includes("派对") || text.includes("cheers") || text.includes("party")) {
      matchedList = PRESET_FALLBACKS["冰爽夏日派对"];
    } else if (text.includes("赛博") || text.includes("黑啤") || text.includes("neon") || text.includes("cyber") || text.includes("stout")) {
      matchedList = PRESET_FALLBACKS["赛博蒸汽精酿"];
    }
  }
  const randomIndex = Math.floor(Math.random() * matchedList.length);
  return matchedList[randomIndex];
}

// 1. POST /api/generate-prompt: Generate cohesive prompt from creative factors
app.post("/api/generate-prompt", async (req, res) => {
  try {
    const { subject, scene, lighting, style, posture, helper, aspectRatio, styleQuality } = req.body;
    const ai = getGeminiClient();

    let styleInstruction = "";
    if (styleQuality) {
      if (styleQuality === "写实") {
        styleInstruction = "The visual style MUST be extremely realistic, like a high-end food & beverage advertising photograph, with fine lens details, cinematic studio lighting, and high fidelity.";
      } else if (styleQuality === "二次元") {
        styleInstruction = "The visual style MUST be anime / 2D illustration style. Colorful, beautiful hand-drawn lines, and stylized anime aesthetics.";
      } else if (styleQuality === "赛博") {
        styleInstruction = "The visual style MUST be cyberpunk. Dark neon glowing ambient lighting, futuristic tech highlights, cool reflections, and synthwave vibe.";
      } else if (styleQuality === "水彩") {
        styleInstruction = "The visual style MUST be watercolor painting. Elegant fluid paint strokes, organic textures, soft and artistic flow, and beautiful wash effects.";
      }
    }

    const response = await ai.models.generateContent({
      model: "gemini-3.5-flash",
      contents: `You are an expert AI art director. Take the following creative factors and combine them into a highly descriptive, cinematic, and cohesive prompt for AI image generators (like Midjourney, Stable Diffusion, or Imagen).

Creative Factors:
- Target Subject/Character (目标主体/角色): ${subject || "未指定"}
- Background/Setting (背景场景/地理): ${scene || "未指定"}
- Lighting/Atmosphere (光影气候/天气): ${lighting || "未指定"}
- Visual Style/Art (视觉风格/艺术): ${style || "未指定"}
- Pose/Action (主体姿态/动作): ${posture || "未指定"}
- Additional Directives (辅助指令): ${helper || "无"}

${styleInstruction}
The aspect ratio for the target image is ${aspectRatio || "1:1"}.

Please formulate:
1. A refined, highly detailed English prompt suitable for AI image generators.
2. An elegant Chinese description that translates and summarizes the artistic concept.
3. A catchy, creative Chinese title (2-5 characters) for the artwork.

Your response must be a single JSON object.`,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            title: { type: Type.STRING, description: "A creative artwork title in Chinese, 2-5 characters." },
            englishPrompt: { type: Type.STRING, description: "Highly descriptive English image generation prompt." },
            chinesePrompt: { type: Type.STRING, description: "A beautiful, poetic description of the visual scene in Chinese." }
          },
          required: ["title", "englishPrompt", "chinesePrompt"]
        }
      }
    });

    const resultText = response.text;
    if (!resultText) {
      throw new Error("No text received from Gemini.");
    }

    res.json(JSON.parse(resultText.trim()));
  } catch (error: any) {
    console.error("Error generating prompt:", error);
    res.status(500).json({ error: error.message || "Failed to generate prompt" });
  }
});

// 2. POST /api/generate-image: Generate AI image or return a gorgeous fallback
app.post("/api/generate-image", async (req, res) => {
  try {
    const { prompt, theme, aspectRatio } = req.body;
    
    // Always check for Gemini key. If missing, throw error which will trigger fallback gracefully
    if (!process.env.GEMINI_API_KEY) {
      throw new Error("Missing GEMINI_API_KEY. Using beautiful visual fallback.");
    }

    const ai = getGeminiClient();
    console.log("Attempting image generation with prompt:", prompt, "aspectRatio:", aspectRatio);

    // Call gemini-3.1-flash-lite-image model
    const response = await ai.models.generateContent({
      model: "gemini-3.1-flash-lite-image",
      contents: {
        parts: [{ text: prompt || "A beautiful painting" }]
      },
      config: {
        imageConfig: {
          aspectRatio: aspectRatio || "1:1"
        }
      }
    });

    // Traverse candidates to locate the image part
    let base64Image = null;
    const candidates = response.candidates;
    if (candidates && candidates[0]?.content?.parts) {
      for (const part of candidates[0].content.parts) {
        if (part.inlineData && part.inlineData.data) {
          base64Image = `data:image/png;base64,${part.inlineData.data}`;
          break;
        }
      }
    }

    if (base64Image) {
      console.log("Gemini image generation succeeded!");
      res.json({ imageUrl: base64Image, isFallback: false });
    } else {
      console.warn("No inline image data found in Gemini response. Using high-quality curated fallback.");
      const fallbackUrl = getFallbackImage(theme, prompt);
      res.json({ imageUrl: fallbackUrl, isFallback: true });
    }
  } catch (error: any) {
    console.warn("Gemini image generation failed or key is standard/unpaid:", error.message);
    const fallbackUrl = getFallbackImage(req.body.theme, req.body.prompt);
    res.json({ imageUrl: fallbackUrl, isFallback: true, warning: error.message });
  }
});

// 3. POST /api/deconstruct-visual: Visual depth deconstruction
app.post("/api/deconstruct-visual", async (req, res) => {
  try {
    const { prompt, title, image } = req.body;
    const ai = getGeminiClient();

    let contents: any[] = [];

    if (image) {
      let mimeType = "image/png";
      let base64Data = "";

      if (image.startsWith("http")) {
        try {
          const imgRes = await fetch(image);
          if (imgRes.ok) {
            const arrayBuffer = await imgRes.arrayBuffer();
            const buffer = Buffer.from(arrayBuffer);
            mimeType = imgRes.headers.get("content-type") || "image/png";
            base64Data = buffer.toString("base64");
          }
        } catch (fetchErr) {
          console.warn("Failed to fetch image URL in deconstruct:", fetchErr);
        }
      } else {
        const matches = image.match(/^data:([a-zA-Z0-9]+\/[a-zA-Z0-9-.+]+);base64,(.*)$/);
        if (matches && matches.length >= 3) {
          mimeType = matches[1];
          base64Data = matches[2];
        }
      }

      if (base64Data) {
        contents.push({
          inlineData: {
            mimeType: mimeType,
            data: base64Data
          }
        });
      }
    }

    const textPrompt = `You are a world-class art director, design critic and professional food & beverage marketing expert.
Analyze the attached image (which was generated from the prompt: "${prompt}" and titled "${title || "精酿原浆"}"). If no image is provided, analyze the prompt itself.

Provide a detailed structural deconstruction and reverse-engineered visual analysis:
1. Color Palette: 5 precise hex color codes that perfectly match the actual colors, each with a poetic Chinese name and a brief description of its role (e.g., 主色, 辅色, 提亮色, 阴影).
2. Composition Strategy (构图手法): How elements are arranged in the actual composition.
3. Lighting/Atmosphere Analysis (光影氛围): Analysis of how light, contrast and atmosphere operate.
4. Depth/Layering Secrets (层次结构): Layering details for foreground, midground, and background.
5. Emotional Vibe/Tone (情绪基调): The emotional tone or mood of the design.
6. Recognized Factors (识别因子): Reverse-engineered creative factors from the image itself:
   - subject (目标主体): e.g., "晶莹剔透的德式小麦白啤，泡沫细腻，散发麦芽香气"
   - scene (背景场景): e.g., "落日余晖下的金黄大麦田，木质酒桶"
   - lighting (光影气候): e.g., "温暖治愈的逆光，夕阳穿透酒杯"
   - style (视觉风格): e.g., "高端微距静物，高饱和度，大片视感"
   - posture (主体姿态): e.g., "杯壁上凝结的水珠正缓缓滑落"
   - helper (辅助指令): e.g., "高光质感，温润饱满，清凉解暑"

Your response must be a single JSON object.`;

    contents.push({ text: textPrompt });

    const response = await ai.models.generateContent({
      model: "gemini-3.5-flash",
      contents: contents,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            colors: {
              type: Type.ARRAY,
              description: "5 matching colors with hex, name, and role description.",
              items: {
                type: Type.OBJECT,
                properties: {
                  hex: { type: Type.STRING, description: "The hex color code, e.g., #2E4057" },
                  name: { type: Type.STRING, description: "Beautiful Chinese color name" },
                  role: { type: Type.STRING, description: "Aesthetic role in the image" }
                },
                required: ["hex", "name", "role"]
              }
            },
            composition: { type: Type.STRING, description: "Detailed composition strategy analysis." },
            lighting: { type: Type.STRING, description: "Light and atmosphere detailed analysis." },
            depth: { type: Type.STRING, description: "Foreground, midground, and background layering tips." },
            vibe: { type: Type.STRING, description: "The core emotional vibe or tone." },
            recognizedFactors: {
              type: Type.OBJECT,
              description: "Reverse-engineered creative factors from the generated image.",
              properties: {
                subject: { type: Type.STRING, description: "Extract subject / character" },
                scene: { type: Type.STRING, description: "Extract background scene" },
                lighting: { type: Type.STRING, description: "Extract light and climate" },
                style: { type: Type.STRING, description: "Extract visual style / art direction" },
                posture: { type: Type.STRING, description: "Extract posture / pose / action" },
                helper: { type: Type.STRING, description: "Extract camera terms / auxiliary instructions" }
              },
              required: ["subject", "scene", "lighting", "style", "posture", "helper"]
            }
          },
          required: ["colors", "composition", "lighting", "depth", "vibe", "recognizedFactors"]
        }
      }
    });

    const resultText = response.text;
    if (!resultText) {
      throw new Error("No text received from Gemini.");
    }

    res.json(JSON.parse(resultText.trim()));
  } catch (error: any) {
    console.error("Error deconstructing visual:", error);
    res.status(500).json({ error: error.message || "Failed to deconstruct visual" });
  }
});

// 4. POST /api/recognize-image: Analyze uploaded image and extract creative factors
app.post("/api/recognize-image", async (req, res) => {
  try {
    const { image } = req.body; // base64 encoded image with MIME type prefix
    if (!image) {
      return res.status(400).json({ error: "No image provided" });
    }

    const ai = getGeminiClient();

    // Extract raw base64 data and mime type
    const matches = image.match(/^data:([a-zA-Z0-9]+\/[a-zA-Z0-9-.+]+);base64,(.*)$/);
    if (!matches || matches.length < 3) {
      return res.status(400).json({ error: "Invalid image format" });
    }

    const mimeType = matches[1];
    const base64Data = matches[2];

    const imagePart = {
      inlineData: {
        mimeType: mimeType,
        data: base64Data
      }
    };

    const textPart = {
      text: `Analyze this image as an expert art director specializing in beverage and beer marketing. Reverse engineer it and extract its creative design factors in Chinese.
Identify:
1. 目标主体 / 角色 (What/who is the main subject? E.g., glass of cold beer with foam, bottle of craft beer)
2. 背景场景 / 地理 (Where is it set? Describe the environment)
3. 光影气候 / 天气 (What is the lighting, time of day, weather?)
4. 视觉风格 / 艺术 (What is the artistic medium, style, camera settings?)
5. 主体姿态 / 动作 (What is the subject doing or what pose are they in?)
6. 辅助指令 (Any special camera angles, cinematic terms, rendering styles?)
7. Suggested preset category match (Is it closer to: '精酿麦浪风', '冰爽夏日派对', '赛博蒸汽精酿', or '其他'?)

Return your findings in a single JSON object.`
    };

    const response = await ai.models.generateContent({
      model: "gemini-3.5-flash",
      contents: [imagePart, textPart],
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            subject: { type: Type.STRING, description: "Extract subject / character" },
            scene: { type: Type.STRING, description: "Extract background scene" },
            lighting: { type: Type.STRING, description: "Extract light and climate" },
            style: { type: Type.STRING, description: "Extract visual style / art direction" },
            posture: { type: Type.STRING, description: "Extract posture / pose / action" },
            helper: { type: Type.STRING, description: "Extract camera terms / auxiliary instructions" },
            matchedPreset: { type: Type.STRING, description: "One of: 精酿麦浪风, 冰爽夏日派对, 赛博蒸汽精酿, 其他" }
          },
          required: ["subject", "scene", "lighting", "style", "posture", "helper", "matchedPreset"]
        }
      }
    });

    const textResult = response.text;
    if (!textResult) {
      throw new Error("No response from vision model.");
    }

    res.json(JSON.parse(textResult.trim()));
  } catch (error: any) {
    console.error("Error in image recognition:", error);
    res.status(500).json({ error: error.message || "Failed to analyze image" });
  }
});

// 5. POST /api/match-lyrics: Generate poetic prose/copy pairings for a scene
app.post("/api/match-lyrics", async (req, res) => {
  try {
    const { subject, scene, style, title } = req.body;
    const ai = getGeminiClient();

    const response = await ai.models.generateContent({
      model: "gemini-3.5-flash",
      contents: `You are an elegant Chinese literary scholar and high-end beverage brand creative director. Create a set of poetic pairings, brand slogans, and literary titles that perfectly match this artwork style and subject.
Since the user is focusing on premium beer promotion, elegantly integrate themes of brewing craftsmanship, refreshing ice-cold feelings, toasted grains, micro-brewed malt aroma, golden foam, friendship, toast, and deep relaxation.

Artwork Title: ${title || "精酿意境"}
Creative Factors:
- Subject: ${subject || "精酿啤酒"}
- Background: ${scene || "麦田或欢聚派对"}
- Style: ${style || "商业摄影风格"}

Generate:
1. 3 Poetic Title Options (文学感标题): 3 unique evocative literary titles (e.g., "麦浪浮光", "微醺夏夜", "琥珀余晖").
2. Core Verse (主配词/金句): A deeply poetic verse (1-2 lines) that captures the soul of this image, combining ancient elegance with modern beverage emotional resonance.
3. Expanded Verse (意境展开): A longer beautiful brand story prose (3-4 lines) suitable for a magazine cover or poster description.
4. Mood Tags (情感标签): 3 mood tags describing the literary feeling (e.g., 微醺, 欢聚, 匠心).

Return as a single JSON object.`,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            titles: {
              type: Type.ARRAY,
              items: { type: Type.STRING },
              description: "3 literary titles"
            },
            mainVerse: { type: Type.STRING, description: "Deep poetic verse (1-2 lines)" },
            prose: { type: Type.STRING, description: "Expanded aesthetic prose (3-4 lines)" },
            tags: {
              type: Type.ARRAY,
              items: { type: Type.STRING },
              description: "3 mood words"
            }
          },
          required: ["titles", "mainVerse", "prose", "tags"]
        }
      }
    });

    const textResult = response.text;
    if (!textResult) {
      throw new Error("No response from lyrics generator.");
    }

    res.json(JSON.parse(textResult.trim()));
  } catch (error: any) {
    console.error("Error matching lyrics:", error);
    res.status(500).json({ error: error.message || "Failed to generate poetic lyrics" });
  }
});

// 6. POST /api/explosive-copywriting: Ad-copy generation for social channels
app.post("/api/explosive-copywriting", async (req, res) => {
  try {
    const { title, factors, platform } = req.body;
    const ai = getGeminiClient();

    const response = await ai.models.generateContent({
      model: "gemini-3.5-flash",
      contents: `You are a legendary digital copywriter specializing in viral content for social platforms, and a master of food & beverage/beer marketing campaigns.
Create an explosive, highly engaging marketing post tailored for: **${platform || "小红书"}**

Since the product is beer, craft beer, or beer-related experiences, craft the copy to highlight aspects like: refreshing ice-cold throat feel, thick creamy foam, rich toasted malt flavor, floral hop aromas, after-work decompression, friend gatherings, premium lifestyle, or artisanal brewing craftsmanship.

Topic & Brand Concept:
- Product/Artwork Title: ${title || "精酿原浆"}
- Creative Factors summary: ${factors || "冰镇金黄精酿"}

Your ad copy must contain:
1. Eye-catching Title/Headline (爆款标题) with highly relevant beer and lifestyle emojis.
2. Emotional Hook (情绪共鸣开头) focusing on a moment when people crave a cold drink.
3. Beer Highlights (核心卖点/产品亮点) organized with structured bullet points and emojis.
4. An engaging Call to Action (互动引导/评论区钩子 like '你喝精酿最喜欢什么味道？' or '艾特你想一起喝酒的朋友').
5. Curated Hashtags (热门标签) including popular beer/lifestyle topics (e.g., #精酿啤酒, #今日微醺, #爆款文案).

Return as a single JSON object.`,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            headline: { type: Type.STRING, description: "Catchy viral headline with emojis" },
            body: { type: Type.STRING, description: "Full structured post copy, using emojis, bullet points, and high readability." },
            hashtags: {
              type: Type.ARRAY,
              items: { type: Type.STRING },
              description: "5 viral hashtags starting with #"
            }
          },
          required: ["headline", "body", "hashtags"]
        }
      }
    });

    const textResult = response.text;
    if (!textResult) {
      throw new Error("No response from copywriting generator.");
    }

    res.json(JSON.parse(textResult.trim()));
  } catch (error: any) {
    console.error("Error generating copywriting:", error);
    res.status(500).json({ error: error.message || "Failed to generate copy" });
  }
});

// Initialize dev server or serve production build
async function startServer() {
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
    console.log("Vite development middleware integrated.");
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
    console.log("Production static files server configured.");
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server is running at http://0.0.0.0:${PORT} in ${process.env.NODE_ENV || "development"} mode.`);
  });
}

startServer();
