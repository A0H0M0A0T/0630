"""
AI 工具箱 — 统一后端 (端口 8000)
整合：GPT Image + 提示词生成 + 文案生成 + 图像识别
启动: python server.py
"""
import sys, os, re, time, base64, json, glob, threading, asyncio, random, uuid, subprocess, hashlib, secrets, sqlite3
import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

# ═══ 统一模型配置 ═══
from model_config import (
    GPT_IMAGE, TISHICI_MODELS, WENAN, TUPIAN,
    MAX_FILE_SIZE, ALLOWED_EXTENSIONS, MAX_BATCH_SIZE, MAX_CONCURRENCY
)

# ═══ 导入 tishici 模块 (本地) — 必须先于 tupian，避免 database 模块冲突 ═══
sys.path.insert(0, os.path.join(_HERE, "modules", "tishici"))
from ai_client import (
    AIClient, MODELS, SCENE_OPTIONS, AUDIENCE_OPTIONS,
    WEATHER_OPTIONS, STYLE_OPTIONS, ACTION_OPTIONS, random_person
)
MODELS["deepseek4"]["api_key"] = WENAN["api_key"]
MODELS["deepseek4"]["base_url"] = WENAN["base_url"]
MODELS["deepseek4"]["model"] = WENAN["model"]
# tishici 的 database.py 注册为 'database'，用完后清除缓存
import database as _tishici_db
PromptDatabase = _tishici_db.PromptDatabase
SimilarityChecker = _tishici_db.SimilarityChecker
del _tishici_db
if 'database' in sys.modules: del sys.modules['database']

# ═══ 导入 tupian 模块 (本地) ═══
sys.path.insert(0, os.path.join(_HERE, "modules", "tupian"))
from database.db import init_db, save_record, get_all_records, get_record, delete_record
from services.recognize import recognize_by_url, recognize_by_upload_data, RecognizeError

# ═══ 导入 wenan 模块 (本地) ═══
sys.path.insert(0, os.path.join(_HERE, "modules", "wenan"))
from generator import generate_batch, COPY_TYPES

# ═══ 导入 hashtag-enricher 模块 (本地) ═══
sys.path.insert(0, os.path.join(_HERE, "modules", "hashtag_enricher"))
from enricher.llm import generate_hashtags, detect_and_generate
from enricher.config import settings as hashtag_settings

# ═══ 导入 orchestrator 引擎 (workflow) ═══
from modules.orchestrator.state import WorkflowState, init_workflow_db, list_workflow_events, list_workflow_history
from modules.orchestrator.engine import start_workflow, get_workflow_status, get_workflow_result, stop_workflow, continue_workflow_from_review, regenerate_workflow_image
from modules.video_generation.client import check_video_generation_status

# ═══ FastAPI App ═══
from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from typing import Optional, List
from contextlib import asynccontextmanager
from pathlib import Path

# ═══ Auth database ═══
AUTH_DB = os.path.join(_HERE, "auth.db")

