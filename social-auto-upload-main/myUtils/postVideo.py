# myUtils/postVideo.py - Legacy wrapper, delegates to uploader modules.
import sys, io, asyncio, os, traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from conf import BASE_DIR
from patchright.async_api import async_playwright
from uploader.douyin_uploader.main import DouYinVideo
from uploader.ks_uploader.main import KSVideo
from uploader.xiaohongshu_uploader.main import XiaoHongShuVideo
from uploader.tencent_uploader.main import TencentVideo
from utils.log import backend_logger


def _build_video_file_list(file_list: list) -> list:
    result = []
    for f in file_list:
        p = Path(f)
        if p.is_absolute():
            result.append(str(p))
        else:
            result.append(str(Path(BASE_DIR / "videoFile" / f)))
    return result


def _resolve_account_file(account: str) -> str:
    """把 account（文件名或路径）解析为 cookie 文件的绝对路径。"""
    p = Path(account)
    if p.is_absolute():
        return str(p)
    # 如果已经是 cookiesFile/ 下的相对路径，直接拼接 BASE_DIR
    if str(p).startswith("cookiesFile") or str(p).startswith("cookiesFile/"):
        return str(Path(BASE_DIR / p))
    # 否则默认在 cookiesFile/ 下查找
    return str(Path(BASE_DIR / "cookiesFile" / p))


def post_video_DouYin(title, file_list, tags, account_list, category, enableTimer,
                      videos_per_day, daily_times, start_days,
                      thumbnail_path="", productLink="", productTitle=""):
    video_paths = _build_video_file_list(file_list)
    for account in account_list:
        for vp in video_paths:
            resolved = _resolve_account_file(str(account))
            backend_logger.info(f"🔍 抖音解析路径 | raw={account} | resolved={resolved} | exists={os.path.exists(resolved)}")
            try:

                async def _upload_with_playwright():
                    async with async_playwright() as playwright:
                        await DouYinVideo(
                            title=title,
                            file_path=vp,
                            tags=tags if tags else [],
                            publish_date=0,
                            account_file=resolved,
                            thumbnail_landscape_path=thumbnail_path or None,
                            productLink=productLink,
                            productTitle=productTitle,
                        ).upload(playwright)

                asyncio.run(_upload_with_playwright())
            except Exception as e:
                backend_logger.error(f"❌ 抖音发布失败 | account={account} | {e}\n{traceback.format_exc()}")


def post_video_ks(title, file_list, tags, account_list, category, enableTimer,
                  videos_per_day, daily_times, start_days, thumbnail_path=""):
    video_paths = _build_video_file_list(file_list)
    for account in account_list:
        for vp in video_paths:
            try:

                async def _upload_with_playwright():
                    async with async_playwright() as playwright:
                        await KSVideo(
                            title=title,
                            file_path=vp,
                            tags=tags if tags else [],
                            publish_date=0,
                            account_file=_resolve_account_file(str(account)),
                            thumbnail_path=thumbnail_path or None,
                        ).upload(playwright)

                asyncio.run(_upload_with_playwright())
            except Exception as e:
                backend_logger.error(f"❌ 快手发布失败 | account={account} | {e}\n{traceback.format_exc()}")


def post_video_xhs(title, file_list, tags, account_list, category, enableTimer,
                   videos_per_day, daily_times, start_days, thumbnail_path=""):
    video_paths = _build_video_file_list(file_list)
    for account in account_list:
        for vp in video_paths:
            try:

                async def _upload_with_playwright():
                    async with async_playwright() as playwright:
                        await XiaoHongShuVideo(
                            title=title,
                            file_path=vp,
                            tags=tags if tags else [],
                            publish_date=0,
                            account_file=_resolve_account_file(str(account)),
                            thumbnail_path=thumbnail_path or None,
                        ).upload(playwright)

                asyncio.run(_upload_with_playwright())
            except Exception as e:
                backend_logger.error(f"❌ 小红书发布失败 | account={account} | {e}\n{traceback.format_exc()}")


def post_video_tencent(title, file_list, tags, account_list, category, enableTimer,
                       videos_per_day, daily_times, start_days, is_draft=False,
                       thumbnail_path=""):
    video_paths = _build_video_file_list(file_list)
    for account in account_list:
        for vp in video_paths:
            try:

                async def _upload_with_playwright():
                    async with async_playwright() as playwright:
                        await TencentVideo(
                            title=title,
                            file_path=vp,
                            tags=tags if tags else [],
                            publish_date=0,
                            account_file=_resolve_account_file(str(account)),
                            is_draft=is_draft,
                            thumbnail_path=thumbnail_path or None,
                        ).upload(playwright)

                asyncio.run(_upload_with_playwright())
            except Exception as e:
                backend_logger.error(f"❌ 视频号发布失败 | account={account} | {e}\n{traceback.format_exc()}")
