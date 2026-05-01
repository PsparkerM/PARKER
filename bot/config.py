import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
WEBAPP_URL: str = os.getenv("WEBAPP_URL", "")
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")
ADMIN_SECRET:           str = os.getenv("ADMIN_SECRET", "")
WEBHOOK_SECRET_TOKEN:   str = os.getenv("WEBHOOK_SECRET_TOKEN", "")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан")
