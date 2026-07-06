"""
Pydantic 请求/响应数据模型
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional


class RecognizeByUrlRequest(BaseModel):
    """URL 方式识别 — 使用 HttpUrl 严格校验"""
    url: HttpUrl = Field(..., description="图片 URL (http/https only)")


class BatchRecognizeRequest(BaseModel):
    """批量识别请求 — 每项都是 HttpUrl"""
    images: list[HttpUrl] = Field(
        ..., min_length=1, max_length=20, description="图片 URL 列表（最多20张）"
    )


class HistoryItem(BaseModel):
    """历史记录项"""
    id: int
    image_source: str
    image_thumb: Optional[str] = None
    result_json: Optional[dict] = None
    created_at: str


class HistoryListResponse(BaseModel):
    """历史记录列表"""
    items: list[HistoryItem]
    total: int
    page: int
    page_size: int


class DeleteResponse(BaseModel):
    """删除结果"""
    success: bool
    message: str


class ErrorResponse(BaseModel):
    """错误响应"""
    detail: str
