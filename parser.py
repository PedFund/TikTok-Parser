import asyncio
import csv
import random
import re
from datetime import datetime
from typing import List, Dict, Optional

from TikTokApi import TikTokApi


class TikTokParser:
    """Основной класс парсера TikTok"""

    def __init__(self):
        self.api: Optional[TikTokApi] = None

    # ---------------------------
    # ИНИЦИАЛИЗАЦИЯ API
    # ---------------------------
    async def initialize_api_async(self):
        """Асинхронная инициализация TikTokApi"""
        try:
            self.api = TikTokApi()
            await self.api.create_sessions()
            print("✓ TikTok API инициализирован")
        except Exception as e:
            print(f"❌ Ошибка инициализации TikTokApi: {e}")
            raise e

    def initialize_api(self):
        """Синхронная обертка"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.initialize_api_async())

    # ---------------------------
    # ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
    # ---------------------------
    @staticmethod
    def extract_hashtags(text: str) -> List[str]:
        """Извлекает хэштеги из описания"""
        if not text:
            return []
        return re.findall(r"#\w+", text)

    @staticmethod
    def is_within_7_days(timestamp: int) -> bool:
        """Фильтрация по последним 7 дням"""
        if not timestamp:
            return False
        now = datetime.now().timestamp()
        return now - timestamp <= 7 * 24 * 60 * 60

    # ---------------------------
    # ПАРСИНГ ВИДЕО
    # ---------------------------
    def parse_video_data(self, video):
        """Преобразование video-объекта из TikTokApi в dict"""
        try:
            video_id = getattr(video, "id", None)
            if not video_id:
                return None

            # URL
            author = getattr(video, "author", None)
            author_id = getattr(author, "unique_id", "unknown")
            url = f"https://www.tiktok.com/@{author_id}/video/{video_id}"

            # Описание
            desc = getattr(video, "desc", "")

            # Статистика
            stats = getattr(video, "stats", None)
            views = getattr(stats, "play_count", 0)
            likes = getattr(stats, "digg_count", 0)

            # Дата
            create_time = getattr(video, "create_time", None)

            if create_time and create_time > 1e10:
                create_time /= 1000

            hashtags = self.extract_hashtags(desc)

            return {
                "id": str(video_id),
                "url": url,
                "description": desc,
                "views": int(views),
                "likes": int(likes),
                "date": datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')
                if create_time else "",
                "timestamp": int(create_time) if create_time else 0,
                "hashtags": ", ".join(hashtags),
                "author": author_id,
            }
        except Exception as e:
            print(f"⚠ Ошибка парсинга видео: {e}")
            return None

    # ---------------------------
    # ПОИСК ВИДЕО (НОВЫЙ API)
    # ---------------------------
    async def search_videos_async(self, query: str, max_results: int = 30) -> List[Dict]:
        """Поиск видео по ключевому слову или хэштегу"""

        videos = []

        try:
            print(f"🔍 Поиск: {query}")

            # ХЭШТЕГ (#макияж)
            if query.startswith("#"):
                tag = query.replace("#", "")
                hashtag_obj = await self.api.hashtag(name=tag)
                results = hashtag_obj.videos(count=max_results)

            # КЛЮЧЕВОЕ СЛОВО
            else:
                results = await self.api.video.search(query=query, count=max_results)

            async for video in results:
                v = self.parse_video_data(video)
                if v:
                    videos.append(v)
                if len(videos) >= max_results:
                    break

            await asyncio.sleep(random.uniform(2, 4))

        except Exception as e:
            print(f"⚠ Ошибка поиска: {e}")

        return videos

    def search_videos(self, query: str, max_results: int = 30) -> List[Dict]:
        """Синхронная оболочка"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.search_videos_async(query, max_results))

    # ---------------------------
    # СБОР ВИДЕО
    # ---------------------------
    def filter_by_date(self, videos: List[Dict]) -> List[Dict]:
        """Оставляет только последние 7 дней"""
        return [v for v in videos if self.is_within_7_days(v.get("timestamp", 0))]

    async def collect_videos_async(self, query: str) -> List[Dict]:
        """Асинхронный сбор всех видео по данному запросу"""

        if not self.api:
            await self.initialize_api_async()

        # Получаем список видео
        raw_videos = await self.search_videos_async(query, max_results=50)

        # Фильтрация по дате
        fresh = self.filter_by_date(raw_videos)

        # Удаление дублей
        uniq = {v["id"]: v for v in fresh}

        # Сортировка по просмотрам
        final = sorted(uniq.values(), key=lambda x: x["views"], reverse=True)

        return final

    def collect_videos(self, query: str) -> List[Dict]:
        """Синхронная оболочка"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.collect_videos_async(query))


# -----------------------------------------------------
# ВЫЗОВ ИЗ FASTAPI (API-режим)
# -----------------------------------------------------
def run_parser(query: str) -> List[Dict]:
    """
    Обертка API: пользователь передает query.
    """
    parser = TikTokParser()

    try:
        parser.initialize_api()
        videos = parser.collect_videos(query)

        # Хэштеги превращаем в список
        for v in videos:
            if isinstance(v.get("hashtags"), str):
                v["hashtags"] = [tag.strip() for tag in v["hashtags"].split(",") if tag.strip()]

        return videos

    except Exception as e:
        print(f"❌ Ошибка run_parser(): {e}")
        return []

