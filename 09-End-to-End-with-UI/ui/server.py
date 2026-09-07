#!/usr/bin/env python3
"""
ui/server.py — Python stdlib HTTP server for the governance demo portal.

Responsibilities:
  1. Serve static HTML/CSS/JS from ui/static/
  2. POST /api/auth/login     → Cognito USER_PASSWORD_AUTH, returns JWT + groups
  3. POST /api/agent/invoke   → SmartAgent router OR specialist runtime (HTTPS + JWT)
  4. GET  /api/system/status  → live state of Cognito / Gateway / Runtimes / Cedar / Guardrail
  5. GET  /api/config/public  → non-sensitive config (brand, sector, runtime list)

Run:
    python3 ui/server.py                     # port 8080
    python3 ui/server.py --port 9000         # custom port

All AWS calls use the local AWS credentials (~/.aws/credentials).
No secrets are ever returned to the browser — the JWT lives only in the
browser's sessionStorage and is POSTed back on each /api/agent/invoke call.
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import mimetypes
import os
import sys
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import boto3

# Make project root importable so local modules can be resolved cleanly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ─────────────────────────────────────────────────────────────────────────────
#  Configuration & bootstrapping
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("portal")

STATIC_DIR = Path(__file__).parent / "static"


def _find_config_env() -> Path:
    """Procura config.env subindo a partir do diretório do server.
    Funciona tanto na raiz do projeto quanto dentro da pasta de um lab."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "config.env"
        if candidate.exists():
            return candidate
    return PROJECT_ROOT / "config.env"  # fallback


CONFIG_ENV = _find_config_env()

# Routes served for "/" → index, or "/name" without extension → "name.html"
PRETTY_PAGES = {"", "login", "assistente", "governanca", "sistema", "configuracoes"}


def load_config() -> dict:
    """Parse config.env into os.environ (does not overwrite existing vars)."""
    cfg: dict[str, str] = {}
    if CONFIG_ENV.exists():
        for line in CONFIG_ENV.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    # Alias: o workshop usa chaves próprias no config.env; mapeia para os
    # nomes que este portal espera (sem sobrescrever valores já presentes).
    _aliases = {
        "GATEWAY_ID":                    "AGENTCORE_GATEWAY_ID",
        "GATEWAY_ARN":                   "AGENTCORE_GATEWAY_ARN",
        "GATEWAY_URL":                   "AGENTCORE_GATEWAY_URL",
        "POLICY_STORE_ID":               "AGENTCORE_POLICY_ENGINE_ID",
        "RUNTIME_GRID_AGENT_ARN":        "RUNTIME_GRIDMONITOR_AGENT_ARN",
        "RUNTIME_BILLING_AGENT_ARN":     "RUNTIME_CUSTOMERBILLING_AGENT_ARN",
        "RUNTIME_REGULATORY_AGENT_ARN":  "RUNTIME_REGULATORYREPORT_AGENT_ARN",
    }
    for src, dst in _aliases.items():
        if cfg.get(src) and not cfg.get(dst):
            cfg[dst] = cfg[src]
    for k, v in cfg.items():
        os.environ.setdefault(k, v)
    return cfg


CONFIG = load_config()
SECTOR = os.environ.get("DEMO_SECTOR", "utility")


# ─────────────────────────────────────────────────────────────────────────────
#  AgentCore Runtime invocation (used for SmartAgent + every specialist)
#
#  All six agents are deployed as AgentCore Runtimes with Cognito JWT auth,
#  so this portal only needs a signed HTTPS POST. The user's Bearer token
#  travels on the Authorization header end-to-end; the runtime's Cognito
#  authorizer validates it before the agent code is executed.
# ─────────────────────────────────────────────────────────────────────────────

RUNTIMES = {
    "SmartAgent":            "RUNTIME_SMART_AGENT_ARN",
    "GridMonitorAgent":      "RUNTIME_GRIDMONITOR_AGENT_ARN",
    "MaintenanceAgent":      "RUNTIME_MAINTENANCE_AGENT_ARN",
    "ContractAgent":         "RUNTIME_CONTRACT_AGENT_ARN",
    "CustomerBillingAgent":  "RUNTIME_CUSTOMERBILLING_AGENT_ARN",
    "RegulatoryReportAgent": "RUNTIME_REGULATORYREPORT_AGENT_ARN",
}


def _invoke_runtime(agent_name: str, prompt: str, user_jwt: str, session_id: str = "") -> dict:
    """POST to an AgentCore Runtime, return the parsed JSON response dict."""
    env = RUNTIMES[agent_name]
    arn = os.environ.get(env, "")
    if not arn:
        raise RuntimeError(f"{env} not configured in config.env")

    region = os.environ.get("AWS_REGION", "us-east-1")
    from urllib.parse import quote as _quote
    url = (
        f"https://bedrock-agentcore.{region}.amazonaws.com"
        f"/runtimes/{_quote(arn, safe='')}/invocations?qualifier=DEFAULT"
    )
    headers = {
        "Authorization": f"Bearer {user_jwt}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }
    if session_id:
        headers["X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"] = session_id

    import urllib.request
    import urllib.error
    req = urllib.request.Request(
        url, method="POST",
        data=json.dumps({"prompt": prompt}).encode("utf-8"),
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"response": f"[HTTP {e.code}] {body[:400]}", "agent_name": agent_name}
    except urllib.error.URLError as e:
        return {"response": f"[network] {e}", "agent_name": agent_name}

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"response": body, "agent_name": agent_name}

    if isinstance(data, dict) and "response" in data:
        return data
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    return {"response": json.dumps(data, ensure_ascii=False), "agent_name": agent_name}


