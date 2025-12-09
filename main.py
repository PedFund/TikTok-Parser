import re
import time
import pandas as pd
from datetime import datetime
from playwright.sync_api import sync_playwright

# --- НАСТРОЙКИ ---
KEYWORDS = ["тушь для ресниц", "стойкая тушь", "объемная тушь"]
HASHTAGS = ["#тушь", "#ресницы", "#макияж"]
TARGET_COUNT = 20  # Сколько видео собрать (не ставь больше 30, чтобы не забанили)
OUTPUT_FILE = "tiktok_mascara_results.csv"


def get_video_details(page, url):
    """Заходит внутрь видео и собирает точные данные"""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Ждем загрузки основных элементов (лайков или комментов)
        # data-e2e - самые надежные селекторы в ТикТоке
        try:
            page.wait_for_selector('[data-e2e="like-count"]', timeout=5000)
        except:
            pass  # Если не дождались, пробуем собрать так

        # 1. Лайки
        likes = "0"
        if page.locator('[data-e2e="like-count"]').count() > 0:
            likes = page.locator('[data-e2e="like-count"]').inner_text()

        # 2. Комментарии (для массовки, раз уж зашли)
        comments = "0"
        if page.locator('[data-e2e="comment-count"]').count() > 0:
            comments = page.locator('[data-e2e="comment-count"]').inner_text()

        # 3. Дата (она внутри видео точная!)
        # Селектор даты бывает разным, ищем элемент с датой
        date_pub = datetime.now().strftime('%Y-%m-%d')
        date_el = page.locator('[data-e2e="browser-nickname"] span:last-child')
        # Иногда дата лежит просто текстом рядом с ником.
        # Попробуем найти через текст, похожий на дату (например 2023-...)

        # Простой вариант: берем дату из метаданных видео (часто надежнее)
        # Но для простоты оставим дату сбора, если не найдем точный элемент.
        # Попытка найти элемент времени:
        if page.locator('[data-e2e="browser-nickname"] + span').count() > 0:
            date_text = page.locator('[data-e2e="browser-nickname"] + span').inner_text()
            # Если там есть цифры, берем
            if any(char.isdigit() for char in date_text):
                date_pub = date_text

        # 4. Описание и Хештеги
        desc = ""
        if page.locator('[data-e2e="browse-video-desc"]').count() > 0:
            desc = page.locator('[data-e2e="browse-video-desc"]').inner_text()

        hashtags = ", ".join(re.findall(r"#\w+", desc))

        return {
            "Likes": likes,
            "Comments": comments,
            "Description": desc.replace("\n", " ")[:150],
            "Hashtags": hashtags,
            "Real_Date": date_pub
        }

    except Exception as e:
        print(f"⚠️ Ошибка внутри видео {url}: {e}")
        return None


def run():
    collected_links = set()
    final_data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        # ЭТАП 1: Сбор ссылок (БЫСТРО)
        print("--- ЭТАП 1: Сбор ссылок из поиска ---")
        search_queries = KEYWORDS + HASHTAGS

        for query in search_queries:
            if len(collected_links) >= TARGET_COUNT: break

            print(f"🔎 Ищу: {query}")
            try:
                page.goto(f"https://www.tiktok.com/search?q={query}", wait_until="domcontentloaded")
                time.sleep(2)

                # Скроллим пару раз
                page.mouse.wheel(0, 2000)
                time.sleep(2)

                # Собираем ссылки
                links = page.locator('a[href*="/video/"]').all()
                for link in links:
                    url = link.get_attribute('href')
                    if url and url not in collected_links:
                        collected_links.add(url)
                        print(f"🔗 Найдена ссылка: {url[-20:]}...")
                        if len(collected_links) >= TARGET_COUNT: break
            except Exception as e:
                print(f"Ошибка поиска: {e}")
                continue

        print(f"\n--- ЭТАП 2: Обход {len(collected_links)} видео (ДЕТАЛЬНО) ---")
        print("Это займет время, так как мы заходим в каждое видео...")

        # ЭТАП 2: Заход в каждое видео (МЕДЛЕННО, НО ТОЧНО)
        for i, url in enumerate(collected_links):
            print(f"[{i + 1}/{len(collected_links)}] Обрабатываю: {url}")

            details = get_video_details(page, url)

            if details:
                entry = {
                    "Link": url,
                    "Description": details["Description"],
                    "Likes": details["Likes"],  # Теперь тут точные лайки!
                    "Comments": details["Comments"],  # Бонусом комменты
                    "Date": details["Real_Date"],  # Попытка точной даты
                    "Hashtags": details["Hashtags"]
                }
                final_data.append(entry)
                print(f"✅ Успех: {details['Likes']} лайков")

            # Пауза, чтобы ТикТок не подумал, что мы робот
            time.sleep(2)

        browser.close()

    # Сохранение
    if final_data:
        df = pd.DataFrame(final_data)
        df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
        print(f"\n🎉 ГОТОВО! Файл сохранен: {OUTPUT_FILE}")
    else:
        print("\n😔 Не удалось собрать данные.")


if __name__ == "__main__":
    run()