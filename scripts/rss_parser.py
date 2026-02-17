"""
GameNews — RSS Parser
Сбор игровых новостей из RSS-источников.
Категории: Турниры, Релизы, Обзоры

Источники:
- StopGame.ru (новости, обзоры)
- GoHa.ru (киберспорт, MMO)
- Cyber.Sports.ru (киберспорт)

Автор: GameNews Team
"""

import feedparser
import json
import os
import re
import logging
from datetime import datetime, timedelta
from html import unescape

# === НАСТРОЙКА ЛОГИРОВАНИЯ ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('rss_parser.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('GameNews_RSS')

# === КОНФИГУРАЦИЯ RSS-ИСТОЧНИКОВ ===
# Каждый источник привязан к категории
RSS_FEEDS = {
    "Турниры": [
        {
            "name": "Cyber.Sports.ru",
            "url": "https://cyber.sports.ru/rss/main.xml",
            "priority": 1
        },
        {
            "name": "GoHa.ru - Киберспорт",
            "url": "https://www.goha.ru/rss/:Киберспорт",
            "priority": 2
        },
    ],
    "Релизы": [
        {
            "name": "StopGame - Новости",
            "url": "https://rss.stopgame.ru/rss_news.xml",
            "priority": 1
        },
        {
            "name": "GoHa.ru - Общее",
            "url": "https://www.goha.ru/rss/",
            "priority": 2
        },
    ],
    "Обзоры": [
        {
            "name": "StopGame - Обзоры",
            "url": "https://rss.stopgame.ru/rss_review.xml",
            "priority": 1
        },
        {
            "name": "StopGame - Превью",
            "url": "https://rss.stopgame.ru/rss_preview.xml",
            "priority": 2
        },
    ],
}

# Максимум новостей на категорию
MAX_NEWS_PER_CATEGORY = 5

# Папка для результатов
OUTPUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def clean_html(text):
    """
    Очистка HTML-тегов из текста.
    
    Args:
        text: строка с возможными HTML-тегами
    Returns:
        чистый текст без тегов
    """
    if not text:
        return ""
    # Убираем HTML-теги
    clean = re.sub(r'<[^>]+>', '', text)
    # Декодируем HTML-сущности
    clean = unescape(clean)
    # Убираем лишние пробелы
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def truncate_text(text, max_length=500):
    """
    Обрезка текста до заданной длины с сохранением целых слов.
    
    Args:
        text: исходный текст
        max_length: максимальная длина
    Returns:
        обрезанный текст
    """
    if len(text) <= max_length:
        return text
    truncated = text[:max_length].rsplit(' ', 1)[0]
    return truncated + '...'


def extract_image(entry):
    """
    Извлечение URL картинки из RSS-записи.
    Проверяет: media:content, enclosure, описание.
    
    Args:
        entry: объект записи feedparser
    Returns:
        URL картинки или пустая строка
    """
    # media:content
    if hasattr(entry, 'media_content') and entry.media_content:
        for media in entry.media_content:
            if 'image' in media.get('type', ''):
                return media.get('url', '')

    # media:thumbnail
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url', '')

    # enclosure
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if 'image' in enc.get('type', ''):
                return enc.get('href', '')

    # Ищем картинку в описании
    if hasattr(entry, 'summary'):
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', entry.summary)
        if img_match:
            return img_match.group(1)

    return ""


def parse_date(entry):
    """
    Извлечение и форматирование даты публикации.
    
    Args:
        entry: объект записи feedparser
    Returns:
        дата в формате YYYY-MM-DD
    """
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        try:
            dt = datetime(*entry.published_parsed[:6])
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass

    if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        try:
            dt = datetime(*entry.updated_parsed[:6])
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass

    return datetime.now().strftime('%Y-%m-%d')