# ─────────────────────────────────────────────────────────────────────────────
#  Streaming helpers for the SSE invoke endpoint
# ─────────────────────────────────────────────────────────────────────────────

def _runtime_url(agent_name: str) -> str:
    env = RUNTIMES[agent_name]
    arn = os.environ.get(env, "")
    if not arn:
        raise RuntimeError(f"{env} not configured in config.env")
    region = os.environ.get("AWS_REGION", "us-east-1")
    from urllib.parse import quote as _quote
    return (
        f"https://bedrock-agentcore.{region}.amazonaws.com"
        f"/runtimes/{_quote(arn, safe='')}/invocations?qualifier=DEFAULT"
    )


def _stream_smart_agent(prompt: str, user_jwt: str, emit, session_id: str = "", history: list = None) -> None:
    """Open the SSE stream from the SmartAgent runtime and forward each
    `data:` line to the caller via `emit(dict)`. Accumulates delegations
    from `tool_end` events so we can emit a rich `done` with the full
    governance tree."""
    import urllib.request
    headers = {
        "Authorization": f"Bearer {user_jwt}",
        "Content-Type":  "application/json",
        "Accept":        "text/event-stream",
    }
    if session_id:
        headers["X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"] = session_id
    req = urllib.request.Request(
        _runtime_url("SmartAgent"), method="POST",
        data=json.dumps({"prompt": prompt, "history": history or []}).encode("utf-8"),
        headers=headers,
    )
    delegations: list[dict] = []
    final_text:  list[str]  = []
    # When we fast-path the specialist answer (emit it as a delta right when
    # tool_end arrives), suppress the Haiku reformulation that follows.
    # The router system prompt already asks for a verbatim copy, so the
    # reformulation is almost always duplicate tokens. Skipping them makes
    # the response feel 2–3s faster to the user.
    fast_path_active = False

    with urllib.request.urlopen(req, timeout=180) as resp:
        for raw in resp:
            line = raw.decode("utf-8").rstrip()
            if not line.startswith("data: "):
                continue
            try:
                ev = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            t = ev.get("type")
            if t == "delta":
                if fast_path_active:
                    # Router is just re-emitting the specialist text; drop it.
                    continue
                final_text.append(ev.get("text", ""))
                emit({"type": "delta", "text": ev.get("text", "")})
            elif t == "tool_start":
                emit({
                    "type":       "tool_start",
                    "specialist": ev.get("specialist", "Specialist"),
                })
            elif t == "tool_end":
                specialist_text = ev.get("response", "")
                delegations.append({
                    "agent_name":      ev.get("specialist"),
                    "response":        specialist_text,
                    **(ev.get("governance") or {}),
                })
                emit({
                    "type":       "tool_end",
                    "specialist": ev.get("specialist"),
                    "governance": ev.get("governance") or {},
                })
                # Fast path: send the specialist answer to the browser now so
                # it shows immediately, and suppress the router's subsequent
                # reformulation of the same text.
                if specialist_text:
                    # If the router already emitted some text before delegating
                    # (e.g. answered a hello before the action), insert a blank
                    # line so the two parts don't visually collide.
                    if final_text and not final_text[-1].endswith(("\n", "\n\n")):
                        sep = "\n\n"
                        final_text.append(sep)
                        emit({"type": "delta", "text": sep})
                    final_text.append(specialist_text)
                    emit({"type": "delta", "text": specialist_text})
                    fast_path_active = True
            elif t == "done":
                # Runtime-side delegations may be richer (full specialist dicts)
                if ev.get("delegations"):
                    delegations = ev["delegations"]
                break

    emit({
        "type":     "done",
        "agent":    "SmartAgent",
        "session_id": session_id,
        "response": "".join(final_text),
        "governance": {
            "verdict":     _aggregate_verdict(delegations),
            "delegations": delegations,
        },
    })


