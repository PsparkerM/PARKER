import hmac
import html as _html
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from db.queries import get_all_users
from bot.config import VIP_USER_IDS, ADMIN_SECRET

router = APIRouter()

ADMIN_ID = 6135518022

GOAL_MAP = {
    "lose_weight": "🔥 Похудение",
    "gain_muscle": "💪 Набор массы",
    "maintain": "⚖️ Поддержание",
    "recomposition": "🔄 Рекомпозиция",
}


def _check_admin(request: Request) -> bool:
    if ADMIN_SECRET:
        secret = request.query_params.get("secret", "")
        return hmac.compare_digest(secret, ADMIN_SECRET)
    # fallback when ADMIN_SECRET not configured — less secure
    tg_id = request.query_params.get("tg_id", "")
    try:
        return int(tg_id) == ADMIN_ID
    except (ValueError, TypeError):
        return False


def _auth_param(request: Request) -> str:
    if ADMIN_SECRET:
        secret = request.query_params.get("secret", "")
        return f"secret={_html.escape(secret)}"
    return f"tg_id={ADMIN_ID}"


@router.get("/admin/users", response_class=JSONResponse)
async def admin_users(request: Request):
    if not _check_admin(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    users = get_all_users()
    return JSONResponse({"users": users, "total": len(users)})


@router.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    if not _check_admin(request):
        return HTMLResponse("<h2>403 Forbidden</h2>", status_code=403)

    users = get_all_users()

    rows = ""
    for u in users:
        vip = "👑" if u.get("tg_id") in VIP_USER_IDS else ""
        goal_raw = u.get("goal", "")
        goal = GOAL_MAP.get(goal_raw, _html.escape(str(goal_raw)) if goal_raw else "—")
        name = _html.escape(str(u.get("name") or "—"))
        gender = _html.escape(str(u.get("gender") or "—"))
        schedule = _html.escape(str(u.get("schedule") or "—"))
        health = _html.escape(", ".join(u.get("health_issues") or []) or "—")
        tg_id_disp = _html.escape(str(u.get("tg_id", "—")))
        age = _html.escape(str(u.get("age", "—")))
        weight = _html.escape(str(u.get("weight_kg", "—")))
        height = _html.escape(str(u.get("height_cm", "—")))
        created = _html.escape(str(u.get("created_at", "—"))[:10])
        rows += f"""
        <tr>
          <td>{vip} {tg_id_disp}</td>
          <td>{name}</td>
          <td>{goal}</td>
          <td>{gender}</td>
          <td>{age}</td>
          <td>{weight} кг</td>
          <td>{height} см</td>
          <td>{schedule}</td>
          <td>{health}</td>
          <td>{created}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>P.A.R.K.E.R. Admin</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,sans-serif;background:#070710;color:#e8e8f0;padding:20px}}
h1{{color:#f5c518;font-size:22px;margin-bottom:6px;letter-spacing:2px}}
.sub{{color:#6b6b88;font-size:13px;margin-bottom:20px}}
.stat{{display:flex;gap:16px;margin-bottom:20px;flex-wrap:wrap}}
.sc{{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:14px 20px;min-width:120px}}
.sv{{font-size:28px;font-weight:700;color:#f5c518}}
.sl{{font-size:11px;color:#6b6b88;margin-top:3px;text-transform:uppercase;letter-spacing:.5px}}
table{{width:100%;border-collapse:collapse;font-size:12px;min-width:900px}}
th{{background:rgba(245,197,24,.1);color:#f5c518;padding:10px 8px;text-align:left;font-weight:700;
  text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid rgba(245,197,24,.2)}}
td{{padding:10px 8px;border-bottom:1px solid rgba(255,255,255,.05);vertical-align:top}}
tr:hover td{{background:rgba(255,255,255,.03)}}
.wrap{{overflow-x:auto;border-radius:12px;border:1px solid rgba(255,255,255,.08)}}
.refresh{{padding:9px 18px;border-radius:8px;border:1px solid rgba(245,197,24,.4);
  background:rgba(245,197,24,.1);color:#f5c518;font-size:13px;font-weight:600;cursor:pointer;
  text-decoration:none;display:inline-block;margin-bottom:16px}}
</style>
</head>
<body>
<h1>P.A.R.K.E.R. ADMIN</h1>
<div class="sub">Панель управления · Только для администратора</div>
<div class="stat">
  <div class="sc"><div class="sv">{len(users)}</div><div class="sl">Пользователей</div></div>
  <div class="sc"><div class="sv">{sum(1 for u in users if u.get('tg_id') in VIP_USER_IDS)}</div><div class="sl">VIP</div></div>
</div>
<a class="refresh" href="/admin?{_auth_param(request)}">⟳ Обновить</a>
<div class="wrap">
<table>
  <thead><tr>
    <th>TG ID</th><th>Имя</th><th>Цель</th><th>Пол</th><th>Возраст</th>
    <th>Вес</th><th>Рост</th><th>График</th><th>Здоровье</th><th>Дата</th>
  </tr></thead>
  <tbody>{rows if rows else '<tr><td colspan="10" style="text-align:center;padding:30px;color:#6b6b88">Нет пользователей</td></tr>'}</tbody>
</table>
</div>
</body></html>"""
    return HTMLResponse(html)
