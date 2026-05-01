"""
Structured security logging and anomaly detection middleware.

All security events are emitted to the 'parker.security' logger as JSON lines.
Railway captures stdout, so these appear in the Railway log viewer and can be
piped to any external log aggregation tool (Datadog, Grafana Loki, etc.).

Anomaly thresholds (tunable at top of file):
- SUSPICIOUS_IP : > 20 auth errors (401/403) from one IP in 5 min
- TRAFFIC_SPIKE : > 300 requests from one IP in 5 min
"""
import json
import logging
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_sec = logging.getLogger("parker.security")

# ── Anomaly detection thresholds ───────────────────────────────────────────
_AUTH_ERROR_LIMIT  = 20   # 401/403 count per IP per window → SUSPICIOUS_IP
_TRAFFIC_LIMIT     = 300  # total requests per IP per window → TRAFFIC_SPIKE
_WINDOW_SEC        = 300  # 5-minute sliding window
_ALERT_COOLDOWN    = 300  # min seconds between repeated alerts for same IP

# ── Per-IP sliding windows ─────────────────────────────────────────────────
_err_win:  dict[str, deque] = defaultdict(deque)   # 401/403 timestamps
_req_win:  dict[str, deque] = defaultdict(deque)   # all-request timestamps
_alerted:  dict[str, float] = {}                   # ip -> last alert monotonic ts


def _get_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (
        request.client.host if request.client else "unknown"
    )


def _slide(dq: deque, now: float) -> None:
    cutoff = now - _WINDOW_SEC
    while dq and dq[0] < cutoff:
        dq.popleft()


def _should_alert(ip: str, now: float) -> bool:
    last = _alerted.get(ip, 0.0)
    if now - last >= _ALERT_COOLDOWN:
        _alerted[ip] = now
        return True
    return False


def log_security_event(event: str, **fields) -> None:
    """Emit a structured JSON security event. Import this in other modules."""
    _sec.warning(json.dumps({"event": event, **fields}, ensure_ascii=False))


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start  = time.monotonic()
        ip     = _get_ip(request)
        path   = request.url.path
        method = request.method

        response = await call_next(request)

        status      = response.status_code
        duration_ms = round((time.monotonic() - start) * 1000)
        now         = time.monotonic()

        # ── traffic spike detection ────────────────────────────────────────
        rw = _req_win[ip]
        _slide(rw, now)
        rw.append(now)
        if len(rw) >= _TRAFFIC_LIMIT and _should_alert(f"spike:{ip}", now):
            log_security_event(
                "TRAFFIC_SPIKE",
                ip=ip,
                requests=len(rw),
                window_sec=_WINDOW_SEC,
            )

        # ── log all 4xx / 5xx ─────────────────────────────────────────────
        if status >= 400:
            level = logging.ERROR if status >= 500 else logging.WARNING
            _sec.log(level, json.dumps({
                "event":       "HTTP_ERROR",
                "status":      status,
                "method":      method,
                "path":        path,
                "ip":          ip,
                "duration_ms": duration_ms,
            }))

            # ── suspicious IP: repeated auth errors ───────────────────────
            if status in (401, 403):
                ew = _err_win[ip]
                _slide(ew, now)
                ew.append(now)
                if len(ew) >= _AUTH_ERROR_LIMIT and _should_alert(f"suspicious:{ip}", now):
                    log_security_event(
                        "SUSPICIOUS_IP",
                        ip=ip,
                        auth_errors=len(ew),
                        window_sec=_WINDOW_SEC,
                        last_path=path,
                    )

        return response
