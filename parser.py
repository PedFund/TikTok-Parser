"""
TikTok Parser для сбора популярных роликов по теме "тушь для ресниц"
Собирает ролики за последние 7 дней с фильтрацией дублей и сортировкой по популярности
"""

import csv
import json
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Set
import requests
import asyncio
from TikTokApi import TikTokApi
import os


class TikTokParser:
    """Парсер для сбора данных из TikTok"""
    
    def __init__(self):
        self.api = None
        self.seen_video_ids: Set[str] = set()
        self.videos: List[Dict] = []
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
        ]
        
    async def initialize_api_async(self):
        """Асинхронная инициализация TikTok API"""
        try:
            # Попытка асинхронной инициализации (новые версии TikTokApi)
            if hasattr(TikTokApi, 'create'):
                self.api = await TikTokApi.create()
                print("✓ TikTok API инициализирован (асинхронный режим)")
                return True
        except Exception as e:
            print(f"⚠ Ошибка асинхронной инициализации API: {e}")
        
        try:
            # Попытка синхронной инициализации (старые версии TikTokApi)
            self.api = TikTokApi()
            print("✓ TikTok API инициализирован (синхронный режим)")
            return True
        except Exception as e2:
            print(f"⚠ Ошибка синхронной инициализации: {e2}")
            print("💡 Убедитесь, что установлен playwright: playwright install chromium")
            self.api = None
            return False
    
    def initialize_api(self):
        """Синхронная обертка для инициализации API"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.initialize_api_async())
    
    def random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Случайная задержка для обхода rate limits"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)
    
    def get_search_queries(self) -> List[str]:
        """Формирование списка поисковых запросов"""
        keywords = [
            "тушь для ресниц",
            "стойкая тушь",
            "объемная тушь"
        ]
        
        hashtags = [
            "тушь",
            "ресницы",
            "макияж"
        ]
        
        queries = keywords + [f"#{tag}" for tag in hashtags]
        return queries
    
    def is_within_7_days(self, timestamp: int) -> bool:
        """Проверка, что ролик опубликован в последние 7 дней"""
        if not timestamp:
            return False
        
        try:
            # TikTok использует Unix timestamp в секундах
            video_date = datetime.fromtimestamp(timestamp)
            seven_days_ago = datetime.now() - timedelta(days=7)
            return video_date >= seven_days_ago
        except Exception:
            return False
    
    def extract_hashtags(self, text: str) -> List[str]:
        """Извлечение хештегов из текста"""
        if not text:
            return []
        
        hashtags = []
        words = text.split()
        for word in words:
            if word.startswith('#'):
                hashtags.append(word)
        return hashtags
    
    def parse_video_data(self, video_data) -> Dict:
        """Извлечение данных из объекта видео"""
        try:
            # Обработка разных форматов данных TikTokApi
            if hasattr(video_data, 'as_dict'):
                video_data = video_data.as_dict
            elif hasattr(video_data, '__dict__'):
                video_data = video_data.__dict__
            elif not isinstance(video_data, dict):
                # Попытка преобразования в dict
                try:
                    video_data = dict(video_data)
                except:
                    video_data = {}
            
            video_id = str(video_data.get('id', video_data.get('video_id', '')))
            if not video_id or video_id in self.seen_video_ids:
                return None
            
            self.seen_video_ids.add(video_id)
            
            # Получение основных данных (разные варианты структуры)
            stats = video_data.get('stats', video_data.get('statistics', {}))
            if not isinstance(stats, dict):
                stats = {}
            
            author = video_data.get('author', video_data.get('user', {}))
            if not isinstance(author, dict):
                author = {}
            
            # Формирование ссылки
            author_id = author.get('uniqueId', author.get('unique_id', author.get('username', 'unknown')))
            video_url = f"https://www.tiktok.com/@{author_id}/video/{video_id}"
            
            # Описание
            desc = video_data.get('desc', video_data.get('description', video_data.get('text', '')))
            
            # Статистика (разные варианты названий полей)
            views = stats.get('playCount', stats.get('play_count', stats.get('view_count', stats.get('views', 0))))
            likes = stats.get('diggCount', stats.get('digg_count', stats.get('like_count', stats.get('likes', 0))))
            
            # Дата публикации (может быть в секундах или миллисекундах)
            create_time = video_data.get('createTime', video_data.get('create_time', video_data.get('timestamp', 0)))
            if create_time and create_time > 1e10:  # Если в миллисекундах
                create_time = create_time / 1000
            
            # Хештеги
            hashtags = self.extract_hashtags(desc)
            hashtags_str = ', '.join(hashtags) if hashtags else ''
            
            return {
                'id': video_id,
                'url': video_url,
                'description': str(desc) if desc else '',
                'views': int(views) if views else 0,
                'likes': int(likes) if likes else 0,
                'date': datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S') if create_time else '',
                'timestamp': int(create_time) if create_time else 0,
                'hashtags': hashtags_str,
                'author': str(author_id)
            }
        except Exception as e:
            print(f"⚠ Ошибка парсинга видео: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def search_videos_async(self, query: str, max_results: int = 30) -> List[Dict]:
        """Асинхронный поиск видео по запросу"""
        videos = []
        
        try:
            if self.api:
                # Используем TikTokApi для поиска
                print(f"🔍 Поиск по запросу: {query}")
                
                try:
                    # Попытка использовать асинхронный метод
                    results = self.api.search.videos(query, count=max_results)
                    
                    # Конвертируем async generator в список
                    video_list = []
                    count = 0
                    async for video in results:
                        video_list.append(video)
                        count += 1
                        if count >= max_results:
                            break
                    
                    for video in video_list:
                        video_dict = self.parse_video_data(video)
                        if video_dict:
                            videos.append(video_dict)
                            
                except TypeError:
                    # Если метод синхронный, используем его напрямую
                    try:
                        results = self.api.search.videos(query, count=max_results)
                        if hasattr(results, '__iter__'):
                            for video in results:
                                video_dict = self.parse_video_data(video)
                                if video_dict:
                                    videos.append(video_dict)
                                    if len(videos) >= max_results:
                                        break
                    except Exception as e2:
                        print(f"⚠ Ошибка синхронного поиска: {e2}")
                
                await asyncio.sleep(random.uniform(2, 4))
                
            else:
                print(f"⚠ API не инициализирован для запроса: {query}")
                
        except Exception as e:
            print(f"⚠ Ошибка поиска для '{query}': {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(random.uniform(3, 5))
        
        return videos
    
    def search_videos(self, query: str, max_results: int = 30) -> List[Dict]:
        """Синхронная обертка для поиска видео"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.search_videos_async(query, max_results))
    
    def filter_by_date(self, videos: List[Dict]) -> List[Dict]:
        """Фильтрация видео по дате (последние 7 дней)"""
        filtered = []
        for video in videos:
            if video.get('timestamp') and self.is_within_7_days(video['timestamp']):
                filtered.append(video)
        return filtered
    
    async def collect_videos_async(self) -> List[Dict]:
        """Асинхронный метод сбора видео"""
        print("🚀 Начало сбора данных...")
        
        # Инициализация API если еще не выполнена
        if not self.api:
            await self.initialize_api_async()
        
        queries = self.get_search_queries()
        all_videos = []
        
        for query in queries:
            try:
                videos = await self.search_videos_async(query, max_results=30)
                all_videos.extend(videos)
                print(f"✓ Собрано {len(videos)} видео по запросу '{query}'")
            except Exception as e:
                print(f"⚠ Ошибка при обработке запроса '{query}': {e}")
                continue
        
        # Фильтрация по дате
        print(f"\n📅 Фильтрация по дате (последние 7 дней)...")
        filtered_videos = self.filter_by_date(all_videos)
        print(f"✓ После фильтрации: {len(filtered_videos)} видео")
        
        # Удаление дублей (уже обработано через seen_video_ids, но на всякий случай)
        unique_videos = {}
        for video in filtered_videos:
            video_id = video.get('id')
            if video_id and video_id not in unique_videos:
                unique_videos[video_id] = video
        
        final_videos = list(unique_videos.values())
        
        # Сортировка по просмотрам
        final_videos.sort(key=lambda x: x.get('views', 0), reverse=True)
        
        # Ограничение минимум 20 видео
        if len(final_videos) < 20:
            print(f"⚠ Собрано только {len(final_videos)} видео (требуется минимум 20)")
            print("💡 Попробуйте запустить парсер позже или увеличьте количество запросов")
        
        return final_videos
    
    def collect_videos(self) -> List[Dict]:
        """Синхронная обертка для сбора видео"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.collect_videos_async())
    
    def save_to_csv(self, videos: List[Dict], filename: str = 'результат.csv'):
        """Сохранение результатов в CSV"""
        if not videos:
            print("⚠ Нет данных для сохранения")
            return
        
        fieldnames = ['url', 'description', 'views', 'likes', 'date', 'hashtags', 'author']
        
        try:
            with open(filename, 'w', encoding='utf-8-sig', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for video in videos:
                    row = {
                        'url': video.get('url', ''),
                        'description': video.get('description', ''),
                        'views': video.get('views', 0),
                        'likes': video.get('likes', 0),
                        'date': video.get('date', ''),
                        'hashtags': video.get('hashtags', ''),
                        'author': video.get('author', '')
                    }
                    writer.writerow(row)
            
            print(f"✓ Данные сохранены в {filename}")
            print(f"✓ Всего записей: {len(videos)}")
            
        except Exception as e:
            print(f"❌ Ошибка сохранения в CSV: {e}")


def main():
    """Главная функция"""
    print("=" * 60)
    print("TikTok Parser - Сбор роликов по теме 'тушь для ресниц'")
    print("=" * 60)
    print()
    
    parser = TikTokParser()
    
    try:
        # Инициализация API
        parser.initialize_api()
        
        # Сбор видео
        videos = parser.collect_videos()
        
        if videos:
            # Сохранение в CSV
            parser.save_to_csv(videos, 'результат.csv')
            
            # Вывод статистики
            print("\n" + "=" * 60)
            print("📊 Статистика:")
            print(f"   Всего собрано уникальных видео: {len(videos)}")
            if videos:
                total_views = sum(v.get('views', 0) for v in videos)
                avg_views = total_views / len(videos) if videos else 0
                print(f"   Среднее количество просмотров: {avg_views:,.0f}")
                print(f"   Топ-3 видео по просмотрам:")
                for i, video in enumerate(videos[:3], 1):
                    print(f"   {i}. {video.get('url', 'N/A')} - {video.get('views', 0):,} просмотров")
            print("=" * 60)
        else:
            print("❌ Не удалось собрать видео")
            print("💡 Возможные причины:")
            print("   - Проблемы с подключением к TikTok API")
            print("   - Rate limits TikTok")
            print("   - Недостаточно свежих видео за последние 7 дней")
            print("   - Проблемы с обходом антибота")
            
    except KeyboardInterrupt:
        print("\n⚠ Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

