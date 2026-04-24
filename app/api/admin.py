import hmac
import html as _html
import json
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from db.queries import get_all_users, set_user_status
from bot.config import VIP_USER_IDS, ADMIN_SECRET

router = APIRouter()

ADMIN_ID = 6135518022

GOAL_MAP = {
    "lose_weight": "🔥 Похудение",
    "gain_muscle": "💪 Набор массы",
    "maintain": "⚖️ Поддержание",
    "recomposition": "🔄 Рекомпозиция",
}

STATUS_BADGE = {
    "vip":  ('<span class="badge bvip">👑 VIP</span>', "#f5c518"),
    "pro":  ('<span class="badge bpro">💎 PRO</span>', "#a78bfa"),
    "free": ('<span class="badge bfree">⚡ Free</span>', "#6b6b88"),
}


def _check_admin(request: Request) -> bool:
    if ADMIN_SECRET:
        secret = request.query_params.get("secret", "")
        return hmac.compare_digest(secret, ADMIN_SECRET)
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


def _resolve_status(u: dict) -> str:
    db_status = u.get("status") or ""
    if db_status in ("vip", "pro", "free"):
        return db_status
    if u.get("tg_id") in VIP_USER_IDS:
        return "vip"
    return "free"


@router.get("/admin/users", response_class=JSONResponse)
async def admin_users_json(request: Request):
    if not _check_admin(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    users = get_all_users()
    return JSONResponse({"users": users, "total": len(users)})


@router.post("/admin/set-status")
async def admin_set_status(request: Request):
    if not _check_admin(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    tg_id = payload.get("tg_id")
    status = payload.get("status")
    if not tg_id or status not in ("free", "pro", "vip"):
        return JSONResponse({"error": "bad params"}, status_code=400)
    ok = set_user_status(int(tg_id), status)
    return JSONResponse({"ok": ok})


@router.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    if not _check_admin(request):
        return HTMLResponse("<h2>403 Forbidden</h2>", status_code=403)

    users = get_all_users()
    auth = _auth_param(request)

    total = len(users)
    vip_count = sum(1 for u in users if _resolve_status(u) == "vip")
    pro_count = sum(1 for u in users if _resolve_status(u) == "pro")
    free_count = sum(1 for u in users if _resolve_status(u) == "free")

    from datetime import datetime, timezone, timedelta
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    new_week = sum(1 for u in users if (u.get("created_at") or "") >= week_ago)

    rows = ""
    modals = ""
    for u in users:
        status = _resolve_status(u)
        badge_html, _ = STATUS_BADGE.get(status, STATUS_BADGE["free"])
        goal_raw = u.get("goal", "")
        goal = GOAL_MAP.get(goal_raw, _html.escape(str(goal_raw)) if goal_raw else "—")
        name = _html.escape(str(u.get("name") or "—"))
        gender_raw = u.get("gender", "")
        gender = "♀ Жен" if gender_raw == "female" else ("♂ Муж" if gender_raw == "male" else "—")
        tg_id_val = str(u.get("tg_id", ""))
        tg_id_disp = _html.escape(tg_id_val)
        uid = _html.escape(str(u.get("id", "—")))
        age = _html.escape(str(u.get("age", "—")))
        weight = _html.escape(str(u.get("weight_kg", "—")))
        height = _html.escape(str(u.get("height_cm", "—")))
        created = _html.escape(str(u.get("created_at", "—"))[:10])
        health = _html.escape(", ".join(u.get("health_issues") or []) or "—")
        equipment = _html.escape(", ".join(u.get("equipment") or []) or "—")
        bf = _html.escape(str(u.get("body_fat_pct") or "—"))
        waist = _html.escape(str(u.get("waist_cm") or "—"))
        hips = _html.escape(str(u.get("hips_cm") or "—"))
        chest = _html.escape(str(u.get("chest_cm") or "—"))
        thigh = _html.escape(str(u.get("thigh_cm") or "—"))

        modal_id = f"m{tg_id_val}"

        rows += f"""
        <tr onclick="showModal('{modal_id}')" style="cursor:pointer">
          <td><code class="cpytg" onclick="copyTg(event,'{tg_id_disp}')">{tg_id_disp}</code></td>
          <td>{uid[:8]}…</td>
          <td><b>{name}</b></td>
          <td>{badge_html}</td>
          <td>{goal}</td>
          <td>{gender}</td>
          <td>{age}</td>
          <td>{weight} кг / {height} см</td>
          <td>{created}</td>
          <td onclick="event.stopPropagation()">
            <div class="sbtn-group">
              <button class="sbtn {'sact' if status=='free' else ''}" onclick="setStatus('{tg_id_disp}','free',this)">⚡</button>
              <button class="sbtn {'sact' if status=='pro' else ''}" onclick="setStatus('{tg_id_disp}','pro',this)">💎</button>
              <button class="sbtn {'sact' if status=='vip' else ''}" onclick="setStatus('{tg_id_disp}','vip',this)">👑</button>
            </div>
          </td>
        </tr>"""

        modals += f"""
        <div class="modal" id="{modal_id}" onclick="closeModal(this)">
          <div class="mbox" onclick="event.stopPropagation()">
            <div class="mhdr">
              <span>{name} {badge_html}</span>
              <button class="mclose" onclick="closeModal(document.getElementById('{modal_id}'))">✕</button>
            </div>
            <div class="mgrid">
              <div class="mrow"><span class="mk">TG ID</span><span class="mv cp" onclick="copyText('{tg_id_disp}')">{tg_id_disp} 📋</span></div>
              <div class="mrow"><span class="mk">UUID</span><span class="mv mono">{uid}</span></div>
              <div class="mrow"><span class="mk">Имя</span><span class="mv">{name}</span></div>
              <div class="mrow"><span class="mk">Пол</span><span class="mv">{gender}</span></div>
              <div class="mrow"><span class="mk">Возраст</span><span class="mv">{age} лет</span></div>
              <div class="mrow"><span class="mk">Рост</span><span class="mv">{height} см</span></div>
              <div class="mrow"><span class="mk">Вес</span><span class="mv">{weight} кг</span></div>
              <div class="mrow"><span class="mk">% жира</span><span class="mv">{bf}</span></div>
              <div class="mrow"><span class="mk">Талия</span><span class="mv">{waist} см</span></div>
              <div class="mrow"><span class="mk">Бёдра</span><span class="mv">{hips} см</span></div>
              <div class="mrow"><span class="mk">Грудь</span><span class="mv">{chest} см</span></div>
              <div class="mrow"><span class="mk">Бедро</span><span class="mv">{thigh} см</span></div>
              <div class="mrow"><span class="mk">Цель</span><span class="mv">{goal}</span></div>
              <div class="mrow"><span class="mk">Здоровье</span><span class="mv">{health}</span></div>
              <div class="mrow"><span class="mk">Оборудование</span><span class="mv">{equipment}</span></div>
              <div class="mrow"><span class="mk">Регистрация</span><span class="mv">{created}</span></div>
              <div class="mrow"><span class="mk">Статус</span><span class="mv">{badge_html}</span></div>
            </div>
            <div class="mfooter">
              <span style="color:#6b6b88;font-size:12px">Изменить статус:</span>
              <button class="sbtn {'sact' if status=='free' else ''}" onclick="setStatus('{tg_id_disp}','free',this)">⚡ Free</button>
              <button class="sbtn {'sact' if status=='pro' else ''}" onclick="setStatus('{tg_id_disp}','pro',this)">💎 Pro</button>
              <button class="sbtn {'sact' if status=='vip' else ''}" onclick="setStatus('{tg_id_disp}','vip',this)">👑 VIP</button>
            </div>
          </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>P.A.R.K.E.R. Admin</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#07070f;color:#e8e8f0;padding:20px;min-height:100vh}}
h1{{color:#f5c518;font-size:22px;margin-bottom:4px;letter-spacing:2px;font-weight:800}}
.sub{{color:#6b6b88;font-size:13px;margin-bottom:24px}}
.stats{{display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap}}
.sc{{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:14px 20px;min-width:110px}}
.sv{{font-size:30px;font-weight:800;color:#f5c518}}
.sl{{font-size:10px;color:#6b6b88;margin-top:4px;text-transform:uppercase;letter-spacing:.8px}}
.sc.cpro .sv{{color:#a78bfa}}
.sc.cfree .sv{{color:#6b6b88}}
.sc.cnew .sv{{color:#34d399}}
.toolbar{{display:flex;gap:10px;margin-bottom:14px;align-items:center;flex-wrap:wrap}}
.btn{{padding:9px 16px;border-radius:8px;border:1px solid rgba(245,197,24,.4);background:rgba(245,197,24,.08);color:#f5c518;font-size:13px;font-weight:600;cursor:pointer;text-decoration:none;display:inline-block}}
.btn:hover{{background:rgba(245,197,24,.15)}}
input.search{{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:#e8e8f0;padding:9px 14px;font-size:13px;width:220px;outline:none}}
input.search::placeholder{{color:#6b6b88}}
select.filter{{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:#e8e8f0;padding:9px 12px;font-size:13px;outline:none;cursor:pointer}}
.wrap{{overflow-x:auto;border-radius:14px;border:1px solid rgba(255,255,255,.07)}}
table{{width:100%;border-collapse:collapse;font-size:12px;min-width:960px}}
th{{background:rgba(245,197,24,.07);color:#f5c518;padding:11px 10px;text-align:left;font-weight:700;text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid rgba(245,197,24,.15);white-space:nowrap}}
td{{padding:11px 10px;border-bottom:1px solid rgba(255,255,255,.04);vertical-align:middle}}
tr:hover td{{background:rgba(255,255,255,.02)}}
code.cpytg{{background:rgba(255,255,255,.06);border-radius:5px;padding:2px 6px;font-size:11px;cursor:pointer;color:#7dd3fc;font-family:monospace}}
code.cpytg:hover{{background:rgba(125,211,252,.15)}}
.badge{{border-radius:20px;padding:3px 10px;font-size:11px;font-weight:700;white-space:nowrap}}
.bvip{{background:rgba(245,197,24,.15);color:#f5c518;border:1px solid rgba(245,197,24,.3)}}
.bpro{{background:rgba(167,139,250,.15);color:#a78bfa;border:1px solid rgba(167,139,250,.3)}}
.bfree{{background:rgba(107,107,136,.12);color:#9ca3af;border:1px solid rgba(107,107,136,.2)}}
.sbtn-group{{display:flex;gap:4px}}
.sbtn{{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:6px;color:#9ca3af;font-size:12px;padding:4px 8px;cursor:pointer;transition:all .2s}}
.sbtn:hover{{background:rgba(255,255,255,.12);color:#fff}}
.sbtn.sact{{background:rgba(245,197,24,.15);border-color:rgba(245,197,24,.4);color:#f5c518}}
.mono{{font-family:monospace;font-size:11px;color:#6b6b88}}
/* Modal */
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:1000;align-items:center;justify-content:center;padding:20px}}
.modal.open{{display:flex}}
.mbox{{background:#0f0f1a;border:1px solid rgba(255,255,255,.1);border-radius:18px;width:100%;max-width:480px;max-height:90vh;overflow-y:auto;padding:0}}
.mhdr{{display:flex;justify-content:space-between;align-items:center;padding:18px 20px;border-bottom:1px solid rgba(255,255,255,.07);font-size:15px;font-weight:700;gap:10px;position:sticky;top:0;background:#0f0f1a;border-radius:18px 18px 0 0}}
.mclose{{background:rgba(255,255,255,.06);border:none;color:#9ca3af;font-size:16px;border-radius:8px;width:32px;height:32px;cursor:pointer;display:flex;align-items:center;justify-content:center}}
.mclose:hover{{background:rgba(255,255,255,.12);color:#fff}}
.mgrid{{padding:16px 20px;display:flex;flex-direction:column;gap:1px}}
.mrow{{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid rgba(255,255,255,.04)}}
.mrow:last-child{{border-bottom:none}}
.mk{{color:#6b6b88;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.4px;min-width:100px}}
.mv{{color:#e8e8f0;font-size:13px;text-align:right;word-break:break-all}}
.mv.cp{{cursor:pointer;color:#7dd3fc}}
.mv.cp:hover{{text-decoration:underline}}
.mfooter{{padding:16px 20px;border-top:1px solid rgba(255,255,255,.07);display:flex;gap:8px;align-items:center;flex-wrap:wrap;background:#0f0f1a;border-radius:0 0 18px 18px;position:sticky;bottom:0}}
.toast{{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1e1e2e;border:1px solid rgba(245,197,24,.3);color:#f5c518;padding:10px 20px;border-radius:10px;font-size:13px;font-weight:600;z-index:9999;opacity:0;transition:opacity .3s;pointer-events:none}}
.toast.show{{opacity:1}}
</style>
</head>
<body>
<h1>⚡ P.A.R.K.E.R. ADMIN</h1>
<div class="sub">Панель управления · Только для администратора · <a href="/admin?{auth}" style="color:#f5c518">Обновить</a></div>

<div class="stats">
  <div class="sc"><div class="sv">{total}</div><div class="sl">Всего</div></div>
  <div class="sc"><div class="sv">{vip_count}</div><div class="sl">👑 VIP</div></div>
  <div class="sc cpro"><div class="sv">{pro_count}</div><div class="sl">💎 Pro</div></div>
  <div class="sc cfree"><div class="sv">{free_count}</div><div class="sl">⚡ Free</div></div>
  <div class="sc cnew"><div class="sv">{new_week}</div><div class="sl">За 7 дней</div></div>
</div>

<div class="toolbar">
  <input class="search" id="srch" placeholder="🔍 Поиск по имени / TG ID…" oninput="filterTable()">
  <select class="filter" id="stFilter" onchange="filterTable()">
    <option value="">Все статусы</option>
    <option value="vip">👑 VIP</option>
    <option value="pro">💎 Pro</option>
    <option value="free">⚡ Free</option>
  </select>
  <a class="btn" href="/admin/users?{auth}" target="_blank">📥 JSON</a>
</div>

<div class="wrap">
<table id="tbl">
  <thead><tr>
    <th>TG ID</th>
    <th>UUID</th>
    <th>Имя</th>
    <th>Статус</th>
    <th>Цель</th>
    <th>Пол</th>
    <th>Возраст</th>
    <th>Вес / Рост</th>
    <th>Регистрация</th>
    <th>Действие</th>
  </tr></thead>
  <tbody id="tbody">{rows if rows else '<tr><td colspan="10" style="text-align:center;padding:30px;color:#6b6b88">Нет пользователей</td></tr>'}</tbody>
</table>
</div>

{modals}

<div class="toast" id="toast"></div>

<script>
const AUTH = "{auth}";

function showToast(msg, ok=true) {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.borderColor = ok ? 'rgba(52,211,153,.4)' : 'rgba(239,68,68,.4)';
  t.style.color = ok ? '#34d399' : '#f87171';
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2200);
}}

function copyText(text) {{
  navigator.clipboard.writeText(text).then(() => showToast('Скопировано: ' + text));
}}

function copyTg(e, tg) {{
  e.stopPropagation();
  copyText(tg);
}}

function showModal(id) {{
  document.getElementById(id).classList.add('open');
}}

function closeModal(el) {{
  el.classList.remove('open');
}}

document.addEventListener('keydown', e => {{
  if(e.key === 'Escape') document.querySelectorAll('.modal.open').forEach(m => m.classList.remove('open'));
}});

async function setStatus(tgId, status, btn) {{
  const res = await fetch('/admin/set-status?' + AUTH, {{
    method: 'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{tg_id: parseInt(tgId), status}})
  }});
  const data = await res.json();
  if(data.ok) {{
    showToast('✅ Статус обновлён → ' + status);
    btn.closest('.sbtn-group, .mfooter').querySelectorAll('.sbtn').forEach(b => b.classList.remove('sact'));
    btn.classList.add('sact');
  }} else {{
    showToast('❌ Ошибка: ' + (data.error||'unknown'), false);
  }}
}}

function filterTable() {{
  const q = document.getElementById('srch').value.toLowerCase();
  const st = document.getElementById('stFilter').value.toLowerCase();
  document.querySelectorAll('#tbody tr').forEach(row => {{
    const txt = row.textContent.toLowerCase();
    const badge = row.querySelector('.badge');
    const badgeText = badge ? badge.textContent.toLowerCase() : '';
    const matchQ = !q || txt.includes(q);
    const matchSt = !st || badgeText.includes(st);
    row.style.display = (matchQ && matchSt) ? '' : 'none';
  }});
}}
</script>
</body></html>"""
    return HTMLResponse(html)
