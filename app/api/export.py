import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from aiogram.types import BufferedInputFile

from app.api.deps import get_current_tg_id
from bot.bot_instance import bot
from db.queries import get_user, get_user_logs

router = APIRouter()

# UTF-8 BOM — чтобы Excel правильно открыл кириллицу. ';' и десятичная запятая — формат RU-Excel.
_BOM = "﻿"


def _num(v) -> str:
    """Число в формате RU-Excel (десятичная запятая). Пусто, если None."""
    if v is None:
        return ""
    s = (f"{v:g}" if isinstance(v, (int, float)) else str(v))
    return s.replace(".", ",")


def _build_weight_csv(logs: dict) -> Optional[bytes]:
    rows = [r for r in (logs.get("weight_logs") or []) if r.get("weight") is not None]
    if not rows:
        return None
    rows.sort(key=lambda r: r.get("date", ""))

    lines = ["Дата;Вес (кг);Δ к прошлому (кг);Сон (ч)"]
    prev = None
    for r in rows:
        w = r.get("weight")
        delta = "" if prev is None or w is None else _num(round(w - prev, 1))
        lines.append(";".join([r.get("date", ""), _num(w), delta, _num(r.get("sleep"))]))
        prev = w

    # итоговая строка: изменение от старта к финишу
    first, last = rows[0].get("weight"), rows[-1].get("weight")
    if first is not None and last is not None:
        lines.append("")
        lines.append(f"Изменение;{_num(round(last - first, 1))};кг")

    text = _BOM + "\r\n".join(lines) + "\r\n"
    return text.encode("utf-8")


@router.post("/api/export/weight")
async def export_weight(tg_id: int = Depends(get_current_tg_id)):
    """Собирает историю веса в CSV (открывается в Excel) и присылает файл в бота."""
    user = await asyncio.to_thread(get_user, tg_id)
    if not user:
        return JSONResponse({"ok": False, "error": "Пользователь не найден"}, status_code=404)

    logs = await asyncio.to_thread(get_user_logs, user["id"])
    csv_bytes = _build_weight_csv(logs or {})
    if not csv_bytes:
        return JSONResponse({"ok": False, "error": "Нет данных о весе для экспорта"})

    try:
        doc = BufferedInputFile(csv_bytes, filename="istoriya_vesa.csv")
        await bot.send_document(
            chat_id=tg_id,
            document=doc,
            caption="📋 История веса — открой в Excel / Google Sheets",
        )
        return JSONResponse({"ok": True})
    except Exception as e:
        logging.warning("export_weight send failed tg_id=%s: %s", tg_id, e)
        return JSONResponse({"ok": False, "error": "Не удалось отправить файл — открой бота и попробуй снова"})
