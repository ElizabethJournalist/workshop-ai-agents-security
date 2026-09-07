"""
SmartAgent — Roteador universal do workshop.

✨ ESTE ARQUIVO É UNIVERSAL — não muda entre setores.

O prompt do agente é carregado dinamicamente de `shared/prompts/<SECTOR>/smart_agent.md`
em runtime, usando a env var SECTOR (default: utility).

Os specialists vivem em `agents/<setor>/*.py` e são chamados via tool delegation.
Os ARNs dos specialists vêm de variáveis de ambiente (set durante deploy):
    RUNTIME_GRID_AGENT_ARN, RUNTIME_MAINTENANCE_AGENT_ARN, etc.

Pattern: Agents-as-Tools (Strands).
- User → SmartAgent (Haiku 4.5, fast routing)
- SmartAgent → invoke_<specialist> tools → POST HTTPS no specialist runtime
- JWT do usuário é propagado em todo o caminho

Note: este SmartAgent é deliberadamente STATELESS por turno. STM é gerenciado
pelo specialist; LTM é puxado direto da Memory API.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Any
from urllib.parse import quote

import boto3
import requests
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel


# ─────────────────────────────────────────────────────────────────────────────
# Prompt loading — carrega de shared/prompts/<SECTOR>/smart_agent.md
# ─────────────────────────────────────────────────────────────────────────────

def _load_prompt() -> str:
    """Carrega smart_agent.md do diretório do setor (env SECTOR, default 'utility')."""
    sector = os.environ.get("SECTOR", "utility")

    # Tenta múltiplos paths (em deploy o file fica num lugar, em dev em outro)
    candidates = [
        Path(__file__).resolve().parent / "smart_agent.md",  # deployado junto
        Path(__file__).resolve().parents[2] / "shared" / "prompts" / sector / "smart_agent.md",  # dev
        Path("shared/prompts") / sector / "smart_agent.md",  # cwd-relative
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"Prompt do SmartAgent não encontrado para setor '{sector}'. "
        f"Tentei: {[str(p) for p in candidates]}"
    )


SYSTEM_PROMPT = _load_prompt()
AGENT_NAME = "SmartAgent"
logger = logging.getLogger(AGENT_NAME)

# Context vars para passar JWT/session sem poluir o tool schema
_current_jwt: ContextVar[str] = ContextVar("smart_jwt", default="")
_current_session: ContextVar[str] = ContextVar("smart_session", default="")
_delegations: ContextVar[list[dict]] = ContextVar("smart_delegations", default=[])


# ─────────────────────────────────────────────────────────────────────────────
# JWT helpers (inline para não depender de base.py)
# ─────────────────────────────────────────────────────────────────────────────

def _ctx_headers(context) -> dict:
    """Headers do contexto do AgentCore Runtime — expostos como request_headers."""
    if context is not None and hasattr(context, "request_headers"):
        return getattr(context, "request_headers", {}) or {}
    if isinstance(context, dict):
        return context.get("request_headers") or context.get("headers") or {}
    return getattr(context, "headers", {}) or {}


def _extract_jwt(context) -> str:
    """Extrai o JWT do context object do AgentCore Runtime."""
    try:
        headers = _ctx_headers(context)
        auth = headers.get("Authorization") or headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            return auth[7:]
    except Exception as e:
        logger.warning("Falha ao extrair JWT: %s", e)
    return ""


def _extract_session_id(context) -> str:
    """Extrai session_id do contexto (atributo session_id ou header)."""
    try:
        if context is not None:
            sid_attr = getattr(context, "session_id", None)
            if sid_attr:
                return sid_attr
        headers = _ctx_headers(context)
        return headers.get("X-Amzn-Bedrock-AgentCore-Runtime-Session-Id") or \
               headers.get("x-amzn-bedrock-agentcore-runtime-session-id", "")
    except Exception:
        return ""


def _extract_actor_id(jwt_token: str) -> str:
    """Decodifica JWT (sem validar) e extrai username/sub."""
    if not jwt_token:
        return ""
    try:
        import jwt as pyjwt
        claims = pyjwt.decode(jwt_token, options={"verify_signature": False})
        return claims.get("username") or claims.get("sub", "")
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Specialist invocation (HTTPS POST com JWT propagado)
# ─────────────────────────────────────────────────────────────────────────────

def _invoke_runtime(env_var: str, query: str, specialist_name: str) -> dict:
    """POST para o runtime do specialist. Retorna dict {response, agent_name}."""
    runtime_arn = os.environ.get(env_var, "")
    if not runtime_arn:
        return {"response": f"[config] {env_var} não configurado", "agent_name": specialist_name}

    user_jwt = _current_jwt.get()
    if not user_jwt:
        return {"response": "[auth] JWT ausente", "agent_name": specialist_name}

    region = os.environ.get("AWS_REGION", "us-east-1")
    parent_sid = _current_session.get() or f"smart-{uuid.uuid4()}"
    session_id = (parent_sid + "-" + specialist_name.lower())[:64]
    if len(session_id) < 33:
        session_id = (session_id + "0" * 40)[:64]

    url = (
        f"https://bedrock-agentcore.{region}.amazonaws.com"
        f"/runtimes/{quote(runtime_arn, safe='')}/invocations?qualifier=DEFAULT"
    )
    headers = {
        "Authorization": f"Bearer {user_jwt}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
    }

    try:
        resp = requests.post(url, json={"prompt": query}, headers=headers, timeout=180)
    except Exception as e:
        return {"response": f"[network] {e}", "agent_name": specialist_name}

    if resp.status_code >= 400:
        return {"response": f"[HTTP {resp.status_code}] {resp.text[:400]}", "agent_name": specialist_name}

    try:
        data = resp.json()
    except Exception:
        return {"response": resp.text, "agent_name": specialist_name}

    if isinstance(data, dict) and "response" in data:
        return data
    return {"response": json.dumps(data, ensure_ascii=False), "agent_name": specialist_name}


def _delegate(env_var: str, query: str, specialist_name: str) -> str:
    data = _invoke_runtime(env_var, query, specialist_name)
    _delegations.get().append(data)
    return str(data.get("response", ""))


# ─────────────────────────────────────────────────────────────────────────────
# Tools — uma por specialist (Strands @tool)
# ─────────────────────────────────────────────────────────────────────────────

@tool
def invoke_grid_agent(query: str) -> str:
    """Delegue ao GridMonitorAgent: estado da rede, alertas, setores."""
    return _delegate("RUNTIME_GRID_AGENT_ARN", query, "GridMonitorAgent")


@tool
def invoke_maintenance_agent(query: str) -> str:
    """Delegue ao MaintenanceAgent: ordens de serviço, aprovações."""
    return _delegate("RUNTIME_MAINTENANCE_AGENT_ARN", query, "MaintenanceAgent")


@tool
def invoke_contract_agent(query: str) -> str:
    """Delegue ao ContractAgent: contratos, cláusulas."""
    return _delegate("RUNTIME_CONTRACT_AGENT_ARN", query, "ContractAgent")


@tool
def invoke_billing_agent(query: str) -> str:
    """Delegue ao CustomerBillingAgent: faturas e consumo (restrito)."""
    return _delegate("RUNTIME_BILLING_AGENT_ARN", query, "CustomerBillingAgent")


@tool
def invoke_regulatory_agent(query: str) -> str:
    """Delegue ao RegulatoryReportAgent: relatórios ANEEL (submissão bloqueada)."""
    return _delegate("RUNTIME_REGULATORY_AGENT_ARN", query, "RegulatoryReportAgent")


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint do AgentCore Runtime — async generator com SSE
# ─────────────────────────────────────────────────────────────────────────────

app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(payload, context):
    """Async generator. Cada `yield` vira um evento SSE."""
    prompt = (payload or {}).get("prompt", "")
    history = (payload or {}).get("history", [])
    user_jwt = _extract_jwt(context)
    session_id = _extract_session_id(context) or f"smart-{uuid.uuid4()}"

    token_jwt = _current_jwt.set(user_jwt)
    token_sid = _current_session.set(session_id)
    token_dels = _delegations.set([])

    try:
        model_id = os.environ.get(
            "SMART_AGENT_MODEL_ID",
            "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        )
        agent = Agent(
            model=BedrockModel(model_id=model_id),
            system_prompt=SYSTEM_PROMPT,
            tools=[
                invoke_grid_agent,
                invoke_maintenance_agent,
                invoke_contract_agent,
                invoke_billing_agent,
                invoke_regulatory_agent,
            ],
            callback_handler=None,
        )

        async for event in agent.stream_async(prompt):
            if "data" in event:
                yield {"type": "delta", "text": event["data"]}

        yield {"type": "done", "delegations": _delegations.get()}
    finally:
        _current_jwt.reset(token_jwt)
        _current_session.reset(token_sid)
        _delegations.reset(token_dels)


if __name__ == "__main__":
    app.run()
