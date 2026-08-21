"""Business ideas analyzer - extracts top 3 money-making ideas from news."""

import asyncio
import json
from typing import List, Dict
from gigachat import GigaChat
import config
import database

# GigaChat pricing (бесплатно для физических лиц)
PRICE_INPUT_PER_1M = 0.0
PRICE_OUTPUT_PER_1M = 0.0


def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1_000_000) * PRICE_INPUT_PER_1M + \
           (output_tokens / 1_000_000) * PRICE_OUTPUT_PER_1M


def get_gigachat_client() -> GigaChat:
    """Get or create GigaChat client."""
    return GigaChat(
        credentials=config.GIGACHAT_CREDENTIALS,
        scope="GIGACHAT_API_PERS",
        verify_ssl_certs=False,
        model="GigaChat-3.5-Ultra"
    )


async def analyze_business_ideas(news_items: List[Dict]) -> str:
    """Analyze news and extract top 3 business ideas."""

    if not config.GIGACHAT_CREDENTIALS or not news_items:
        return None

    # Prepare news summary for analysis
    news_summary = "\n\n".join([
        f"**{item.get('title_ru', item.get('title', ''))}**\n{item.get('description_ru', item.get('description', ''))}"
        for item in news_items[:20]  # Limit to top 20 for context
    ])

    prompt = f"""Проанализируй эти AI-новости и выбери 3 самые перспективные бизнес-идеи, на которых можно заработать.

НОВОСТИ:
{news_summary}

Для каждой идеи укажи:
1. Название идеи (короткое, цепляющее)
2. Суть: что конкретно делать (2-3 предложения)
3. Почему выстрелит: почему это актуально и востребовано прямо сейчас
4. Как заработать: конкретная модель монетизации
5. Первый шаг: что сделать уже сегодня, чтобы начать

Фокусируйся на:
- Идеях, которые можно реализовать быстро (недели, не месяцы)
- Низкий порог входа (минимум вложений)
- Реальный спрос (люди готовы платить)
- Тренды, которые только набирают обороты

Формат ответа - строго JSON:
{{
  "ideas": [
    {{
      "title": "Название идеи",
      "what": "Суть идеи",
      "why": "Почему выстрелит",
      "money": "Как заработать",
      "first_step": "Первый шаг"
    }}
  ]
}}"""

    try:
        client = get_gigachat_client()

        # GigaChat не поддерживает асинхронные вызовы, используем to_thread
        response = await asyncio.to_thread(
            client.chat,
            prompt,
            model="GigaChat-3.5-Ultra"
        )

        result = response.choices[0].message.content.strip()

        # Примерный подсчет токенов (GigaChat не возвращает точное количество)
        input_tokens = len(prompt.split()) * 2
        output_tokens = len(result.split()) * 2
        cost = calculate_cost(input_tokens, output_tokens)
        await database.log_token_usage(input_tokens, output_tokens, cost)

        # Парсим JSON
        data = json.loads(result)
        return format_ideas_message(data.get("ideas", []))

    except Exception as e:
        print(f"Error analyzing business ideas: {e}")
        return None


def format_ideas_message(ideas: List[Dict]) -> str:
    """Format ideas into a Telegram message."""
    if not ideas:
        return None

    message = "💡 <b>ТОП-3 БИЗНЕС-ИДЕИ ДНЯ</b>\n\n"

    for i, idea in enumerate(ideas[:3], 1):
        message += f"{'🥇' if i == 1 else '🥈' if i == 2 else '🥉'} <b>{idea.get('title', 'Идея')}</b>\n\n"
        message += f"📌 <b>Что делать:</b>\n{idea.get('what', '')}\n\n"
        message += f"🚀 <b>Почему выстрелит:</b>\n{idea.get('why', '')}\n\n"
        message += f"💰 <b>Как заработать:</b>\n{idea.get('money', '')}\n\n"
        message += f"👉 <b>Первый шаг:</b>\n{idea.get('first_step', '')}\n\n"
        message += "━━━━━━━━━━━━━━━━━━━━\n\n"

    return message
