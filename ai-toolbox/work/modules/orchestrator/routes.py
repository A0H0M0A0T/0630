"""
FastAPI routes for the workflow orchestrator.
"""
import sys, os, shutil
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _ROOT)

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel
from typing import Optional

from .state import WorkflowState, init_workflow_db
from .engine import start_workflow, get_workflow_status, get_workflow_result, stop_workflow

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


class WorkflowStartRequest(BaseModel):
    story_type: str = "正常性"       # 趣味性 / 休闲性 / 正常性
    gender: str = "随机"            # 随机 / 男 / 女
    scene: str = "随机"
    product_image: str = ""         # path to uploaded product image


@router.post("/start")
async def workflow_start(req: WorkflowStartRequest):
    """Start a new 6-step workflow. Returns workflow_id immediately."""
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

    try:
        wf_id = start_workflow(state)
        return {"success": True, "workflow_id": wf_id}
    except Exception as e:
        raise HTTPException(500, f"启动工作流失败: {e}")


@router.get("/status/{workflow_id}")
async def workflow_status(workflow_id: str):
    """Get current progress of a workflow."""
    status = get_workflow_status(workflow_id)
    if status is None:
        raise HTTPException(404, f"Workflow {workflow_id} not found")
    return status


@router.get("/result/{workflow_id}")
async def workflow_result(workflow_id: str):
    """Get full result of a completed workflow."""
    result = get_workflow_result(workflow_id)
    if result is None:
        # Check if it exists but is still running
        status = get_workflow_status(workflow_id)
        if status:
            raise HTTPException(409, f"Workflow still running. Current step: {status.get('current_step', '')}")
        raise HTTPException(404, f"Workflow {workflow_id} not found")
    return result


@router.post("/stop/{workflow_id}")
async def workflow_stop(workflow_id: str):
    """Request to stop a running workflow."""
    ok = stop_workflow(workflow_id)
    if not ok:
        raise HTTPException(404, f"Workflow {workflow_id} not found or already finished")
    return {"success": True, "message": "Workflow stop requested"}


@router.post("/upload-product")
async def workflow_upload_product(file: UploadFile = File(...)):
    """Upload a product reference image. Returns the saved path."""
    if not file.filename:
        raise HTTPException(400, "No file provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        raise HTTPException(400, "Only .png/.jpg/.jpeg allowed")

    product_dir = os.path.join(_ROOT, "static", "product")
    os.makedirs(product_dir, exist_ok=True)

    # Simple filename: product_timestamp.ext
    import time
    filename = f"product_{int(time.time())}{ext}"
    filepath = os.path.join(product_dir, filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"success": True, "path": f"/static/product/{filename}", "filename": filename}