def _init_auth_db():
    with sqlite3.connect(AUTH_DB) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL
        )""")
        conn.commit()

def _hash_password(password: str, salt: bytes = None) -> tuple[str, bytes]:
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return salt.hex() + ":" + dk.hex(), salt

def _verify_password(password: str, stored: str) -> bool:
    salt_hex, _ = stored.split(":", 1)
    dk, _ = _hash_password(password, bytes.fromhex(salt_hex))
    return dk == stored

def _create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() + 7 * 86400))
    with sqlite3.connect(AUTH_DB) as conn:
        conn.execute("INSERT INTO sessions(token, user_id, expires_at) VALUES(?,?,?)", (token, user_id, expires))
        conn.commit()
    return token

def _get_user_by_token(token: str) -> dict | None:
    with sqlite3.connect(AUTH_DB) as conn:
        row = conn.execute(
            "SELECT u.id, u.username, u.created_at FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token=? AND s.expires_at > datetime('now')",
            (token,)
        ).fetchone()
    if not row:
        return None
    return {"id": row[0], "username": row[1], "created_at": row[2]}

@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_auth_db()
    init_db()
    try: from openai import OpenAI; OpenAI(base_url=TUPIAN["base_url"], api_key=TUPIAN["api_key"])
    except: pass
    yield

app = FastAPI(title="AI工具箱", version="4.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ═══════════════════════════════════════════
# 本地认证 (/api/auth/*)
# ═══════════════════════════════════════════
class AuthRegisterReq(BaseModel):
    username: str
    password: str

class AuthLoginReq(BaseModel):
    username: str
    password: str

@app.post("/api/auth/register")
async def auth_register(req: AuthRegisterReq):
    username = req.username.strip()
    password = req.password
    if not username or len(username) < 2:
        raise HTTPException(400, "用户名至少 2 个字符")
    if not password or len(password) < 4:
        raise HTTPException(400, "密码至少 4 个字符")
    try:
        pw_hash, _ = _hash_password(password)
        with sqlite3.connect(AUTH_DB) as conn:
            conn.execute("INSERT INTO users(username, password_hash) VALUES(?,?)", (username, pw_hash))
            conn.commit()
        return {"success": True, "message": "注册成功"}
    except sqlite3.IntegrityError:
        raise HTTPException(409, "用户名已存在")

@app.post("/api/auth/login")
async def auth_login(req: AuthLoginReq):
    username = req.username.strip()
    password = req.password
    with sqlite3.connect(AUTH_DB) as conn:
        row = conn.execute("SELECT id, password_hash FROM users WHERE username=?", (username,)).fetchone()
    if not row or not _verify_password(password, row[1]):
        raise HTTPException(401, "用户名或密码错误")
    token = _create_session(row[0])
    return {"success": True, "token": token, "username": username}

@app.get("/api/auth/me")
async def auth_me(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "未登录")
    user = _get_user_by_token(auth[7:])
    if not user:
        raise HTTPException(401, "登录已过期，请重新登录")
    return {"success": True, "user": user}

@app.post("/api/auth/logout")
async def auth_logout(request: Request):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        with sqlite3.connect(AUTH_DB) as conn:
            conn.execute("DELETE FROM sessions WHERE token=?", (auth[7:],))
            conn.commit()
    return {"success": True}

# ═══ Static files ═══
STATIC_DIR = os.path.join(_HERE, "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

GENERATED_DIR = os.path.join(STATIC_DIR, "generated")
os.makedirs(GENERATED_DIR, exist_ok=True)
app.mount("/generated", StaticFiles(directory=GENERATED_DIR), name="generated")

DIST_DIR = os.path.join(_HERE, "dist")
if os.path.exists(os.path.join(DIST_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")

# ═══ Workflow API 路由 (/api/workflow/*) ═══
init_workflow_db()

class WorkflowStartReq(BaseModel):
    story_type: str = "正常性"
    gender: str = "随机"
    scene: str = "随机"
    product_image: str = ""
    # 高级参数
    model: str = "deepseek4"
    audience: str = "默认随机(按画像比例55/15/30)"
    weather: str = "随机"
    style: str = "随机"
    action: str = "随机"
    extra: str = ""
    aspect_ratio: str = "1:1"


class VideoUrlBackfillReq(BaseModel):
    video_url: str


@app.post("/api/workflow/start")
async def workflow_start(req: WorkflowStartReq):
    """启动 6 步短视频方案工作流。返回 workflow_id。"""
    if req.story_type not in ("趣味性", "休闲性", "正常性"):
        raise HTTPException(400, "story_type must be 趣味性/休闲性/正常性")
    if req.gender not in ("随机", "男", "女"):
        raise HTTPException(400, "gender must be 随机/男/女")
    init_workflow_db()
    state = WorkflowState()
    state.story_type = req.story_type
    state.gender = req.gender
    state.scene = req.scene
    state.product_image = req.product_image
    state.model = req.model
    state.audience = req.audience
    state.weather = req.weather
    state.style = req.style
    state.action = req.action
    state.extra = req.extra
    state.aspect_ratio = req.aspect_ratio
    try:
        wf_id = start_workflow(state)
        return {"success": True, "workflow_id": wf_id}
    except Exception as e:
        raise HTTPException(500, f"启动工作流失败: {e}")

@app.get("/api/workflow/status/{workflow_id}")
async def workflow_status_route(workflow_id: str):
    """查询工作流进度。"""
    s = get_workflow_status(workflow_id)
    if s is None:
        raise HTTPException(404, f"Workflow {workflow_id} not found")
    return s

@app.get("/api/workflow/history")
async def workflow_history_route(limit: int = Query(20, ge=1, le=100)):
    """列出有生成图片的历史工作流。"""
    return {"items": list_workflow_history(limit=limit)}


@app.get("/api/workflow/logs/{workflow_id}")
async def workflow_logs_route(workflow_id: str, limit: int = Query(200, ge=1, le=500)):
    """获取工作流诊断日志。"""
    s = get_workflow_status(workflow_id)
    if s is None:
        raise HTTPException(404, f"Workflow {workflow_id} not found")
    return {
        "workflow_id": workflow_id,
        "items": list_workflow_events(workflow_id, limit=limit),
    }

@app.get("/api/workflow/result/{workflow_id}")
async def workflow_result_route(workflow_id: str):
    """获取已完成工作流的完整结果。"""
    r = get_workflow_result(workflow_id)
    if r is None:
        s = get_workflow_status(workflow_id)
        if s:
            raise HTTPException(409, f"Workflow still running. Current step: {s.get('current_step', '')}")
        raise HTTPException(404, f"Workflow {workflow_id} not found")
    return r

@app.post("/api/workflow/stop/{workflow_id}")
async def workflow_stop_route(workflow_id: str):
    """中止运行中的工作流。"""
    ok = stop_workflow(workflow_id)
    if not ok:
        raise HTTPException(404, f"Workflow {workflow_id} not found or already finished")
    return {"success": True}

@app.get("/api/product-images")
async def list_product_images():
    """列出 static/product/ 中的所有产品图（默认素材 + 用户上传的）。"""
    product_dir = os.path.join(STATIC_DIR, "product")
    items = []
    if os.path.isdir(product_dir):
        for name in sorted(os.listdir(product_dir)):
            if name.lower().endswith((".png", ".jpg", ".jpeg")):
                abs_path = os.path.join(product_dir, name)
                items.append({
                    "filename": name,
                    "url": f"/static/product/{name}",
                    "size": os.path.getsize(abs_path),
                })
    return {"images": items, "count": len(items)}


@app.post("/api/workflow/upload-product")
async def workflow_upload_product(file: UploadFile = File(...)):
    """上传产品参考图。"""
    if not file.filename:
        raise HTTPException(400, "No file provided")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        raise HTTPException(400, "Only .png/.jpg/.jpeg allowed")
    product_dir = os.path.join(STATIC_DIR, "product")
    os.makedirs(product_dir, exist_ok=True)
    filename = f"product_{int(time.time())}{ext}"
    filepath = os.path.join(product_dir, filename)
    with open(filepath, "wb") as f:
        import shutil
        shutil.copyfileobj(file.file, f)
    return {"success": True, "path": f"/static/product/{filename}", "filename": filename}


@app.post("/api/workflow/video-status/{workflow_id}")
async def workflow_video_status_refresh(workflow_id: str):
    """刷新视频生成任务状态。有 video_job_id 则查 provider，否则返回当前状态。"""
    try:
        st = WorkflowState(workflow_id)
    except ValueError:
        raise HTTPException(404, f"Workflow {workflow_id} not found")

    if st.video_job_id:
        result = check_video_generation_status(st.video_job_id)
        st.video_status = result.get("video_status", st.video_status)
        st.video_job_id = result.get("video_job_id", st.video_job_id)
        st.video_url = result.get("video_url", st.video_url)
        st.video_error = result.get("video_error", st.video_error)
        st.save()

    return {
        "workflow_id": st.id,
        "video_status": st.video_status,
        "video_job_id": st.video_job_id,
        "video_url": st.video_url,
        "video_error": st.video_error,
    }


@app.post("/api/workflow/video-url/{workflow_id}")
async def workflow_video_url_backfill(workflow_id: str, body: VideoUrlBackfillReq):
    """手动回填视频地址。写入 video_url 并将状态置为 completed。"""
    try:
        st = WorkflowState(workflow_id)
    except ValueError:
        raise HTTPException(404, f"Workflow {workflow_id} not found")

    st.video_url = body.video_url
    st.video_status = "completed"
    st.video_error = ""
    st.save()

    return {
        "workflow_id": st.id,
        "video_status": st.video_status,
        "video_job_id": st.video_job_id,
        "video_url": st.video_url,
        "video_error": st.video_error,
    }


@app.post("/api/workflow/continue/{workflow_id}")
async def workflow_continue_route(workflow_id: str):
    """评分闸门：继续使用当前图片，从 Step 5 继续执行。"""
    try:
        wf_id = continue_workflow_from_review(workflow_id)
        return {"success": True, "workflow_id": wf_id, "message": "从 Step 5 继续执行"}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/workflow/regenerate/{workflow_id}")
async def workflow_regenerate_route(workflow_id: str):
    """评分闸门：重新生成图片，从 Step 3 重新执行。"""
    try:
        wf_id = regenerate_workflow_image(workflow_id)
        return {"success": True, "workflow_id": wf_id, "message": "从 Step 3 重新生成图片"}
    except ValueError as e:
        raise HTTPException(400, str(e))


# ═══ GPT Image config ═══
@app.get("/api/gpt-image/config")
async def gpt_image_config():
    return {
        "default_api_key": GPT_IMAGE["default_api_key"],
        "base_url": GPT_IMAGE["base_url"],
        "generate_endpoint": GPT_IMAGE["generate_endpoint"],
        "edit_endpoint": GPT_IMAGE["edit_endpoint"],
    }

class GptImageGenerateReq(BaseModel):
    prompt: str
    aspectRatio: str = "1:1"
    n: int = 1
    quality: str = "high"

def _aspect_to_size(aspect_ratio: str) -> str:
    return {
        "1:1": "1024x1024",
        "16:9": "1536x1024",
        "9:16": "1024x1536",
        "4:3": "1536x1024",
        "3:4": "1024x1536",
    }.get(aspect_ratio, "1024x1024")

def _extract_image_url(data: dict) -> Optional[str]:
    items = data.get("data") or data.get("images") or []
    if isinstance(items, dict):
        items = [items]
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("url"):
            return item["url"]
        if item.get("b64_json"):
            return "data:image/png;base64," + item["b64_json"]
    for key in ("image", "url"):
        if data.get(key):
            return data[key]
    return None

async def _save_generated_image(image_url: str, prompt: str, raw: dict) -> dict:
    file_id = time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    meta = {
        "prompt": prompt,
        "original_url": image_url,
        "saved": False,
        "local_url": "",
        "local_path": "",
        "error": "",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        if image_url.startswith("data:image/"):
            match = re.match(r"^data:(image/[\w.+-]+);base64,(.+)$", image_url, re.S)
            if not match:
                raise ValueError("无法解析 base64 图片")
            mime, encoded = match.groups()
            ext = ".jpg" if mime in ("image/jpeg", "image/jpg") else ".webp" if mime == "image/webp" else ".png"
            image_bytes = base64.b64decode(encoded)
        elif image_url.startswith("http://") or image_url.startswith("https://"):
            response = requests.get(image_url, headers={"User-Agent": "Mozilla/5.0"}, verify=False, timeout=60)
            response.raise_for_status()
            image_bytes = response.content
            content_type = response.headers.get("content-type", "")
            ext = ".jpg" if "jpeg" in content_type or "jpg" in content_type else ".webp" if "webp" in content_type else ".png"
        else:
            raise ValueError("未知图片地址格式")

        filename = file_id + ext
        image_path = os.path.join(GENERATED_DIR, filename)
        with open(image_path, "wb") as f:
            f.write(image_bytes)
        meta["saved"] = True
        meta["local_url"] = "/generated/" + filename
        meta["local_path"] = image_path
    except Exception as e:
        meta["error"] = str(e)

    safe_raw = raw.copy() if isinstance(raw, dict) else {"raw": raw}
    if "data" in safe_raw:
        safe_raw["data"] = "[omitted]"
    meta_path = os.path.join(GENERATED_DIR, file_id + ".json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({**meta, "raw": safe_raw}, f, ensure_ascii=False, indent=2)
    meta["meta_url"] = "/generated/" + file_id + ".json"
    meta["meta_path"] = meta_path
    return meta

@app.post("/api/gpt-image/generate")
async def gpt_image_generate(req: GptImageGenerateReq):
    if not req.prompt.strip():
        raise HTTPException(400, "提示词不能为空")
    payload = {
        "model": "gpt-image-2",
        "prompt": req.prompt,
        "n": max(1, min(req.n, 4)),
        "size": _aspect_to_size(req.aspectRatio),
        "quality": req.quality,
    }
    url = GPT_IMAGE["base_url"].rstrip("/") + GPT_IMAGE["generate_endpoint"]
    print(f"[GPT-IMAGE] POST {url} model={payload['model']} size={payload['size']} quality={payload['quality']}")
    try:
        response = requests.post(
            url,
            json=payload,
            timeout=120,
            verify=False,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": "Bearer " + GPT_IMAGE["default_api_key"],
            },
        )
        print(f"[GPT-IMAGE] response status={response.status_code}")
        if response.status_code >= 400:
            raise HTTPException(response.status_code, response.text or "图片生成接口请求失败")
        data = response.json()
    except requests.RequestException as e:
        print(f"[GPT-IMAGE] RequestException: {type(e).__name__}: {e}")
        raise HTTPException(502, f"图片生成服务连接失败: {e}")
    except Exception as e:
        raise HTTPException(500, f"图片生成失败: {e}")

    image_url = _extract_image_url(data)
    if not image_url:
        raise HTTPException(502, "图片生成接口未返回图片")
    saved = await _save_generated_image(image_url, req.prompt, data)
    return {
        "success": True,
        "imageUrl": saved["local_url"] or image_url,
        "originalImageUrl": image_url,
        "saved": saved["saved"],
        "localPath": saved["local_path"],
        "metaUrl": saved["meta_url"],
        "saveError": saved["error"],
        "raw": data,
    }

# ═══ API Key verification ═══
APP_API_KEY = TUPIAN["app_api_key"]
_api_key_header = APIKeyHeader(name="X-App-Key", auto_error=False)

async def verify_key(x_app_key: str = Depends(_api_key_header)):
    if APP_API_KEY and (not x_app_key or x_app_key != APP_API_KEY):
        raise HTTPException(401, "Invalid X-App-Key")

# ═══════════════════════════════════════════
# 图像识别 API (/api/image/*)
# ═══════════════════════════════════════════
_batch_semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

def _sanitize_url(url):
    from urllib.parse import urlparse, urlunparse
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))

def _validate_upload(filename, size):
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持格式: {Path(filename).suffix}")
    if size and size > MAX_FILE_SIZE:
        raise HTTPException(413, "文件超过10MB限制")

async def _read_upload(file):
    chunks, total = [], 0
    while True:
        chunk = await file.read(1024*1024)
        if not chunk: break
        total += len(chunk)
        if total > MAX_FILE_SIZE: raise HTTPException(413, "文件超过10MB限制")
        chunks.append(chunk)
    return b"".join(chunks)

class RecognizeUrlReq(BaseModel): url: str
class BatchRecognizeReq(BaseModel): images: List[str]

@app.get("/api/image/config")
async def img_config(): return {"app_api_key": APP_API_KEY, "version": "1.0"}

@app.get("/api/image/health")
async def img_health():
    try:
        from openai import OpenAI
        c = OpenAI(base_url=TUPIAN["base_url"], api_key=TUPIAN["api_key"])
        c.chat.completions.create(model=TUPIAN["model"], messages=[{"role":"user","content":"hi"}], max_tokens=5)
        return {"status":"ok","model":TUPIAN["model"]}
    except Exception as e:
        return JSONResponse({"status":"error","detail":str(e)}, 502)

@app.post("/api/image/recognize/url")
async def img_url(req: RecognizeUrlReq):
    try:
        result = await recognize_by_url(str(req.url))
        rid = save_record(image_source=str(req.url), result=result, image_thumb=str(req.url))
        return {"success":True,"id":rid,"result":result}
    except RecognizeError as e:
        raise HTTPException(e.status_code or 400, e.message)

@app.post("/api/image/recognize/upload")
async def img_upload(file: UploadFile = File(...)):
    fn = file.filename or "unknown"
    _validate_upload(fn, None)
    contents = await _read_upload(file)
    _validate_upload(fn, len(contents))
    try:
        result = await recognize_by_upload_data(contents, fn)
        suffix = Path(fn).suffix.lower()
        mime = "image/jpeg" if suffix in (".jpg",".jpeg") else "image/png"
        thumb = f"data:{mime};base64,{base64.b64encode(contents).decode()}"
        rid = save_record(image_source=fn, result=result, image_thumb=thumb)
        return {"success":True,"id":rid,"result":result,"thumb":thumb}
    except RecognizeError as e:
        raise HTTPException(e.status_code or 400, e.message)

@app.post("/api/image/recognize/batch")
async def img_batch(req: BatchRecognizeReq):
    async def one(url, i):
        async with _batch_semaphore:
            try:
                r = await recognize_by_url(url)
                save_record(image_source=url, result=r, image_thumb=url)
                return {"url":url,"success":True,"result":r}
            except RecognizeError as e:
                return {"url":url,"success":False,"error":e.message}
    results = await asyncio.gather(*[one(u, i) for i, u in enumerate(req.images)])
    sc = sum(1 for r in results if r["success"])
    return {"total":len(req.images),"success":sc,"failed":len(req.images)-sc,"results":results}

@app.post("/api/image/recognize/batch/upload")
async def img_batch_upload(files: list[UploadFile] = File(...)):
    if len(files) > MAX_BATCH_SIZE: raise HTTPException(400, f"最多{MAX_BATCH_SIZE}张")
    async def one(file, i):
        fn = file.filename or "unknown"
        async with _batch_semaphore:
            try:
                c = await _read_upload(file)
                _validate_upload(fn, len(c))
                r = await recognize_by_upload_data(c, fn)
                save_record(image_source=fn, result=r)
                return {"filename":fn,"success":True,"result":r}
            except Exception as e:
                return {"filename":fn,"success":False,"error":str(e)}
    results = await asyncio.gather(*[one(f, i) for i, f in enumerate(files)])
    sc = sum(1 for r in results if r["success"])
    return {"total":len(files),"success":sc,"failed":len(files)-sc,"results":results}

@app.get("/api/image/history", dependencies=[Depends(verify_key)])
async def img_history(page:int=Query(1,ge=1), page_size:int=Query(20,ge=1,le=100)):
    items, total = get_all_records(page=page, page_size=page_size)
    return {"items":items,"total":total,"page":page,"page_size":page_size}

@app.get("/api/image/history/{rid}", dependencies=[Depends(verify_key)])
async def img_history_item(rid:int):
    r = get_record(rid)
    if not r: raise HTTPException(404)
    return r

@app.delete("/api/image/history/{rid}", dependencies=[Depends(verify_key)])
async def img_delete(rid:int):
    if not delete_record(rid): raise HTTPException(404)
    return {"success":True}

# ═══════════════════════════════════════════
# 提示词生成 API (/api/prompt/*)
# ═══════════════════════════════════════════
prompt_db = PromptDatabase()
checker = SimilarityChecker()
_pgen_state = {"running":False,"progress":0,"total":0,"message":"","start_time":0,"success_count":0,"last_error":""}

class PromptGenReq(BaseModel):
    model:str="deepseek4"; audience:str="默认随机(按画像比例55/15/30)"; scene:str="随机"
    weather:str="随机"; style:str="随机"; action:str="随机"
    min_product:int=1; max_product:int=3; batch:int=1; tolerance:float=65.0; extra:str=""

@app.get("/api/prompt/config")
async def prompt_config():
    default_client = AIClient("deepseek4")
    return {
        "current_model":default_client.model_key,"current_model_name":default_client.get_model_name(),
        "available_models":{k:v["name"] for k,v in MODELS.items()},
        "scene_options":SCENE_OPTIONS,"weather_options":WEATHER_OPTIONS,
        "style_options":STYLE_OPTIONS,"action_options":ACTION_OPTIONS,
        "audience_options":AUDIENCE_OPTIONS,"generating":_pgen_state["running"],
    }

@app.post("/api/prompt/generate")
async def prompt_start(req:PromptGenReq):
    global _pgen_state
    if _pgen_state["running"]: raise HTTPException(400,"已有任务在运行")
    if req.model not in MODELS: raise HTTPException(400,f"未知模型:{req.model}")
    _pgen_state={"running":True,"progress":0,"total":req.batch,"message":"准备中...","start_time":time.time(),"success_count":0,"last_error":""}
    threading.Thread(target=_run_prompt_gen,args=(req,),daemon=True).start()
    return {"success":True}

@app.post("/api/prompt/stop")
async def prompt_stop():
    global _pgen_state; _pgen_state["running"]=False; return {"success":True}

@app.get("/api/prompt/status")
async def prompt_status():
    e=time.time()-_pgen_state["start_time"] if _pgen_state["start_time"] else 0
    return {"running":_pgen_state["running"],"progress":_pgen_state["progress"],
            "total":_pgen_state["total"],"message":_pgen_state["message"],"elapsed":round(e),
            "success_count":_pgen_state.get("success_count",0),"last_error":_pgen_state.get("last_error","")}

@app.get("/api/prompt/history")
async def prompt_history(page:int=Query(1),page_size:int=Query(50),sort:str=Query("latest"),search:str=Query("")):
    order="copy_count DESC" if sort=="most_copied" else "id DESC"
    rows=prompt_db.search_prompts(search) if search else prompt_db.get_all_prompts(order_by=order)
    total=len(rows); start=(page-1)*page_size; page_rows=rows[start:start+page_size]
    items=[{"id":pid,"prompt":t,"created_at":str(ca),"params":ps,"copy_count":cc or 0} for pid,t,ca,ps,cc in page_rows]
    return {"items":items,"total":total,"total_copies":prompt_db.count_total_copies(),"page":page}

@app.get("/api/prompt/history/{pid}")
async def prompt_history_item(pid:int):
    r=prompt_db.get_prompt_by_id(pid)
    if not r: raise HTTPException(404)
    return {"id":pid,"prompt":r[0],"copy_count":r[1]}

@app.delete("/api/prompt/history/{pid}")
async def prompt_delete(pid:int): prompt_db.delete_prompt(pid); return {"success":True}

@app.post("/api/prompt/history/batch-delete")
async def prompt_batch_delete(req:dict):
    ids=req.get("ids",[]); prompt_db.delete_prompts_batch(ids); return {"success":True}

@app.post("/api/prompt/history/{pid}/copy")
async def prompt_copy(pid:int): prompt_db.increment_copy_count(pid); return {"success":True}

# ═══════════════════════════════════════════
# 单图提示词生成 (TS 前端全链条专用)
# ═══════════════════════════════════════════
class SinglePromptReq(BaseModel):
    model: str = "deepseek4"
    subject: str = ""
    scene: str = ""
    weather: str = ""
    style: str = ""
    action: str = ""
    min_product: int = 1
    max_product: int = 1
    tolerance: float = 65.0
    extra: str = ""
    aspect_ratio: str = "1:1"
    style_quality: str = "写实"
    audience: str = "默认随机(按画像比例55/15/30)"

SINGLE_IMAGE_SYSTEM = """你是一个为 gpt-image-2 写单张图片生成提示词的专业AI。你的任务是根据给定的参数，生成一段简洁、精准的单图描述。

