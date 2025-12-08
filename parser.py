import asyncio
import csv
import re
from datetime import datetime, timedelta
from typing import List, Dict

from TikTokApi import TikTokApi


class TikTokParser:
    """Парсер TikTok под TikTokApi 7.x"""

    def __init__(self):
        self.api = TikTokApi()
        self.session = None

    # ---------------------------
    # ИНИЦИАЛИЗАЦИЯ
    # ---------------------------
    async def init(self):
        """Запускает API с сессией"""
        self.session = await self.api.create_sessions(ms_token="", num_sessions=1)

    # ---------------------------
    # ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
    # ---------------------------
    @staticmethod
    def extract_hashtags(text: str) -> List[str]:
        if not text:
            return []
        return re.findall(r"#\w+", text)

    @staticmethod
    def within_7_days(ts: int) -> bool:
        if not ts:
            return False
        dt = datetime.fromtimestamp(ts)
        return dt >= datetime.now() - timedelta(days=7)

    # ---------------------------
    # НОВЫЙ ПОИСК (РАБОТАЕТ)
    # ---------------------------
    async def search(self, query: str, limit: int = 40) -> List[Dict]:
        """Рабочий поиск через новый search().videos()"""

        results = []
        print(f"🔍 Поиск TikTok по запросу: {query}")

        try:
            # Ключевой метод TikTokApi 7.x!
            async for video in self.api.search().videos(query, count=limit):
                data = self.convert(video)
                if data:
                    results.append(data)
                if len(results) >= limit:
                    break

        except Exception as e:
            print(f"❌ Ошибка поиска: {e}")

        return results

    # ---------------------------
    # ПАРСИНГ ВИДЕО
    # ---------------------------
    def convert(self, video) -> Dict:
        """Приводит видео в dict"""

        try:
            vid = getattr(video, "id", None)
            if not vid:
                return None

            author = getattr(video, "author", None)
            username = getattr(author, "unique_id", "unknown")

            desc = getattr(video, "desc", "")
            stats = getattr(video, "stats", None)

            views = getattr(stats, "play_count", 0)
            likes = getattr(stats, "digg_count", 0)

            ct = getattr(video, "create_time", 0)
            if ct > 1e10:
                ct /= 1000

            return {
                "id": str(vid),
                "url": f"https://www.tiktok.com/@{username}/video/{vid}",
                "description": desc,
                "views": int(views),
                "likes": int(likes),
                "timestamp": int(ct),
                "date": datetime.fromtimestamp(ct).strftime("%Y-%m-%d %H:%M:%S"),
                "hashtags": ", ".join(self.extract_hashtags(desc)),
                "author": username,
            }

        except Exception as e:
            print(f"⚠ Ошибка convert: {e}")
            return None

    # ---------------------------
    # СБОР ДАННЫХ
    # ---------------------------
    async def collect(self, query: str) -> List[Dict]:
        await self.init()

        raw = await self.search(query, limit=50)

        # фильтр по дате
        fresh = [v for v in raw if self.within_7_days(v["timestamp"])]

        # уникальные
        uniq = {v["id"]: v for v in fresh}.values()

        # сортировка
        final = sorted(uniq, key=lambda x: x["views"], reverse=True)

        return list(final)


# ---------------------------------------------
# ВЫЗОВ ИЗ FASTAPI
# ---------------------------------------------
def run_parser(query: str) -> List[Dict]:
    """Синхронный интерфейс для FastAPI"""

    parser = TikTokParser()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        data = loop.run_until_complete(parser.collect(query))

        # привести hashtags к списку
        for v in data:
            if isinstance(v["hashtags"], str):
                v["hashtags"] = [t.strip() for t in v["hashtags"].split(",") if t.strip()]

        return data

    except Exception as e:
        print(f"❌ Ошибка run_parser: {e}")
        return []


