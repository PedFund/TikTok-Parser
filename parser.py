import asyncio
from datetime import datetime
from typing import List, Dict

from TikTokApi import TikTokApi


# -------------------------------------
#  ИНИЦИАЛИЗАЦИЯ API
# -------------------------------------
async def get_api():
    """
    Создаёт рабочую сессию TikTokApi (TikTokApi 7.x)
    """
    api = TikTokApi()
    await api.create_sessions()
    return api


# -------------------------------------
#  ОБРАБОТКА ОДНОГО ВИДЕО
# -------------------------------------
def video_to_dict(video):
    """Превращает TikTokApi объект видео в dict"""

    try:
        video_id = getattr(video, "id", "")
        author = getattr(video, "author", None)
        author_id = getattr(author, "unique_id", "unknown")

        url = f"https://www.tiktok.com/@{author_id}/video/{video_id}"
        desc = getattr(video, "desc", "")

        stats = getattr(video, "stats", None)
        views = getattr(stats, "play_count", 0)
        likes = getattr(stats, "digg_count", 0)

        ts = getattr(video, "create_time", 0)
        if ts > 1e10:
            ts = ts / 1000

        date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else ""

        return {
            "id": str(video_id),
            "url": url,
            "description": desc,
            "views": int(views),
            "likes": int(likes),
            "timestamp": int(ts),
            "date": date,
            "author": author_id,
            "hashtags": []
        }

    except Exception:
        return None


# -------------------------------------
#  ПОИСК ВИДЕО (ОФИЦИАЛЬНЫЙ МЕТОД TikTokApi 7.x)
# -------------------------------------
async def search_async(query: str, limit: int = 30) -> List[Dict]:
    """
    Асинхронный поиск видео TikTok (TikTokApi v7.x)
    """
    api = await get_api()

    results = []

    try:
        videos = api.video.search(query=query, count=limit)

        async for v in videos:
            parsed = video_to_dict(v)
            if parsed:
                results.append(parsed)
            if len(results) >= limit:
                break

    except Exception as e:
        print("Ошибка поиска:", e)

    return results


# -------------------------------------
#  СИНХРОННАЯ ОБОЛОЧКА ДЛЯ FASTAPI
# -------------------------------------
def run_parser(query: str) -> List[Dict]:
    """
    Синхронный вызов для FastAPI
    """

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop = asyncio.get_event_loop()

    try:
        return loop.run_until_complete(search_async(query))
    except Exception as e:
        print("❌ Ошибка run_parser:", e)
        return []