规则：
1. 只输出一段描述，用于生成一张图，不得输出多条或编号
2. 禁止输出"第一张/第二张/第三张/第四张"或任何编号
3. 禁止输出"四张图/四宫格/组图/拼图/九宫格"
4. 禁止编造产品文件名（如 s101.png、s101 等），用"产品/酒瓶/主体"等通用词
5. 产品数量严格按参数里 min_product-max_product 范围
6. 输出纯文本，不要 Markdown，不要 JSON，不要解释性文字
7. 描述用中文，在末尾附加英文关键词标签（逗号分隔）
8. 整体控制在 200 字以内，精简有画面感"""

def _build_single_user_prompt(params: dict) -> str:
    lines = ["为 gpt-image-2 写一段单图生图提示词。参数如下："]
    if params.get("subject"):
        lines.append(f"画面主体：{params['subject']}")
    else:
        lines.append("画面主体：用户指定产品/主体（不要编造文件名）")
    lines.append(f"场景：{params.get('scene', '随机')}")
    lines.append(f"光线天气：{params.get('weather', '随机')}")
    lines.append(f"视觉风格：{params.get('style', '随机')}")
    lines.append(f"动作姿态：{params.get('action', '随机')}")
    if params.get("aspect_ratio"):
        lines.append(f"画幅比例：{params['aspect_ratio']}")
    if params.get("style_quality") and params["style_quality"] != "写实":
        lines.append(f"渲染风格：{params['style_quality']}")
    lines.append(f"产品数量：{params.get('min_product', 1)}-{params.get('max_product', 1)} 个")
    if params.get("extra"):
        lines.append(f"附加要求：{params['extra']}")
    lines.append("\n请直接输出一段完整的生图提示词：")
    return "\n".join(lines)

@app.post("/api/prompt/generate-single")
async def generate_single_prompt(req: SinglePromptReq):
    if req.model not in MODELS:
        raise HTTPException(400, f"未知模型: {req.model}")
    try:
        ai_client = AIClient(req.model)
        scene = req.scene if req.scene != "随机" else random.choice(SCENE_OPTIONS)
        weather = req.weather if req.weather != "随机" else random.choice(WEATHER_OPTIONS)
        style = req.style if req.style != "随机" else random.choice(STYLE_OPTIONS)
        action = req.action if req.action != "随机" else random.choice(ACTION_OPTIONS)
        person = random_person(req.audience)
        user_msg = _build_single_user_prompt({
            "subject": req.subject,
            "scene": scene,
            "weather": weather,
            "style": style,
            "action": action,
            "min_product": req.min_product,
            "max_product": req.max_product,
            "aspect_ratio": req.aspect_ratio,
            "style_quality": req.style_quality,
            "extra": req.extra,
        })
        result = ai_client.generate_prompt(
            {"scene": scene, "person": person, "audience": req.audience,
             "weather": weather, "style": style, "action": action,
             "count": 1, "min_product": req.min_product, "max_product": req.max_product,
             "extra": req.extra},
            temperature=0.85,
        )
        # Override the prompt to use our single-image system message
        messages = [
            {"role": "system", "content": SINGLE_IMAGE_SYSTEM},
            {"role": "user", "content": user_msg},
        ]
        try:
            from openai import OpenAI
            client = OpenAI(base_url=MODELS[req.model]["base_url"], api_key=MODELS[req.model]["api_key"])
            extra_body = {}
            if "volces" in MODELS[req.model].get("base_url", ""):
                extra_body["top_p"] = 0.92
            resp = client.chat.completions.create(
                model=MODELS[req.model]["model"],
                messages=messages,
                max_tokens=1024,
                temperature=0.85,
                seed=random.randint(1, 99999),
                **({"extra_body": extra_body} if extra_body else {}),
            )
            prompt_text = (resp.choices[0].message.content or "").strip()
        except Exception:
            prompt_text = result or ""
        if not prompt_text:
            raise HTTPException(500, "模型未返回有效提示词")
        title = (prompt_text.split("\n")[0].strip()[:40] if prompt_text else "AI 提示词")
        return {
            "success": True,
            "title": title,
            "prompt": prompt_text,
            "chinesePrompt": prompt_text,
            "englishPrompt": prompt_text,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"单图提示词生成失败: {e}")

def _run_prompt_gen(req:PromptGenReq):
    global _pgen_state
    try:
        ai_client = AIClient(req.model)
        existing=[row[1] for row in prompt_db.get_all_prompts()]
        tolerance=req.tolerance/100.0; sc=0
        audience_key=req.audience
        param_str=f"模型:{req.model}|人群:{audience_key}|场景:{req.scene}|天气:{req.weather}|动作:{req.action}"
        for i in range(req.batch):
            if not _pgen_state["running"]: break
            _pgen_state["progress"]=i; _pgen_state["message"]=f"生成第{i+1}/{req.batch}批..."
            person=random_person(audience_key)
            scene=random.choice(SCENE_OPTIONS) if req.scene=="随机" else req.scene
            weather=random.choice(WEATHER_OPTIONS) if req.weather=="随机" else req.weather
            style=random.choice(STYLE_OPTIONS) if req.style=="随机" else req.style
            action=random.choice(ACTION_OPTIONS) if req.action=="随机" else req.action
            extra=req.extra.strip()
            if extra in ["无特殊要求，让AI自由发挥","无特殊要求",""]: extra=""
            params={"scene":scene,"person":person,"audience":audience_key,"weather":weather,
                    "style":style,"action":action,"count":4,"min_product":req.min_product,
                    "max_product":req.max_product,"extra":extra}
            ok=False
            for attempt in range(5):
                if not _pgen_state["running"]: break
                try:
                    temp=round(0.80+min(attempt*0.025,0.15),2)
                    result=ai_client.generate_prompt(params,temperature=temp,seed=random.randint(1,99999))
                    if not result: time.sleep(0.3); continue
                    ms,_=checker.find_max_similarity(result,existing)
                    if ms>=tolerance:
                        if attempt>=2: params["scene"]=random.choice(SCENE_OPTIONS); params["action"]=random.choice(ACTION_OPTIONS)
                        time.sleep(0.2); continue
                    prompt_db.add_prompt(result,param_str)
                    existing.append(result); sc+=1; _pgen_state["success_count"]=sc
                    _pgen_state["message"]=f"✅ 第{i+1}批完成 (相似度{ms:.0%})"
                    ok=True; break
                except Exception as e:
                    _pgen_state["last_error"]=str(e)
                    _pgen_state["message"]=f"⚠️ {str(e)[:120]}，重试..."
                    time.sleep(1)
            if not ok: _pgen_state["message"]=f"⚠️ 第{i+1}批跳过：{_pgen_state.get('last_error','未生成有效内容')[:120]}"
        _pgen_state["progress"]=req.batch
        if sc:
            _pgen_state["message"]=f"✅ 完成！成功{sc}/{req.batch}批={sc*4}张"
        else:
            _pgen_state["message"]=f"❌ 生成失败：{_pgen_state.get('last_error','没有生成有效内容')[:160]}"
    except Exception as e:
        _pgen_state["last_error"]=str(e)
        _pgen_state["message"]=f"❌ {str(e)}"
    finally: _pgen_state["running"]=False

# ═══════════════════════════════════════════
# 文案生成 API (/api/copy/*)
# ═══════════════════════════════════════════
_cgen_state={"running":False,"progress":0,"total":0,"message":"","result":None,"start_time":0}
_cancel_event: Optional[threading.Event] = None

class CopyGenReq(BaseModel):
    copy_type:str="朋友圈/社群"; count:int=10; workers:int=5; custom_topic:str=""; custom_style:str=""

@app.get("/api/copy/types")
async def copy_types(): return {"types":{k:v["label"] for k,v in COPY_TYPES.items()}}

@app.get("/api/copy/health")
async def copy_health(): return {"status":"ok"}

@app.post("/api/copy/generate")
async def copy_start(req:CopyGenReq):
    global _cgen_state, _cancel_event
    if _cgen_state["running"]: raise HTTPException(400,"已有任务在运行")
    if req.copy_type not in COPY_TYPES: raise HTTPException(400,f"未知类型:{req.copy_type}")
    _cancel_event=threading.Event()
    _cgen_state={"running":True,"progress":0,"total":req.count,"message":"准备中...","result":None,"start_time":time.time(),
                 "accepted":0,"failed_count":0,"dup":0,"issue":0,"copy_type":req.copy_type}
    def cb(cur,tot,acc,fail,dup,issue):
        _cgen_state["progress"]=cur; _cgen_state["accepted"]=acc; _cgen_state["failed_count"]=fail
        _cgen_state["dup"]=dup; _cgen_state["issue"]=issue
        e=time.time()-_cgen_state["start_time"]; eta=(e/cur*(tot-cur)) if cur else 0
        _cgen_state["message"]=f"⏳ {cur}/{tot} · ✅{acc} · ❌{fail} · ⏱≈{eta:.0f}s"
    def worker():
        global _cgen_state, _cancel_event
        try:
            r=generate_batch(req.copy_type,req.count,req.custom_style,req.custom_topic,cb,req.workers,cancel_event=_cancel_event)
            _cgen_state["result"]=r
            e=time.time()-_cgen_state["start_time"]
            cn=" (已取消)" if r.get("cancelled") else ""
            _cgen_state["message"]=f"{'⏹' if r.get('cancelled') else '✅'} 完成{cn}：accepted {r['accepted_count']}/{r['total_count']} · 耗时{e:.0f}s"
        except Exception as e: _cgen_state["message"]=f"❌ {str(e)}"
        finally: _cgen_state["running"]=False; _cancel_event=None
    threading.Thread(target=worker,daemon=True).start()
    return {"success":True}

@app.post("/api/copy/stop")
async def copy_stop():
    global _cancel_event
    if _cancel_event: _cancel_event.set()
    _cgen_state["running"]=False; return {"success":True}

@app.get("/api/copy/status")
async def copy_status():
    e=time.time()-_cgen_state["start_time"] if _cgen_state["start_time"] else 0
    return {"running":_cgen_state["running"],"progress":_cgen_state["progress"],"total":_cgen_state["total"],
            "message":_cgen_state["message"],"elapsed":round(e),"accepted":_cgen_state.get("accepted",0),
            "failed_count":_cgen_state.get("failed_count",0),"dup":_cgen_state.get("dup",0),"issue":_cgen_state.get("issue",0)}

@app.get("/api/copy/result")
async def copy_result():
    if _cgen_state["running"]: raise HTTPException(400,"仍在生成中")
    if not _cgen_state["result"]: raise HTTPException(404,"无结果")
    r=_cgen_state["result"]; e=time.time()-_cgen_state["start_time"] if _cgen_state["start_time"] else 0
    return {"results":r["results"][:50],"total_count":r["total_count"],"accepted_count":r["accepted_count"],
            "failed":r.get("failed",[]),"avg_similarity":r["avg_similarity"],"max_similarity":r["max_similarity"],
            "dup_rewrites":r["dup_rewrites"],"issue_rewrites":r["issue_rewrites"],
            "cancelled":r.get("cancelled",False),"job_file":r.get("job_file"),"gen_time":round(e,1)}

OUTPUT_DIR = os.path.join(_HERE, "modules", "wenan", "outputs")

@app.get("/api/copy/jobs")
async def copy_jobs():
    jobs=[]
    for csv_path in sorted(glob.glob(os.path.join(OUTPUT_DIR,"job_*.csv")),reverse=True):
        p=csv_path[:-4]; jl=p+".jsonl"; bn=os.path.basename(p); ts=bn[4:]
        st={"total":0,"accepted":0,"failed":0,"cancelled":0}
        if os.path.exists(jl):
            try:
                with open(jl,encoding="utf-8") as f:
                    for line in f:
                        if not line.strip(): continue
                        e=json.loads(line); st["total"]+=1
                        s=e.get("status",""); st[s]=st.get(s,0)+1
            except: pass
        jobs.append({"prefix":bn,"ts":ts,"label":f"📁 {ts[:8]} {ts[9:15]}","stats":st})
    return {"jobs":jobs}

@app.get("/api/copy/jobs/{prefix}/csv")
async def copy_dl_csv(prefix:str):
    p=os.path.join(OUTPUT_DIR,f"{prefix}.csv")
    if not os.path.exists(p): raise HTTPException(404)
    return Response(content=open(p,"rb").read(),media_type="text/csv",
                    headers={"Content-Disposition":f"attachment; filename={os.path.basename(p)}"})

@app.get("/api/copy/jobs/{prefix}/jsonl")
async def copy_dl_jsonl(prefix:str):
    p=os.path.join(OUTPUT_DIR,f"{prefix}.jsonl")
    if not os.path.exists(p): raise HTTPException(404)
    return Response(content=open(p,"rb").read(),media_type="application/x-ndjson",
                    headers={"Content-Disposition":f"attachment; filename={os.path.basename(p)}"})

@app.get("/api/scene-pool")
async def scene_pool():
    """返回 50 个可选场景列表，供前端下拉使用。"""
    from modules.storyboard.scene_pool import SCENE_POOL
    return {"scenes": SCENE_POOL}


# ═══════════════════════════════════════════
# 标签生成 API (/api/hashtag/*)
# ═══════════════════════════════════════════
class HashtagGenerateReq(BaseModel):
    topic: str = ""                     # 直接传文本主题（不依赖 mp4）
    dir: str = ""                       # 或传含 .mp4 的目录路径
    platform: str = "youtube"           # youtube | tiktok | instagram
    lang: str = ""                      # 语言，空=自动检测
    force: bool = False                 # 强制重新生成


@app.get("/api/hashtag/config")
async def hashtag_config():
    """返回标签生成配置。"""
    return {
        "platforms": {
            "youtube": {"label": "YouTube", "hard_limit": 60, "recommended": "3-5"},
            "tiktok": {"label": "TikTok", "hard_limit": 5, "recommended": "3-5"},
            "instagram": {"label": "Instagram", "hard_limit": 5, "recommended": "3-5"},
        },
        "min_tags": hashtag_settings.min_tags,
        "max_tags": hashtag_settings.max_tags,
        "max_tag_length": hashtag_settings.max_tag_length,
        "always_include": list(hashtag_settings.always_include),
        "model": hashtag_settings.model,
    }


@app.post("/api/hashtag/generate")
async def hashtag_generate(req: HashtagGenerateReq):
    """
    生成视频发布标签。
    支持两种模式：
    1. 传 topic（文本主题直接生成）
    2. 传 dir（扫描目录中的 .mp4 文件批量生成）
    """
    platform = req.platform
    if platform not in ("youtube", "tiktok", "instagram"):
        raise HTTPException(400, "platform 必须是 youtube / tiktok / instagram")

    # ── 模式 1: 文本主题直接生成 ──
    if req.topic.strip():
        topic = req.topic.strip()
        if req.lang.strip():
            lang = req.lang.strip()
            tags = generate_hashtags(topic, lang, platform=platform)
        else:
            lang, tags = detect_and_generate(topic, platform=platform)

        return {
            "success": True,
            "topic": topic,
            "language": lang,
            "platform": platform,
            "tags_list": tags,
            "tags_string": " ".join(tags),
            "tag_count": len(tags),
            "mode": "topic",
        }

    # ── 模式 2: 目录扫描 ──
    if req.dir.strip():
        dir_path = Path(req.dir.strip()).resolve()
        # Restrict to project static/ directory to prevent path traversal
        allowed_root = Path(_HERE, "static").resolve()
        if str(dir_path) != str(allowed_root) and not str(dir_path).startswith(str(allowed_root) + os.sep):
            raise HTTPException(400, "目录必须在项目静态资源目录下")
        if not dir_path.is_dir():
            raise HTTPException(400, f"目录不存在: {req.dir}")

        mp4_files = sorted(dir_path.glob("*.mp4"))
        if not mp4_files:
            raise HTTPException(404, f"目录中没有 .mp4 文件: {req.dir}")

        results = []
        from enricher.reader import resolve_meta
        from enricher.writer import build_hashtags_block, write_hashtags

        lang_override = req.lang.strip() or None

        for mp4_path in mp4_files:
            meta = resolve_meta(mp4_path, lang_override=lang_override)
            json_path = mp4_path.with_suffix(".json")

            # Skip if already enriched (unless --force)
            if not req.force and json_path.exists():
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                    if "hashtags" in existing:
                        results.append({
                            "file": mp4_path.name,
                            "status": "skipped",
                            "tags_list": existing["hashtags"].get("tags_list", []),
                            "tags_string": existing["hashtags"].get("tags_string", ""),
                        })
                        continue
                except (json.JSONDecodeError, OSError):
                    pass

            try:
                if meta.language_hint:
                    language = meta.language_hint
                    tags = generate_hashtags(meta.topic, language, platform=platform)
                else:
                    language, tags = detect_and_generate(meta.topic, platform=platform)

                if not tags:
                    tags = list(hashtag_settings.always_include) or ["#shorts"]

                block = build_hashtags_block(
                    tags_list=tags,
                    language=language,
                    model=hashtag_settings.model,
                    source=meta.source,
                    platform=platform,
                )
                write_hashtags(json_path, block)
                results.append({
                    "file": mp4_path.name,
                    "status": "ok",
                    "tags_list": tags,
                    "tags_string": " ".join(tags),
                    "language": language,
                })
            except Exception as e:
                results.append({
                    "file": mp4_path.name,
                    "status": "error",
                    "error": str(e),
                })

        ok_count = sum(1 for r in results if r["status"] == "ok")
        return {
            "success": True,
            "total": len(mp4_files),
            "ok": ok_count,
            "skipped": sum(1 for r in results if r["status"] == "skipped"),
            "error": sum(1 for r in results if r["status"] == "error"),
            "results": results,
            "mode": "directory",
        }

    raise HTTPException(400, "请提供 topic 或 dir 参数")


@app.get("/api/health")
async def health(): return {"status":"ok","services":["gpt-image","image","prompt","copy","hashtag"]}

# ═══ Root — serve index.html ═══
@app.get("/")
async def index():
    built_index = os.path.join(DIST_DIR, "index.html")
    if os.path.exists(built_index):
        return FileResponse(built_index)
    return FileResponse(os.path.join(_HERE, "index.html"))

def _free_dev_port_for_current_server(port: int) -> None:
    if os.name != "nt":
        return

    same_health = False
    try:
        health = requests.get(f"http://127.0.0.1:{port}/api/health", timeout=1)
        if health.status_code == 200:
            services = health.json().get("services", [])
            same_health = all(name in services for name in ("gpt-image", "image", "prompt", "copy"))
    except Exception:
        pass

    ps_script = (
        f"$items = Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | "
        "ForEach-Object { "
        "$p = Get-CimInstance Win32_Process -Filter \"ProcessId=$($_.OwningProcess)\"; "
        "[PSCustomObject]@{Pid=$_.OwningProcess; CommandLine=$p.CommandLine} "
        "}; "
        "$items | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception as exc:
        print(f"[dev-server] 跳过端口检查：{exc}")
        return

    output = result.stdout.strip()
    if not output:
        return

    try:
        listeners = json.loads(output)
    except json.JSONDecodeError:
        print(f"[dev-server] 无法解析端口 {port} 占用信息：{output}")
        return

    if isinstance(listeners, dict):
        listeners = [listeners]

    current_pid = os.getpid()
    current_server = os.path.normcase(os.path.abspath(__file__))
    killed = []
    blocked = []

    for item in listeners:
        pid = int(item.get("Pid") or 0)
        command_line = item.get("CommandLine") or ""
        normalized_command = os.path.normcase(command_line.replace("/", "\\"))
        if pid == current_pid:
            continue
        if current_server in normalized_command or same_health:
            subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], capture_output=True, text=True)
            killed.append(pid)
        else:
            blocked.append((pid, command_line))

    if killed:
        print(f"[dev-server] 已清理旧的 work/server.py 进程：{', '.join(map(str, killed))}")
        for _ in range(20):
            check = subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    f"Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue"
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if not check.stdout.strip():
                break
            time.sleep(0.2)

    if blocked:
        details = "; ".join(f"PID {pid}: {cmd}" for pid, cmd in blocked)
        print(f"[dev-server] 端口 {port} 被非当前 server.py 进程占用，未自动结束：{details}")

if __name__ == "__main__":
    import uvicorn
    _free_dev_port_for_current_server(8000)
    uvicorn.run(app, host="0.0.0.0", port=8000)