def _stream_specialist(agent_name: str, prompt: str, user_jwt: str, emit, session_id: str = "") -> None:
    """Specialists still return a single JSON object. Wrap it as two SSE
    events so the browser consumer is the same for both SmartAgent and
    direct specialist invocations."""
    import urllib.request, urllib.error
    headers = {
        "Authorization": f"Bearer {user_jwt}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }
    if session_id:
        headers["X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"] = session_id
    req = urllib.request.Request(
        _runtime_url(agent_name), method="POST",
        data=json.dumps({"prompt": prompt}).encode("utf-8"),
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        emit({"type": "error", "message": f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:400]}"})
        return

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        data = {"response": body, "agent_name": agent_name}
    if isinstance(data, list) and data:
        data = data[0]

    text = data.get("response", "") if isinstance(data, dict) else str(data)
    emit({"type": "delta", "text": text})
    emit({
        "type":     "done",
        "agent":    agent_name,
        "session_id": session_id,
        "response": text,
        "governance": {
            "verdict":     data.get("cedar_verdict", "not-invoked") if isinstance(data, dict) else "unknown",
            "delegations": [data] if isinstance(data, dict) else [],
        },
    })


# ─────────────────────────────────────────────────────────────────────────────
#  Handler
# ─────────────────────────────────────────────────────────────────────────────

class PortalHandler(BaseHTTPRequestHandler):

    server_version = "AgentsGovernancePortal/1.0"

    # --- logging ------------------------------------------------------------

    def log_message(self, fmt, *args):  # noqa: N802 (stdlib name)
        log.info("%s - %s", self.address_string(), fmt % args)

    # --- helpers ------------------------------------------------------------

    def _send(self, status: int, body: bytes, content_type: str = "text/plain", extra_headers: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if content_type == "application/json" else "public, max-age=60")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: Any):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode()
        self._send(status, body, "application/json")

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON body: {e}")

    def _read_bearer_jwt(self) -> str:
        auth = self.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:]
        return ""

    # --- dispatch -----------------------------------------------------------

    def do_GET(self):  # noqa: N802
        try:
            self._route_get()
        except Exception:
            log.exception("GET %s failed", self.path)
            self._send_json(500, {"error": "internal", "detail": traceback.format_exc(limit=2)})

    def do_POST(self):  # noqa: N802
        try:
            self._route_post()
        except Exception:
            log.exception("POST %s failed", self.path)
            self._send_json(500, {"error": "internal", "detail": traceback.format_exc(limit=2)})

    # --- GET routes ---------------------------------------------------------

    def _route_get(self):
        path = urlparse(self.path).path

        # API routes
        if path == "/api/system/status":
            return self._api_system_status()
        if path == "/api/config/public":
            return self._api_config_public()
        if path == "/api/governance/metrics":
            return self._api_governance_metrics()
        if path == "/api/governance/cedar-decisions":
            return self._api_cedar_decisions()
        if path.startswith("/api/governance/trace/"):
            trace_id = path[len("/api/governance/trace/"):]
            return self._api_cedar_trace(trace_id)

        # Static files
        if path.startswith("/static/"):
            return self._serve_static(path[len("/static/"):])

        # Pretty page routing: "/" → index, "/assistente" → assistente.html
        stripped = path.lstrip("/").removesuffix("/")
        if stripped in PRETTY_PAGES:
            page = "index.html" if stripped in {"", "login"} else f"{stripped}.html"
            return self._serve_static(page, root=STATIC_DIR)

        # Explicit .html request (e.g. /assistente.html)
        if path.endswith(".html"):
            return self._serve_static(path.lstrip("/"), root=STATIC_DIR)

        self._send(404, b"404 Not Found", "text/plain")

    # --- POST routes --------------------------------------------------------

    def _route_post(self):
        path = urlparse(self.path).path

        if path == "/api/auth/login":
            return self._api_auth_login()
        if path == "/api/agent/invoke":
            return self._api_agent_invoke()

        self._send_json(404, {"error": "unknown endpoint"})

    # ─────────────────────────────────────────────────────────────────────
    #  API handlers
    # ─────────────────────────────────────────────────────────────────────

    def _api_config_public(self):
        """Non-sensitive values the front-end needs for branding/labels."""
        specialists = []
        for name, env in RUNTIMES.items():
            arn = os.environ.get(env, "")
            specialists.append({
                "name": name,
                "arn": arn,
                "configured": bool(arn),
                # Derived runtime ID (last segment of the ARN, used for log groups)
                "runtime_id": arn.split("/")[-1] if arn else "",
            })

        # Account ID from any ARN we have, fallback empty.
        account_id = ""
        for env in (*RUNTIMES.values(), "AGENTCORE_GATEWAY_ARN"):
            v = os.environ.get(env, "")
            if v.startswith("arn:") and len(v.split(":")) > 4:
                account_id = v.split(":")[4]
                break

        region = os.environ.get("AWS_REGION", "us-east-1")
        gw_id  = os.environ.get("AGENTCORE_GATEWAY_ID", "")
        # Log groups the front-end can deep-link into.
        log_groups = {
            "gateway": (
                f"/aws/vendedlogs/bedrock-agentcore/gateway/APPLICATION_LOGS/{gw_id}"
                if gw_id else ""
            ),
            "lambdas": [
                f"/aws/lambda/agents-governance-utility-{api}"
                for api in ("grid_api", "maintenance_api", "contract_api",
                            "billing_api", "regulatory_api")
            ],
            "runtimes": {
                s["name"]: f"/aws/bedrock-agentcore/runtimes/{s['runtime_id']}-DEFAULT"
                for s in specialists if s["runtime_id"]
            },
        }

        self._send_json(200, {
            "sector": SECTOR,
            "model":  os.environ.get("BEDROCK_MODEL_ID", ""),
            "gatewayUrl": os.environ.get("AGENTCORE_GATEWAY_URL", ""),
            "specialists": specialists,
            "cognitoClientId": os.environ.get("COGNITO_CLIENT_ID", ""),
            # Observability surface — used by the front-end to deep-link to
            # CloudWatch Logs Insights, X-Ray and CloudTrail consoles.
            "observability": {
                "accountId": account_id,
                "region":    region,
                "gatewayId": gw_id,
                "logGroups": log_groups,
                "cloudtrailName": os.environ.get("CLOUDTRAIL_NAME", "agents-governance-trail"),
            },
        })

    def _api_auth_login(self):
        """Cognito USER_PASSWORD_AUTH. Returns {token, groups, email}."""
        body = self._read_json()
        email    = (body.get("email") or "").strip()
        password = body.get("password") or ""
        if not email or not password:
            return self._send_json(400, {"error": "email and password are required"})

        if "@" not in email:
            email = f"{email}@demo.internal"

        client_id = os.environ.get("COGNITO_CLIENT_ID", "")
        region    = os.environ.get("AWS_REGION", "us-east-1")
        if not client_id:
            return self._send_json(500, {"error": "COGNITO_CLIENT_ID not configured"})

        cognito = boto3.client("cognito-idp", region_name=region)
        try:
            resp = cognito.initiate_auth(
                AuthFlow="USER_PASSWORD_AUTH",
                ClientId=client_id,
                AuthParameters={"USERNAME": email, "PASSWORD": password},
            )
        except cognito.exceptions.NotAuthorizedException:
            return self._send_json(401, {"error": "invalid_credentials"})
        except cognito.exceptions.UserNotFoundException:
            return self._send_json(401, {"error": "user_not_found"})
        except Exception as e:
            log.exception("Login error")
            return self._send_json(500, {"error": "cognito_error", "detail": str(e)})

        token = resp["AuthenticationResult"]["AccessToken"]
        groups = _decode_groups(token)
        # One chat session per login. AgentCore Memory requires >=33 chars,
        # so we pad the UUID. Cross-login LTM still works because the Memory
        # namespace is keyed on actor_id (the Cognito `sub`), not session_id.
        import uuid as _uuid
        session_id = (str(_uuid.uuid4()) + "-" + "0" * 40)[:64]
        self._send_json(200, {
            "token":      token,
            "groups":     groups,
            "email":      email,
            "session_id": session_id,
        })

    def _api_agent_invoke(self):
        """Invoke SmartAgent router OR a specific specialist runtime and
        stream the response back to the browser as Server-Sent Events.

        For SmartAgent: its AgentCore runtime is itself an async generator;
        we transparently pipe each `data:` line from the runtime response
        to our HTTP response. Event shapes defined in smart_agent.py:
          * delta      — {type, text}
          * tool_start — {type, tool, specialist}
          * tool_end   — {type, specialist, response, governance}
          * done       — {type, delegations, agent_name, session_id}

        For specialists: they still return a single JSON response (not
        streaming). We wrap it as a single `delta` + `done` pair so the
        frontend can use the same consumer for both paths.

        Body: {"agent": "SmartAgent"|<SpecialistName>, "prompt": str}
        Auth: Authorization: Bearer <user_jwt>
        """
        body = self._read_json()
        agent_name = body.get("agent") or "SmartAgent"
        prompt     = body.get("prompt") or ""
        jwt_token  = self._read_bearer_jwt()
        # AgentCore Memory requires a >=33-char session id. The browser sends
        # a stable per-chat UUID so Memory groups all turns under one session.
        session_id = (body.get("session_id") or "").strip()
        if session_id and len(session_id) < 33:
            session_id = (session_id + "-" + "0" * 40)[:64]
        # Specialists invoked directly (not through SmartAgent) need their own
        # sub-session to avoid tool-schema mismatches with whatever the
        # SmartAgent wrote in that same parent session.
        if agent_name != "SmartAgent" and session_id:
            session_id = (session_id + "-" + agent_name.lower())[:64]

        if not jwt_token:
            return self._send_json(401, {"error": "missing_bearer_token"})
        if not prompt.strip():
            return self._send_json(400, {"error": "empty_prompt"})
        if agent_name not in RUNTIMES:
            return self._send_json(400, {"error": f"unknown agent: {agent_name}"})

        # Open the SSE response early so the browser can start rendering.
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()

        def emit(event: dict) -> None:
            try:
                self.wfile.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                raise

        try:
            if agent_name == "SmartAgent":
                _stream_smart_agent(prompt, jwt_token, emit, session_id=session_id,
                                    history=body.get("history") or [])
            else:
                _stream_specialist(agent_name, prompt, jwt_token, emit, session_id=session_id)
        except Exception as e:
            log.exception("agent invoke stream failed")
            try:
                emit({"type": "error", "message": str(e)})
            except Exception:
                pass

    def _api_governance_metrics(self):
        """Governance analytics sourced from the native CloudWatch metrics the
        AgentCore Policy Engine publishes automatically into the
        ``AWS/Bedrock-AgentCore`` namespace.

        Returns aggregate counters, time-series and per-tool breakdowns for
        the requested window (default 24h). No derivation or custom
        instrumentation — just reads metrics AWS emits by default when Cedar
        evaluates a request.
        """
        from datetime import datetime, timedelta, timezone

        region = os.environ.get("AWS_REGION", "us-east-1")
        engine = os.environ.get("AGENTCORE_POLICY_ENGINE_ID", "")
        hours  = int(_query_param(self.path, "hours", "24"))
        now    = datetime.now(timezone.utc)
        start  = now - timedelta(hours=hours)
        period = _pick_period(hours)

        if not engine:
            return self._send_json(500, {"error": "AGENTCORE_POLICY_ENGINE_ID not set"})

        cw = boto3.client("cloudwatch", region_name=region)

        # ── 1) Policy Engine totals for the window ────────────────────────────
        #
        # NOTE: we only query metrics that are actually scoped to the
        # PolicyEngine dimension. Service-wide counters (Invocations, Latency,
        # UserErrors, SystemErrors) do NOT carry PolicyEngine — those are
        # emitted for the gateway/runtime HTTP API as a whole, not for Cedar
        # decisions — so including them here would silently return zeros.
        totals_queries = [
            _total_query("allow",    "AllowDecisions",          engine, 3600),
            _total_query("deny",     "DenyDecisions",           engine, 3600),
            _total_query("mismatch", "TotalMismatchedPolicies", engine, 3600),
        ]
        totals_resp = cw.get_metric_data(
            MetricDataQueries=totals_queries,
            StartTime=start, EndTime=now, ScanBy="TimestampAscending",
        )
        totals = {q["Id"]: _sum_or_last(q["Id"], totals_resp) for q in totals_queries}

        # ── 2) Time series for the Allow/Deny chart ───────────────────────────
        series_queries = [
            _series_query("allow_ts", "AllowDecisions", engine, period),
            _series_query("deny_ts",  "DenyDecisions",  engine, period),
        ]
        series_resp = cw.get_metric_data(
            MetricDataQueries=series_queries,
            StartTime=start, EndTime=now, ScanBy="TimestampAscending",
        )
        series = {q["Id"]: _points(q["Id"], series_resp) for q in series_queries}

        # ── 3) Top tools grouped by decision ─────────────────────────────────
        per_tool_queries = [
            _per_tool_query("allow_t", "AllowDecisions", engine, period),
            _per_tool_query("deny_t",  "DenyDecisions",  engine, period),
        ]
        tools_resp = cw.get_metric_data(
            MetricDataQueries=per_tool_queries,
            StartTime=start, EndTime=now, ScanBy="TimestampAscending",
            MaxDatapoints=10000,
        )
        # Filter to the currently active gateway so stale metrics from
        # previous gateway instances don't skew the top-N.
        current_gw = os.environ.get("AGENTCORE_GATEWAY_ID", "")
        by_tool = _aggregate_by_tool(tools_resp, current_gw)

        self._send_json(200, {
            "window": {
                "start": start.isoformat(timespec="seconds"),
                "end":   now.isoformat(timespec="seconds"),
                "hours": hours,
            },
            "engine":  engine,
            "totals":  totals,
            "series":  series,
            "by_tool": by_tool,
        })

    def _api_cedar_decisions(self):
        """Lists Cedar policy decisions from aws/spans, summarized.

        Returns one entry per Cedar span (AuthorizeAction or
        PartiallyAuthorizeActions), enriched with traceId so the front-end
        can drill down into the full trace.

        Query params:
          hours       — lookback window (default 3)
          decision    — 'allow' | 'deny' | 'all' (default 'all')

        Response:
          {
            totals: { allow: int, deny: int },
            by_tool: [{ tool, allow, deny }],
            decisions: [{
              timestamp, traceId, name, decision, tool,
              determining_policies[], allowed_tools[], denied_tools[]
            }]
          }
        """
        from urllib.parse import parse_qs
        qs = parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
        hours = max(1, min(24, int((qs.get("hours") or ["3"])[0])))
        filter_decision = (qs.get("decision") or ["all"])[0].lower()

        region = os.environ.get("AWS_REGION", "us-east-1")
        logs = boto3.client("logs", region_name=region)

        query_str = (
            "fields @timestamp, traceId, name, @message\n"
            "| filter name like /AgentCore.Policy/\n"
            "| sort @timestamp desc\n"
            "| limit 200"
        )
        end_s = int(time.time())
        start_s = end_s - hours * 3600

        try:
            qid = logs.start_query(
                logGroupName="aws/spans",
                startTime=start_s, endTime=end_s,
                queryString=query_str,
            )["queryId"]
            # Poll until done (max 15s)
            for _ in range(15):
                time.sleep(1)
                resp = logs.get_query_results(queryId=qid)
                if resp.get("status") in ("Complete", "Failed", "Cancelled"):
                    break
        except logs.exceptions.ResourceNotFoundException:
            return self._send_json(200, {
                "decisions": [], "totals": {"allow": 0, "deny": 0}, "by_tool": {},
                "warning": "Log group /aws/spans does not exist. Run Lab 05 with traces enabled first."
            })
        except Exception as e:
            return self._send_json(500, {"error": "query_failed", "detail": str(e)})

        decisions = []
        totals = {"allow": 0, "deny": 0}
        by_tool: dict[str, dict] = {}

        for row in resp.get("results", []):
            f = {x["field"]: x["value"] for x in row}
            try:
                msg = json.loads(f.get("@message", "{}"))
            except Exception:
                continue
            attrs = msg.get("attributes", {})
            name = msg.get("name", "")
            ts = f.get("@timestamp", "")
            trace_id = f.get("traceId", "") or msg.get("traceId", "")

            if name.endswith("AuthorizeAction"):
                d = attrs.get("aws.agentcore.policy.authorization_decision", "")
                tool = (attrs.get("aws.agentcore.policy.target_resource.id") or "").split("/")[-1]
                # Tool name often missing in AuthorizeAction; infer from sibling ExecuteTool
                # For now, leave blank — front-end can fetch trace details.
                entry = {
                    "timestamp": ts,
                    "traceId":   trace_id,
                    "name":      "AuthorizeAction",
                    "decision":  d,
                    "tool":      "",  # populated by drill-down
                    "determining_policies": attrs.get("aws.agentcore.policy.determining_policies", []),
                }
                if d == "ALLOW": totals["allow"] += 1
                elif d == "DENY": totals["deny"] += 1
                decisions.append(entry)
            elif name.endswith("PartiallyAuthorizeActions"):
                allowed = attrs.get("aws.agentcore.policy.allowed_tools", []) or []
                denied = attrs.get("aws.agentcore.policy.denied_tools", []) or []
                # Each tool in the response counts as a separate decision
                # for tally purposes (matches metrics behaviour).
                for t in allowed:
                    by_tool.setdefault(t, {"tool": t, "allow": 0, "deny": 0})["allow"] += 1
                for t in denied:
                    by_tool.setdefault(t, {"tool": t, "allow": 0, "deny": 0})["deny"] += 1
                totals["allow"] += len(allowed)
                totals["deny"]  += len(denied)
                # Add a single summary entry; drill-down shows the breakdown
                decisions.append({
                    "timestamp": ts,
                    "traceId":   trace_id,
                    "name":      "PartiallyAuthorizeActions",
                    "decision":  "MIXED" if (allowed and denied) else ("ALLOW" if allowed else "DENY"),
                    "tool":      "",
                    "allowed_count": len(allowed),
                    "denied_count":  len(denied),
                    "denied_tools":  denied[:10],
                })

        # Filter by decision if requested
        if filter_decision == "allow":
            decisions = [d for d in decisions if d.get("decision") == "ALLOW"]
        elif filter_decision == "deny":
            decisions = [d for d in decisions if d.get("decision") in ("DENY", "MIXED")]

        return self._send_json(200, {
            "totals":    totals,
            "by_tool":   sorted(by_tool.values(), key=lambda x: -(x["allow"] + x["deny"])),
            "decisions": decisions[:100],
            "window_hours": hours,
        })

    def _api_cedar_trace(self, trace_id: str):
        """Returns all spans for a given traceId, with the user prompt
        extracted from the SmartAgent runtime logs (correlated by
        session.id).

        Spans alone don't carry the user prompt verbatim — that lives in
        the runtime logs. We get session.id from any span in the trace,
        then query the SmartAgent log group for the last user role message.
        """
        import re
        if not trace_id or len(trace_id) > 64:
            return self._send_json(400, {"error": "invalid_trace_id"})

        region = os.environ.get("AWS_REGION", "us-east-1")
        logs = boto3.client("logs", region_name=region)

        end_s = int(time.time())
        start_s = end_s - 24 * 3600

        # Step 1: Get all spans in the trace.
        spans_query = (
            f"fields @timestamp, name, @message\n"
            f"| filter traceId = '{trace_id}'\n"
            f"| sort @timestamp asc\n"
            f"| limit 200"
        )
        try:
            qid = logs.start_query(
                logGroupName="aws/spans",
                startTime=start_s, endTime=end_s,
                queryString=spans_query,
            )["queryId"]
            for _ in range(15):
                time.sleep(1)
                resp = logs.get_query_results(queryId=qid)
                if resp.get("status") in ("Complete", "Failed", "Cancelled"):
                    break
        except logs.exceptions.ResourceNotFoundException:
            return self._send_json(200, {
                "events": [], "session_id": None, "cedar_decisions": [],
                "warning": "Log group /aws/spans does not exist. Run Lab 05 with traces enabled first."
            })
        except Exception as e:
            return self._send_json(500, {"error": "query_failed", "detail": str(e)})

        events = []
        session_id = None
        cedar_decisions = []
        tool_calls = []
        agents_seen = set()

        for row in resp.get("results", []):
            f = {x["field"]: x["value"] for x in row}
            try:
                msg = json.loads(f.get("@message", "{}"))
            except Exception:
                continue
            name = msg.get("name", "")
            svc = msg.get("resource", {}).get("attributes", {}).get("service.name", "")
            attrs = msg.get("attributes", {})
            ts = f.get("@timestamp", "")

            if svc and svc not in agents_seen:
                agents_seen.add(svc)

            # Session ID — from any attribute with session.id.
            if not session_id:
                sid = attrs.get("session.id") or attrs.get("session_id")
                if sid:
                    session_id = sid

            if name.endswith("AgentCore.Policy.AuthorizeAction"):
                cedar_decisions.append({
                    "timestamp": ts,
                    "type": "AuthorizeAction",
                    "decision": attrs.get("aws.agentcore.policy.authorization_decision"),
                    "determining_policies": attrs.get("aws.agentcore.policy.determining_policies", []),
                })
            elif name.endswith("AgentCore.Policy.PartiallyAuthorizeActions"):
                cedar_decisions.append({
                    "timestamp": ts,
                    "type": "PartiallyAuthorizeActions",
                    "allowed_tools": attrs.get("aws.agentcore.policy.allowed_tools", []),
                    "denied_tools":  attrs.get("aws.agentcore.policy.denied_tools", []),
                })

            if "InvokeTool." in name:
                tool_name = name.split("InvokeTool.", 1)[1]
                tool_calls.append({"timestamp": ts, "tool": tool_name})

            events.append({"timestamp": ts, "service": svc, "name": name})

        # Step 2: Extract user prompt and assistant response from runtime logs
        # using session_id correlation.
        user_prompt = None
        agent_response = None

        if session_id:
            # Look in the SmartAgent runtime log group (router has the user prompt).
            sa_arn = os.environ.get("RUNTIME_SMART_AGENT_ARN", "")
            sa_id = sa_arn.split("/")[-1] if sa_arn else ""
            if sa_id:
                rt_log = f"/aws/bedrock-agentcore/runtimes/{sa_id}-DEFAULT"
                try:
                    qid = logs.start_query(
                        logGroupName=rt_log,
                        startTime=start_s, endTime=end_s,
                        queryString=(
                            f"fields @timestamp, @message\n"
                            f"| filter @message like /{session_id[:32]}/\n"
                            f"| sort @timestamp asc\n"
                            f"| limit 50"
                        ),
                    )["queryId"]
                    for _ in range(10):
                        time.sleep(1)
                        rresp = logs.get_query_results(queryId=qid)
                        if rresp.get("status") in ("Complete", "Failed", "Cancelled"):
                            break

                    # Strands telemetry stringifies messages as escaped JSON.
                    # The user prompt appears as `"text": "<content>"` followed
                    # by `"role":"user"` (sometimes far apart in the same line).
                    # We search for "role":"user" and look backwards for the
                    # nearest preceding "text" field.
                    role_user_pat = re.compile(r'"role"\s*:\s*"user"')
                    # Match either escaped or unescaped text fields.
                    text_pat_escaped = re.compile(r'\\"text\\"\s*:\s*\\"((?:[^\\"\\\\]|\\\\.)*?)\\"')
                    text_pat_plain   = re.compile(r'"text"\s*:\s*"((?:[^"\\]|\\.)*?)"')
                    asst_pat = re.compile(
                        r'"finish_reason"\s*:\s*"end_turn"[^}]*?"message"\s*:\s*"((?:[^"\\]|\\.){5,500})"'
                    )

                    for r in rresp.get("results", []):
                        f = {x["field"]: x["value"] for x in r}
                        m = f.get("@message", "")

                        if not user_prompt:
                            for ru in role_user_pat.finditer(m):
                                start = max(0, ru.start() - 500)
                                chunk = m[start:ru.end()]
                                texts = list(text_pat_escaped.finditer(chunk)) or \
                                        list(text_pat_plain.finditer(chunk))
                                if texts:
                                    user_prompt = (
                                        texts[-1].group(1)
                                        .replace("\\n", " ").replace("\\\"", '"').strip()
                                    )[:500]
                                    break

                        if not agent_response:
                            am = asst_pat.search(m)
                            if am:
                                agent_response = (
                                    am.group(1).replace("\\n", " ").replace("\\\"", '"').strip()
                                )[:500]
                except Exception as e:
                    log.exception("runtime log query failed")

        return self._send_json(200, {
            "trace_id": trace_id,
            "user_prompt": user_prompt,
            "agent_response": agent_response,
            "session_id": session_id,
            "agents_involved": sorted(agents_seen),
            "cedar_decisions": cedar_decisions,
            "tool_calls": tool_calls,
            "spans_count": len(events),
        })

    def _api_system_status(self):
        """Live state of the demo's AWS resources. Shown on 'sistema.html'."""
        region = os.environ.get("AWS_REGION", "us-east-1")
        status: dict[str, Any] = {"region": region, "sector": SECTOR}

        # Cognito
        try:
            pool_id = os.environ.get("COGNITO_USER_POOL_ID", "")
            client_id = os.environ.get("COGNITO_CLIENT_ID", "")
            cognito = boto3.client("cognito-idp", region_name=region)
            pool = cognito.describe_user_pool(UserPoolId=pool_id).get("UserPool", {}) if pool_id else {}
            groups = cognito.list_groups(UserPoolId=pool_id).get("Groups", []) if pool_id else []
            status["cognito"] = {
                "poolId":   pool_id,
                "clientId": client_id,
                "poolName": pool.get("Name"),
                "groups":   [g["GroupName"] for g in groups],
                "ok":       bool(pool_id and client_id),
            }
        except Exception as e:
            status["cognito"] = {"ok": False, "error": str(e)}

        # Gateway
        try:
            gw_id  = os.environ.get("AGENTCORE_GATEWAY_ID", "")
            gw_url = os.environ.get("AGENTCORE_GATEWAY_URL", "")
            ac = boto3.client("bedrock-agentcore-control", region_name=region)
            gw = ac.get_gateway(gatewayIdentifier=gw_id) if gw_id else {}
            status["gateway"] = {
                "id":        gw_id,
                "url":       gw_url,
                "status":    gw.get("status"),
                "searchType": gw.get("protocolConfiguration", {}).get("mcp", {}).get("searchType"),
                "policyEngine": gw.get("policyEngineConfiguration", {}),
                "ok":        gw.get("status") == "READY",
            }
        except Exception as e:
            status["gateway"] = {"ok": False, "error": str(e)}

        # Runtimes
        runtimes_state = []
        try:
            ac = boto3.client("bedrock-agentcore-control", region_name=region)
            for name, env in RUNTIMES.items():
                arn = os.environ.get(env, "")
                rid = arn.split("/")[-1] if arn else ""
                item = {"name": name, "arn": arn, "id": rid, "ok": False, "status": None}
                if rid:
                    try:
                        d = ac.get_agent_runtime(agentRuntimeId=rid)
                        item["status"] = d.get("status")
                        item["ok"]     = d.get("status") == "READY"
                    except Exception as e:
                        item["error"] = str(e)
                runtimes_state.append(item)
        except Exception as e:
            status["runtimesError"] = str(e)
        status["runtimes"] = runtimes_state

        # Policy engine + policies
        try:
            eid = os.environ.get("AGENTCORE_POLICY_ENGINE_ID", "")
            ac = boto3.client("bedrock-agentcore-control", region_name=region)
            policies = ac.list_policies(policyEngineId=eid).get("policies", []) if eid else []
            status["policyEngine"] = {
                "id":        eid,
                "policies":  [{"name": p["name"], "id": p.get("policyId"), "status": p.get("status")} for p in policies],
                "count":     len(policies),
                "ok":        bool(eid and policies),
            }
        except Exception as e:
            status["policyEngine"] = {"ok": False, "error": str(e)}

        # Guardrail
        status["guardrail"] = {
            "id":      os.environ.get("BEDROCK_GUARDRAIL_ID", ""),
            "version": os.environ.get("BEDROCK_GUARDRAIL_VERSION", ""),
            "ok":      bool(os.environ.get("BEDROCK_GUARDRAIL_ID")),
        }

        self._send_json(200, status)

    # ─────────────────────────────────────────────────────────────────────
    #  Static file serving
    # ─────────────────────────────────────────────────────────────────────

    def _serve_static(self, relpath: str, root: Path = STATIC_DIR):
        relpath = relpath.lstrip("/")
        target = (root / relpath).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError:
            return self._send(403, b"forbidden", "text/plain")

        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            return self._send(404, f"Not found: {relpath}".encode(), "text/plain")

        ctype, _ = mimetypes.guess_type(str(target))
        ctype = ctype or "application/octet-stream"
        self._send(200, target.read_bytes(), ctype)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _decode_groups(access_token: str) -> list[str]:
    """Decode (no verify) the Cognito access token to read cognito:groups claim."""
    try:
        payload_b64 = access_token.split(".")[1]
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        return payload.get("cognito:groups", []) or []
    except Exception:
        return []


