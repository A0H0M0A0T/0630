"""
应用日志模块

使用标准库 logging + RotatingFileHandler
- 控制台输出：INFO 级别
- 文件输出：DEBUG 级别，带轮转（10MB * 5）
- 绝不记录 token、完整 base64 图片内容
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_FILE = LOG_DIR / "app.log"
MAX_BYTES = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5

_logger: logging.Logger | None = None


def _sanitize_record(record: logging.LogRecord) -> bool:
    """过滤敏感信息：如果消息中包含明显 base64 数据则截断标记"""
    msg = record.getMessage()
    # 如果消息中包含 data:image/...;base64, 说明有完整的 base64 图片，替换为占位符
    if "base64," in msg:
        # 找到 base64, 之后的内容替换为 [BASE64_REDACTED]
        idx = msg.find("base64,")
        # 找到这个 key 的起始位置
        key_start = msg.rfind('"', 0, idx)
        if key_start == -1:
            key_start = msg.rfind("'", 0, idx)
        if key_start == -1:
            key_start = msg.rfind(" ", 0, idx)
        if key_start >= 0:
            record.msg = msg[:key_start] + '"***": "[BASE64_REDACTED]"'
        else:
            record.msg = msg[:idx] + "[BASE64_REDACTED]"
        record.args = ()
    return True


def get_logger(name: str = "app") -> logging.Logger:
    """获取或创建应用日志器"""
    global _logger

    if _logger is not None:
        return _logger.getChild(name)

    _logger = logging.getLogger("image_recognizer")
    _logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler（reload 场景）
    if _logger.handlers:
        return _logger.getChild(name)

    # 控制台 handler — INFO
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-5s] %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_fmt)
    _logger.addHandler(console_handler)

    # 确保日志目录存在
    LOG_DIR.mkdir(exist_ok=True)

    # 文件 handler — DEBUG，RotatingFileHandler
    file_handler = RotatingFileHandler(
        str(LOG_FILE),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-5s] %(name)s (%(filename)s:%(lineno)d) | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_fmt)
    # 添加敏感信息过滤器
    file_handler.addFilter(_sanitize_record)
    _logger.addHandler(file_handler)

    return _logger.getChild(name)
