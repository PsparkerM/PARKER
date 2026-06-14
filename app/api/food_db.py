"""Поиск продуктов в реальной базе Open Food Facts (КБЖУ без галлюцинаций).

Грунтит калорийность фактическими данными из открытой базы, в отличие от
AI-оценки в /api/food. Бесплатно, без ключа. Сетевые вызовы — через urllib в
отдельном потоке (zero-dependency), с коротким таймаутом и аккуратным fallback.
"""
import asyncio
import json
import logging
import urllib.parse
import urllib.request

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.api.deps import get_current_tg_id

router = APIRouter()
logger = logging.getLogger(__name__)

_OFF_BASE = "https://world.openfoodfacts.org"
_UA = "PARKER-MiniApp/1.0 (personal nutrition assistant)"
_TIMEOUT = 6.0
_MAX_RESULTS = 10


def _num(nutriments: dict, *keys) -> float | None:
    """Достаёт первое присутствующее числовое поле из nutriments OFF."""
    for k in keys:
        v = nutriments.get(k)
        if isinstance(v, (int, float)):
            return round(float(v), 1)
        if isinstance(v, str):
            try:
                return round(float(v), 1)
            except ValueError:
                continue
    return None


def _shape(product: dict) -> dict | None:
    """OFF-продукт → компактная карточка КБЖУ на 100 г. None, если нет калорий."""
    n = product.get("nutriments") or {}
    kcal = _num(n, "energy-kcal_100g", "energy-kcal", "energy_100g")
    if kcal is None:
        return None
    name = (product.get("product_name") or product.get("generic_name") or "").strip()
    if not name:
        return None
    return {
        "name":        name[:120],
        "brand":       (product.get("brands") or "").split(",")[0].strip()[:60],
        "code":        product.get("code") or "",
        "kcal_100g":   kcal,
        "protein_100g": _num(n, "proteins_100g", "proteins") or 0.0,
        "fat_100g":     _num(n, "fat_100g", "fat") or 0.0,
        "carb_100g":    _num(n, "carbohydrates_100g", "carbohydrates") or 0.0,
        "source":      "off",
    }


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 (trusted host)
        return json.loads(resp.read().decode("utf-8"))


def _search_off(query: str) -> list[dict]:
    params = urllib.parse.urlencode({
        "search_terms": query,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": 24,
        "fields": "product_name,generic_name,brands,nutriments,code",
    })
    data = _http_get_json(f"{_OFF_BASE}/cgi/search.pl?{params}")
    out = []
    for p in data.get("products", []):
        card = _shape(p)
        if card:
            out.append(card)
        if len(out) >= _MAX_RESULTS:
            break
    return out


def _lookup_barcode(code: str) -> dict | None:
    url = f"{_OFF_BASE}/api/v2/product/{urllib.parse.quote(code)}.json?fields=product_name,generic_name,brands,nutriments,code"
    data = _http_get_json(url)
    if data.get("status") == 1 and data.get("product"):
        return _shape(data["product"])
    return None


@router.get("/api/food/search")
async def food_search(
    q: str = Query(min_length=2, max_length=100),
    tg_id: int = Depends(get_current_tg_id),
):
    """Поиск продуктов по названию в Open Food Facts."""
    try:
        products = await asyncio.to_thread(_search_off, q.strip())
        return JSONResponse({"products": products})
    except Exception:
        logger.warning("food_search failed for %r", q, exc_info=True)
        # Деградация мягкая: пустой список → фронт предложит AI-расчёт.
        return JSONResponse({"products": [], "error": "search_unavailable"})


@router.get("/api/food/barcode")
async def food_barcode(
    code: str = Query(min_length=4, max_length=20, pattern=r"^\d+$"),
    tg_id: int = Depends(get_current_tg_id),
):
    """Поиск продукта по штрихкоду (EAN/UPC) в Open Food Facts."""
    try:
        product = await asyncio.to_thread(_lookup_barcode, code.strip())
        if product:
            return JSONResponse({"product": product})
        return JSONResponse({"product": None, "error": "not_found"}, status_code=404)
    except Exception:
        logger.warning("food_barcode failed for %r", code, exc_info=True)
        return JSONResponse({"product": None, "error": "lookup_unavailable"}, status_code=502)
