"""
统一模型配置模板 — 复制为 model_config.py 并填入真实密钥
"""
GPT_IMAGE = {
    "base_url": "https://yunwu.ai",
    "default_api_key": "sk-your-key-here",
    "generate_endpoint": "/v1/images/generations",
    "edit_endpoint": "/v1/images/edits",
}

TISHICI_MODELS = {
    "main": {"name": "...", "api_key": "...", "base_url": "...", "model": "..."},
    "deepseek4": {"name": "DeepSeek V4-Pro", "api_key": "...", "base_url": "https://api.deepseek.com", "model": "deepseek-v4-pro"}
}

WENAN = {"api_key": "...", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"}

TUPIAN = {"api_key": "...", "base_url": "https://yunwu.ai/v1", "model": "gpt-4o", "app_api_key": "..."}

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_BATCH_SIZE = 20
MAX_CONCURRENCY = 5
