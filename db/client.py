import logging
from bot.config import SUPABASE_URL, SUPABASE_SERVICE_KEY

_client = None


def get_client():
    global _client
    if _client is not None:
        return _client
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logging.warning("Supabase не настроен — данные не сохраняются")
        return None
    try:
        from supabase import create_client
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        logging.info("Supabase подключён")
        return _client
    except Exception:
        logging.exception("Supabase ошибка подключения")
        return None
