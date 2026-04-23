import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
WEBAPP_URL: str = os.getenv("WEBAPP_URL", "")
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан")

# VIP users — lifetime free access, no monetization restrictions
VIP_USER_IDS: set[int] = {
    6135518022,  # Петр (admin)
    1199979214,  # Лера — Свобода попугаям
    923353879,   # Вика — АгроКиса
    494349908,   # Артём — Кабанчик
    1635982841,  # Аник — Ануарчик
}