def _aggregate_verdict(delegations: list[dict]) -> str:
    """Combine per-specialist verdicts into a single one for the SmartAgent turn."""
    if not delegations:
        return "not-invoked"
    verdicts = {d.get("cedar_verdict", "not-invoked") for d in delegations}
    if verdicts == {"permit"}:                             return "permit"
    if "deny" in verdicts and "permit" not in verdicts:    return "deny"
    if "deny" in verdicts and "permit" in verdicts:        return "mixed"
    if verdicts == {"cedar-filtered"}:                     return "cedar-filtered"
    if "cedar-filtered" in verdicts:                       return "mixed"
    if verdicts == {"not-invoked"}:                        return "not-invoked"
    return "mixed"


# ─────────────────────────────────────────────────────────────────────────────
#  CloudWatch helpers for the governance metrics endpoint
#
#  These assemble GetMetricData queries against the `AWS/Bedrock-AgentCore`
#  namespace — the native metrics the AgentCore Policy Engine publishes when
#  Cedar evaluates a request. No derivation, no log parsing, just reads.
# ─────────────────────────────────────────────────────────────────────────────

_CW_NAMESPACE = "AWS/Bedrock-AgentCore"


def _query_param(path: str, key: str, default: str) -> str:
    qs = parse_qs(urlparse(path).query)
    return (qs.get(key) or [default])[0]


