# myUtils/auth.py - Legacy wrapper, delegates to uploader modules.
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from conf import BASE_DIR
from uploader.douyin_uploader.main import cookie_auth as _douyin_cookie_auth
from uploader.ks_uploader.main import cookie_auth as _ks_cookie_auth
from uploader.xiaohongshu_uploader.main import cookie_auth as _xhs_cookie_auth
from uploader.tencent_uploader.main import cookie_auth as _tencent_cookie_auth


def _resolve_account_file(account: str) -> str:
    p = Path(account)
    if p.is_absolute():
        return str(p)
    if str(p).startswith("cookiesFile"):
        return str(Path(BASE_DIR / p))
    return str(Path(BASE_DIR / "cookiesFile" / p))


async def check_cookie(platform_type: int, account_file: str) -> bool:
    mapper = {
        1: _xhs_cookie_auth,
        2: _tencent_cookie_auth,
        3: _douyin_cookie_auth,
        4: _ks_cookie_auth,
    }
    auth_fn = mapper.get(platform_type)
    if auth_fn is None:
        return False
    try:
        return await auth_fn(_resolve_account_file(account_file))
    except Exception:
        return False