def fetch_feed(feed_config):
    """
    Загрузка и парсинг одного RSS-фида.
    
    Args:
        feed_config: словарь с name, url, priority
    Returns:
        список новостей [{title, description, link, image, date, source}]
    """
    url = feed_config['url']
    name = feed_config['name']
    
    logger.info(f"Загружаю RSS: {name} ({url})")
    
    try:
        feed = feedparser.parse(url)
        
        if feed.bozo and not feed.entries:
            logger.warning(f"Ошибка парсинга {name}: {feed.bozo_exception}")
            return []
        
        news = []
        for entry in feed.entries[:MAX_NEWS_PER_CATEGORY * 2]:  # берём с запасом
            title = clean_html(entry.get('title', ''))
            if not title:
                continue
                
            description = clean_html(
                entry.get('summary', entry.get('description', ''))
            )
            description = truncate_text(description)
            
            news_item = {
                "title": title,
                "description": description,
                "link": entry.get('link', ''),
                "image": extract_image(entry),
                "date": parse_date(entry),
                "source": name
            }
            news.append(news_item)
        
        logger.info(f"  → {name}: получено {len(news)} новостей")
        return news
        
    except Exception as e:
        logger.error(f"Ошибка загрузки {name}: {e}")
        return []


def remove_duplicates(news_list):
    """
    Удаление дубликатов по заголовку (нечёткое сравнение).
    
    Args:
        news_list: список новостей
    Returns:
        список без дубликатов
    """
    seen_titles = set()
    unique = []
    
    for item in news_list:
        # Нормализуем заголовок для сравнения
        normalized = item['title'].lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        
        if normalized not in seen_titles:
            seen_titles.add(normalized)
            unique.append(item)
    
    return unique


def collect_all_news():
    """
    Главная функция: сбор новостей из всех категорий.
    
    Returns:
        список всех подкастов [{id, title, category, date, image, audio, description}]
    """
    logger.info("=" * 50)
    logger.info("GameNews RSS — Начало сбора новостей")
    logger.info("=" * 50)
    
    all_podcasts = []
    podcast_id = 1
    
    for category, feeds in RSS_FEEDS.items():
        logger.info(f"\n--- Категория: {category} ---")
        category_news = []
        
        # Собираем новости из всех источников категории
        for feed_config in feeds:
            news = fetch_feed(feed_config)
            category_news.extend(news)
        
        # Убираем дубликаты
        category_news = remove_duplicates(category_news)
        
        # Сортируем по дате (свежие первыми)
        category_news.sort(key=lambda x: x['date'], reverse=True)
        
        # Берём только нужное количество
        category_news = category_news[:MAX_NEWS_PER_CATEGORY]
        
        # Формируем подкаст-записи
        for item in category_news:
            podcast = {
                "id": podcast_id,
                "title": item['title'],
                "category": category,
                "date": item['date'],
                "image": item['image'],
                "audio": "",  # Заполнится после озвучки
                "description": item['description'],
                "source": item['source'],
                "link": item['link']
            }
            all_podcasts.append(podcast)
            podcast_id += 1
        
        logger.info(f"  Итого {category}: {len(category_news)} новостей")
    
    logger.info(f"\n{'=' * 50}")
    logger.info(f"ИТОГО: {len(all_podcasts)} подкастов собрано")
    logger.info(f"{'=' * 50}")
    
    return all_podcasts


def save_podcasts(podcasts):
    """
    Сохранение подкастов в JSON-файл.
    
    Args:
        podcasts: список подкастов
    """
    output_path = os.path.join(OUTPUT_DIR, 'podcasts.json')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(podcasts, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Сохранено в {output_path}")


def save_texts_for_tts(podcasts):
    """
    Сохранение текстов для озвучки (TTS).
    Каждый текст — это заголовок + описание подкаста.
    
    Args:
        podcasts: список подкастов
    """
    texts_dir = os.path.join(OUTPUT_DIR, 'texts')
    os.makedirs(texts_dir, exist_ok=True)
    
    for podcast in podcasts:
        text = f"{podcast['title']}. {podcast['description']}"
        filename = f"podcast_{podcast['id']}.txt"
        filepath = os.path.join(texts_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
    
    logger.info(f"Тексты для озвучки сохранены в {texts_dir}/")


# === ЗАПУСК ===
if __name__ == '__main__':
    podcasts = collect_all_news()
    save_podcasts(podcasts)
    save_texts_for_tts(podcasts)
    logger.info("Готово!")
