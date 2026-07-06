# myUtils/login.py - Legacy wrapper, delegates to uploader QR login flows.
import sys, io, asyncio, sqlite3
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from conf import BASE_DIR
from uploader.douyin_uploader.main import douyin_cookie_gen as _douyin_login
from uploader.ks_uploader.main import get_ks_cookie as _ks_login
from uploader.xiaohongshu_uploader.main import xiaohongshu_cookie_gen as _xhs_login
from uploader.tencent_uploader.main import tencent_cookie_gen as _tencent_login


def _get_account_file(account_id: str) -> str:
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT filePath FROM user_info WHERE id = ?", (account_id,))
        row = cursor.fetchone()
    if row and row[0]:
        return str(Path(BASE_DIR / "cookiesFile" / row[0]))
    return str(Path(BASE_DIR / "cookiesFile" / f"{account_id}.json"))


def _make_qrcode_callback(status_queue):
    async def cb(payload: dict = None):
        if not isinstance(payload, dict):
            return
        image_path = payload.get('image_path', '')
        if image_path:
            status_queue.put(f"qr_status: qrcode_ready:{image_path}")
    return cb


async def douyin_cookie_gen(account_id, status_queue):
    try:
        status_queue.put("login_status: 开始抖音扫码登录...")
        account_file = _get_account_file(account_id)
        qrcode_cb = _make_qrcode_callback(status_queue)
        await _douyin_login(account_file, qrcode_callback=qrcode_cb)
        status_queue.put("login_status: success")
    except Exception as e:
        status_queue.put(f"login_status: error: {e}")


async def get_ks_cookie(account_id, status_queue):
    try:
        status_queue.put("login_status: 开始快手扫码登录...")
        account_file = _get_account_file(account_id)
        qrcode_cb = _make_qrcode_callback(status_queue)
        await _ks_login(account_file, qrcode_callback=qrcode_cb)
        status_queue.put("login_status: success")
    except Exception as e:
        status_queue.put(f"login_status: error: {e}")


async def xiaohongshu_cookie_gen(account_id, status_queue):
    try:
        status_queue.put("login_status: 开始小红书扫码登录...")
        account_file = _get_account_file(account_id)
        qrcode_cb = _make_qrcode_callback(status_queue)
        await _xhs_login(account_file, qrcode_callback=qrcode_cb)
        status_queue.put("login_status: success")
    except Exception as e:
        status_queue.put(f"login_status: error: {e}")


async def get_tencent_cookie(account_id, status_queue):
    try:
        status_queue.put("login_status: 开始视频号扫码登录...")
        account_file = _get_account_file(account_id)
        qrcode_cb = _make_qrcode_callback(status_queue)
        await _tencent_login(account_file, qrcode_callback=qrcode_cb)
        status_queue.put("login_status: success")
    except Exception as e:
        status_queue.put(f"login_status: error: {e}")
