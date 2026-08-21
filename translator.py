"""Translation and summarization module using GigaChat API."""

import asyncio
from typing import List, Dict, Optional
import config
import database

from gigachat import GigaChat

client: Optional[GigaChat] = None

# GigaChat pricing (примерно, для справки)
PRICE_INPUT_PER_1M = 0.0   # для физических лиц бесплатно
PRICE_OUTPUT_PER_1M = 0.0


def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD for token usage."""
    input_cost = (input_tokens / 1_000_000) * PRICE_INPUT_PER_1M
    output_cost = (output_tokens / 1_000_000) * PRICE_OUTPUT_PER_1M
    return input_cost + output_cost


def get_client() -> GigaChat:
    """Get or create GigaChat client."""
    global client
    if client is None:
        client = GigaChat(
            credentials=config.GIGACHAT_CREDENTIALS,
            scope="GIGACHAT_API_PERS",
            verify_ssl_certs=False,
            model="GigaChat"
        )
    return client


async def translate_and_summarize(news_item: Dict) -> Dict:
    """Translate title and create a brief Russian summary."""

    if not config.GIGACHAT_CREDENTIALS:
        return news_item

    title = news_item.get("title", "")
    description = news_item.get("description", "")

    prompt = f"""Переведи заголовок новости на русский язык и напиши краткое описание (1-2 предложения) на русском.

Заголовок: {title}

Описание (если есть): {description}

Формат ответа:
Заголовок: [переведённый заголовок]
Описание: [краткое описание на русском, 1-2 предложения]"""

    try:
        gigachat_client = get_client()

        response = await asyncio.to_thread(
            gigachat_client.chat,
            prompt
        )

        result = response.choices[0].message.content.strip()

        input_tokens = len(prompt.split()) * 2
        output_tokens = len(result.split()) * 2
        cost = calculate_cost(input_tokens, output_tokens)
        await database.log_token_usage(input_tokens, output_tokens, cost)

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
        print(f"Translation error for '{title[:50]}...': {e}")
        return {
            **news_item,
            "title_ru": title,
            "description_ru": description,
            "title_original": title,
        }


async def translate_batch(news_items: List[Dict], batch_size: int = 5) -> List[Dict]:
    """Translate a batch of news items with rate limiting."""
    translated = []

    for i in range(0, len(news_items), batch_size):
        batch = news_items[i:i + batch_size]
        tasks = [translate_and_summarize(item) for item in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, dict):
                translated.append(result)
            elif isinstance(result, Exception):
                print(f"Translation batch error: {result}")

        if i + batch_size < len(news_items):
            await asyncio.sleep(0.5)

    return translated
