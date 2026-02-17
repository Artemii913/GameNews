"""
GameNews — Генератор подкастов (TTS)
Озвучка текстов новостей через gTTS (Google Text-to-Speech).
Обновляет podcasts.json с путями к аудиофайлам.

Автор: GameNews Team
"""

import json
import os
import logging
from gtts import gTTS

# === НАСТРОЙКА ЛОГИРОВАНИЯ ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('generate_podcast.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('GameNews_TTS')

# === ПУТИ ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PODCASTS_JSON = os.path.join(BASE_DIR, 'podcasts.json')
TEXTS_DIR = os.path.join(BASE_DIR, 'texts')
AUDIO_DIR = os.path.join(BASE_DIR, 'audio')


def load_podcasts():
    """
    Загрузка списка подкастов из JSON.
    
    Returns:
        список подкастов или пустой список при ошибке
    """
    try:
        with open(PODCASTS_JSON, 'r', encoding='utf-8') as f:
            podcasts = json.load(f)
        logger.info(f"Загружено {len(podcasts)} подкастов из {PODCASTS_JSON}")
        return podcasts
    except FileNotFoundError:
        logger.error(f"Файл {PODCASTS_JSON} не найден! Сначала запустите rss_parser.py")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка чтения JSON: {e}")
        return []


def generate_audio(podcast):
    """
    Генерация аудиофайла из текста подкаста.
    
    Args:
        podcast: словарь с данными подкаста
    Returns:
        путь к аудиофайлу или None при ошибке
    """
    podcast_id = podcast['id']
    text_file = os.path.join(TEXTS_DIR, f'podcast_{podcast_id}.txt')
    audio_file = os.path.join(AUDIO_DIR, f'podcast_{podcast_id}.mp3')
    
    # Проверяем, есть ли уже аудио
    if os.path.exists(audio_file):
        logger.info(f"  Аудио уже существует: podcast_{podcast_id}.mp3")
        return f"audio/podcast_{podcast_id}.mp3"
    
    # Читаем текст
    try:
        if os.path.exists(text_file):
            with open(text_file, 'r', encoding='utf-8') as f:
                text = f.read().strip()
        else:
            # Формируем текст из данных подкаста
            text = f"{podcast['title']}. {podcast.get('description', '')}"
        
        if not text:
            logger.warning(f"  Пустой текст для podcast_{podcast_id}")
            return None
            
    except Exception as e:
        logger.error(f"  Ошибка чтения текста podcast_{podcast_id}: {e}")
        return None
    
    # Генерируем аудио через gTTS
    try:
        logger.info(f"  Озвучиваю: {podcast['title'][:50]}...")
        
        tts = gTTS(
            text=text,
            lang='ru',      # Русский язык
            slow=False       # Нормальная скорость
        )
        tts.save(audio_file)
        
        # Проверяем размер файла
        size_kb = os.path.getsize(audio_file) / 1024
        logger.info(f"  ✓ Сохранено: podcast_{podcast_id}.mp3 ({size_kb:.1f} KB)")
        
        return f"audio/podcast_{podcast_id}.mp3"
        
    except Exception as e:
        logger.error(f"  ✗ Ошибка озвучки podcast_{podcast_id}: {e}")
        return None


def update_podcasts_json(podcasts):
    """
    Обновление podcasts.json с путями к аудиофайлам.
    
    Args:
        podcasts: обновлённый список подкастов
    """
    with open(PODCASTS_JSON, 'w', encoding='utf-8') as f:
        json.dump(podcasts, f, ensure_ascii=False, indent=2)
    
    logger.info(f"podcasts.json обновлён")


def main():
    """
    Главная функция: озвучка всех подкастов.
    """
    logger.info("=" * 50)
    logger.info("GameNews TTS — Генерация аудио")
    logger.info("=" * 50)
    
    # Создаём папку для аудио
    os.makedirs(AUDIO_DIR, exist_ok=True)
    
    # Загружаем подкасты
    podcasts = load_podcasts()
    if not podcasts:
        logger.error("Нет подкастов для озвучки. Завершаю.")
        return
    
    # Озвучиваем каждый подкаст
    success_count = 0
    error_count = 0
    
    for podcast in podcasts:
        audio_path = generate_audio(podcast)
        if audio_path:
            podcast['audio'] = audio_path
            success_count += 1
        else:
            error_count += 1
    
    # Сохраняем обновлённый JSON
    update_podcasts_json(podcasts)
    
    # Итоги
    logger.info(f"\n{'=' * 50}")
    logger.info(f"ИТОГО: {success_count} озвучено, {error_count} ошибок")
    logger.info(f"{'=' * 50}")


# === ЗАПУСК ===
if __name__ == '__main__':
    main()