def _pick_period(hours: int) -> int:
    """Choose a CloudWatch period (seconds) so the series has ~60 datapoints."""
    if hours <= 1:   return 60
    if hours <= 6:   return 300
    if hours <= 24:  return 900
    if hours <= 72:  return 3600
    return 3600


def _total_query(id_: str, metric: str, engine: str, period: int, stat: str = "Sum") -> dict:
    """Aggregate count for a metric filtered by PolicyEngine.

    The Policy Engine publishes the same metric under a handful of dimension
    combinations. We use SEARCH() over the richest one
    ``{TargetResource,ToolName,OperationName,PolicyEngine}`` because that is
    the combo that carries per-tool counters (one metric per tool per
    gateway). SUM rolls them up.
    """
    search = (
        f"SEARCH('{{AWS/Bedrock-AgentCore,TargetResource,ToolName,OperationName,PolicyEngine}} "
        f"MetricName=\"{metric}\" PolicyEngine=\"{engine}\"','{stat}',{period})"
    )
    return {"Id": id_, "Expression": f"SUM({search})", "ReturnData": True}


def _series_query(id_: str, metric: str, engine: str, period: int) -> dict:
    """Time-series of metric total — buckets aligned to `period` seconds."""
    search = (
        f"SEARCH('{{AWS/Bedrock-AgentCore,TargetResource,ToolName,OperationName,PolicyEngine}} "
        f"MetricName=\"{metric}\" PolicyEngine=\"{engine}\"','Sum',{period})"
    )
    return {"Id": id_, "Expression": f"SUM({search})", "ReturnData": True}


