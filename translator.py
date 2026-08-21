"""Translation and summarization module using OpenAI API (ZvenoAI)."""

import asyncio
from typing import List, Dict
from openai import AsyncOpenAI
import config
import database

client = None

def get_client() -> AsyncOpenAI:
    global client
    if client is None:
        client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL or "https://api.openai.com/v1"
        )
    return client

async def translate_and_summarize(news_item: Dict) -> Dict:
    if not config.OPENAI_API_KEY:
        return news_item

    title = news_item.get("title", "")
    description = news_item.get("description", "")

    prompt = f"""Переведи заголовок новости на русский язык и напиши краткое описание (1-2 предложения) на русском.

Заголовок: {title}
Описание: {description}

Формат ответа:
Заголовок: [переведённый заголовок]
Описание: [краткое описание]"""

    try:
        client = get_client()
        response = await client.chat.completions.create(
            model="deepseek/deepseek-r1",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3
        )

        result = response.choices[0].message.content.strip()
        lines = result.split("\n")
        translated_title = title
        translated_description = description

        for line in lines:
            if line.startswith("Заголовок:"):
                translated_title = line.replace("Заголовок:", "").strip()
            elif line.startswith("Описание:"):
                translated_description = line.replace("Описание:", "").strip()

        return {
            **news_item,
            "title_ru": translated_title,
            "description_ru": translated_description,
            "title_original": title,
        }

    except Exception as e:
        print(f"Translation error: {e}")
        return news_item

async def translate_batch(news_items: List[Dict], batch_size: int = 5) -> List[Dict]:
    translated = []
    for i in range(0, len(news_items), batch_size):
        batch = news_items[i:i + batch_size]
        tasks = [translate_and_summarize(item) for item in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, dict):
                translated.append(result)
        await asyncio.sleep(0.5)
    return translated