def _per_tool_query(id_: str, metric: str, engine: str, period: int) -> dict:
    """Return one series per (Tool, Operation) combination."""
    return {
        "Id": id_,
        "Expression": (
            f"SEARCH('{{AWS/Bedrock-AgentCore,TargetResource,ToolName,OperationName,PolicyEngine}} "
            f"MetricName=\"{metric}\" PolicyEngine=\"{engine}\"','Sum',{period})"
        ),
        "ReturnData": True,
    }


def _sum_or_last(id_: str, resp: dict) -> float:
    """Get the sum of all datapoints for a result by id (or the last one for averages)."""
    for r in resp.get("MetricDataResults", []):
        if r.get("Id") == id_:
            values = r.get("Values") or []
            if not values:
                return 0.0
            # Rough heuristic: averages/percentiles → last point; everything else → sum.
            if any(k in id_ for k in ("avg", "p50", "p90", "p95", "p99", "lat")):
                return round(float(values[-1]), 2)
            return float(sum(values))
    return 0.0


def _points(id_: str, resp: dict) -> list:
    """Return [{t: isoZ, v: number}, ...] for a time-series result."""
    for r in resp.get("MetricDataResults", []):
        if r.get("Id") == id_:
            ts = r.get("Timestamps", [])
            vs = r.get("Values", [])
            return [{"t": t.isoformat(timespec="seconds"), "v": float(v)} for t, v in zip(ts, vs)]
    return []


def _aggregate_by_tool(resp: dict, current_gateway: str = "") -> list[dict]:
    """Build rows ``{tool, allow, deny}`` from per-tool SEARCH() results.

    CloudWatch preserves the parent query ``Id`` on every returned series, so
    we can tell Allow from Deny via that field (our parent queries use
    ``allow_t`` and ``deny_t``). The ``Label`` is the space-joined dimension
    values followed by the metric name:
    ``<TargetResource> <ToolName> <MetricName>`` → ToolName is the
    second-to-last token.
    """
    by_tool: dict[str, dict] = {}
    for r in resp.get("MetricDataResults", []):
        label = r.get("Label") or ""
        parts = label.split()
        if len(parts) < 3:
            continue
        gateway = parts[0]
        tool    = parts[-2]
        if "___" not in tool:              # only our MCP tool names (prefix___name)
            continue
        if current_gateway and gateway != current_gateway:
            continue                        # skip stale metrics from old gateways
        total = float(sum(r.get("Values") or []))
        if total == 0:
            continue
        agg = by_tool.setdefault(tool, {"tool": tool, "allow": 0.0, "deny": 0.0})
        rid = r.get("Id", "")
        if rid.startswith("allow"):
            agg["allow"] += total
        elif rid.startswith("deny"):
            agg["deny"] += total
    rows = [v for v in by_tool.values() if v["allow"] or v["deny"]]
    rows.sort(key=lambda x: (-x["deny"], -x["allow"]))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
#  Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8080)
    return p.parse_args()


def main():
    args = parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), PortalHandler)
    log.info("portal serving on http://%s:%s  (sector=%s)", args.host, args.port, SECTOR)
    log.info("static dir: %s", STATIC_DIR)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down...")
        srv.server_close()


if __name__ == "__main__":
    main()
