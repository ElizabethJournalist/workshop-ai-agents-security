"""
agents/utility/base.py — Shared specialist helpers.

Each specialist is a BedrockAgentCoreApp runtime that:
  1. Validates the user's JWT (forwarded on Authorization header)
  2. Connects to the MCP Gateway → Cedar filters tools for this user's groups
  3. Runs a Strands Agent restricted to those tools
  4. Captures governance signals via a native AfterToolCallEvent hook
  5. Returns a structured dict with visible/denied tools, calls, verdict

Tracing is automatic: the runtime is launched with `opentelemetry-instrument
python <file>` (the AgentCore launcher does this when
`aws-opentelemetry-distro` is in requirements), and Strands emits OTEL spans
for every agent step / tool call. We do NOT emit manual spans here — the
auto-instrumentation plus the structured return value are enough for the
CloudWatch Transaction Search audit trail.

Returned dict schema:
  {
    "response":        str,
    "agent_name":      str,
    "expected_tools":  list[str],
    "visible_tools":   list[str],
    "denied_by_cedar": list[str],
    "tools_called":    list[{ "name": str, "decision": "permit"|"deny", "error"?: str }],
    "cedar_verdict":   "permit" | "deny" | "mixed" | "not-invoked" | "cedar-filtered"
  }
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import jwt
from strands import Agent
from strands.hooks import AfterToolCallEvent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)

# Ground truth used to compute Cedar-filtered tools (expected - visible).
# Must stay in sync with the Lambda tools exposed by setup_gateway.py.
EXPECTED_TOOLS: dict[str, list[str]] = {
    "GridMonitorAgent":      ["gridapi___get_grid_status", "gridapi___get_outage_alerts"],
    "MaintenanceAgent":      ["maintenanceapi___create_work_order",
                              "maintenanceapi___approve_work_order",
                              "maintenanceapi___get_asset_history"],
    "ContractAgent":         ["contractapi___search_contracts", "contractapi___extract_clause"],
    "CustomerBillingAgent":  ["billingapi___get_invoice", "billingapi___get_consumption_history"],
    "RegulatoryReportAgent": ["regulatoryapi___generate_report",
                              "regulatoryapi___get_compliance_data",
                              "regulatoryapi___submit_to_regulator"],
}


# ─────────────────────────────────────────────────────────────────────────────
#  JWT / context helpers
# ─────────────────────────────────────────────────────────────────────────────

def extract_jwt_from_context(context: Any) -> str:
    """Pull the Bearer token from the runtime request context."""
    headers = _headers(context)
    auth = headers.get("Authorization") or headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:]
    return auth


def extract_session_id(context: Any) -> str:
    """AgentCore Runtime exposes the session id in two places:
      1. `context.session_id`  (preferred — top-level attribute on RequestContext)
      2. Request header `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id`
    We try both so the runtime can be upgraded without breaking us."""
    if context is not None:
        sid = getattr(context, "session_id", None)
        if sid:
            return sid
    headers = _headers(context)
    for key in (
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id",
        "x-amzn-bedrock-agentcore-runtime-session-id",
    ):
        if key in headers:
            return headers[key]
    return ""


def extract_actor_id(token: str) -> str:
    """Stable per-user identifier for AgentCore Memory namespacing.

    Preference order:
      1. `sub`       — Cognito immutable UUID, stable even if the user renames
      2. `username`  — e.g. ana.operadora (readable; fine if sub unavailable)
      3. "anonymous" — last-resort fallback (shouldn't happen: JWT is required)
    """
    if not token:
        return "anonymous"
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
    except jwt.InvalidTokenError:
        return "anonymous"
    return claims.get("sub") or claims.get("username") or "anonymous"


def _headers(context: Any) -> dict:
    if context is not None and hasattr(context, "request_headers"):
        return context.request_headers or {}
    if isinstance(context, dict):
        return context.get("headers") or context.get("request_headers") or {}
    return {}


def log_jwt_claims(token: str, agent_name: str) -> None:
    """Decode (without verifying) the access token to log user identity. The
    runtime already validated the signature via the Cognito authorizer."""
    if not token:
        return
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
        logger.info(
            "[%s] JWT: username=%s groups=%s client_id=%s",
            agent_name,
            claims.get("username"),
            claims.get("cognito:groups"),
            claims.get("client_id"),
        )
    except jwt.InvalidTokenError as exc:
        logger.warning("[%s] Could not decode JWT: %s", agent_name, exc)


# ─────────────────────────────────────────────────────────────────────────────
#  MCP transport + prompt augmentation
# ─────────────────────────────────────────────────────────────────────────────

def _transport(gateway_url: str, user_jwt: str):
    return streamablehttp_client(
        gateway_url,
        headers={"Authorization": f"Bearer {user_jwt}"},
    )


def _enhance_prompt(base_prompt: str, visible: list[str], denied: list[str]) -> str:
    """Append minimal governance hints to the system prompt.

    DESIGN: Strands passes the visible tools to the LLM via the Bedrock
    Converse API tool_use mechanism. The LLM already knows which tools
    it can call — duplicating that as text in the prompt is redundant
    AND introduces a security risk (the AWS docs explicitly warn about
    'policy bypass through agent manipulation'; the more tool/policy
    info we put in the prompt, the more surface for prompt injection).

    Reference:
      https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html
        'By moving security controls outside of agent code [...] reducing
         the risk of policy bypass through agent manipulation.'

    What this prompt does:
      - Tells the LLM the canonical phrase to respond with on AuthZ errors
      - Forbids leaking technical names, policy IDs, AWS terms
      - Reinforces 'act, don't announce'

    What this prompt does NOT do:
      - List visible/denied tools (Strands handles via tool definitions)
      - Mention specific policies (P0..P7) or Cedar internals
      - Pre-evaluate authorization (Cedar at the Gateway is authoritative)

    The `visible` and `denied` arguments are kept in the signature only so
    the runtime metadata (used for the UI 'cedar-filtered' badge via
    _summarize) stays available — they are NOT injected here.
    """
    return f"""{base_prompt}

---
## GOVERNANCA

Cada chamada de ferramenta passa pelo Gateway, que aplica politicas de
seguranca antes de executar. Voce nao precisa avaliar permissoes - apenas
chame a ferramenta quando o usuario pedir uma acao.

REGRAS DE RESPOSTA:
1. Acao concreta? Chame a ferramenta IMEDIATAMENTE - nao escreva 'vou
   buscar', nao cumprimente antes da chamada.
2. Se uma ferramenta retornar erro de autorizacao (mensagem com
   'AuthorizeActionException', 'Tool Execution Denied', 'AccessDenied',
   ou similar), responda EXATAMENTE:
     "A politica de seguranca nao permite essa acao para o seu perfil.
      Solicite a um usuario com permissao apropriada."
3. Se o usuario pedir uma acao que voce NAO TEM ferramenta para fazer
   (porque o Gateway filtrou as ferramentas com base na politica), use
   a MESMA frase do item 2. NAO invente motivos como 'indisponibilidade
   temporaria', 'sistema fora do ar', 'nao tenho acesso ao sistema',
   'erro tecnico'. A causa real e SEMPRE governanca.
4. NUNCA mencione nomes tecnicos (billingapi___, gridapi___, etc),
   identificadores de policy (P0, P1, P4...), nem termos como Cedar,
   Gateway, IAM, CloudWatch. Use linguagem de negocio.
5. So responda sem chamar ferramenta quando a pergunta for puramente
   conversacional (saudacao, agradecimento, despedida).
"""


# ─────────────────────────────────────────────────────────────────────────────
#  Main entry
# ─────────────────────────────────────────────────────────────────────────────

def _make_memory_session_manager(actor_id: str, session_id: str, retrieve_ltm: bool = False):
    """Returns an AgentCoreMemorySessionManager if AGENTCORE_MEMORY_ID is set,
    otherwise None (falls back to no persistence). The SmartAgent passes
    retrieve_ltm=True so its prompts are enriched with recalled facts and
    preferences; specialists pass retrieve_ltm=False — they still contribute
    events to memory, but don't pull cross-session context (the supervisor
    already injected it)."""
    memory_id = os.environ.get("AGENTCORE_MEMORY_ID", "")
    if not memory_id or not session_id:
        return None
    # Session id must be >= 33 chars for AgentCore Memory — pad if needed.
    if len(session_id) < 33:
        session_id = (session_id + "-" + "0" * 40)[:64]

    try:
        from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
        from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
    except ImportError:
        logger.warning("bedrock-agentcore[memory] not installed — skipping Memory integration")
        return None

    sector = os.environ.get("DEMO_SECTOR", "utility")
    retrieval_config = {}
    if retrieve_ltm:
        retrieval_config = {
            f"/{sector}/facts/{actor_id}":       {"top_k": 5, "relevance_score": 0.4},
            f"/{sector}/preferences/{actor_id}": {"top_k": 3, "relevance_score": 0.4},
        }

    config = AgentCoreMemoryConfig(
        memory_id=memory_id,
        session_id=session_id,
        actor_id=actor_id,
        retrieval_config=retrieval_config or None,
    )
    region = os.environ.get("AWS_REGION", "us-east-1")
    return AgentCoreMemorySessionManager(config, region_name=region)


def run_specialist(
    prompt: str,
    user_jwt: str,
    system_prompt: str,
    agent_name: str,
    session_id: str = "",
) -> dict:
    """Run a specialist end-to-end and return a governance-aware dict."""
    gateway_url = os.environ.get("AGENTCORE_GATEWAY_URL", "")
    if not gateway_url:
        raise RuntimeError("AGENTCORE_GATEWAY_URL env var is required")
    if not user_jwt:
        raise RuntimeError(f"[{agent_name}] No JWT in Authorization header")

    actor_id = extract_actor_id(user_jwt)
    expected = EXPECTED_TOOLS.get(agent_name, [])
    tools_called: list[dict] = []

    def on_after_tool(event: AfterToolCallEvent) -> None:
        """Strands native hook — records each tool invocation's outcome.

        Distinguishes three cases:
          * success         → decision = "permit"
          * authorization denied (Cedar / IAM / 403) → decision = "deny"
          * validation / runtime error              → decision = "error"
            (e.g. missing required param, bad payload, Lambda timeout)

        This matters because the UI maps "deny" to the 'CEDAR BLOCKED'
        badge. Flagging a missing-argument error as 'deny' is misleading —
        it isn't governance saying no, it's the tool asking for more info.
        """
        name = (event.tool_use or {}).get("name", "?")
        result = event.result
        is_error = (
            getattr(result, "status", None) == "error"
            or (isinstance(result, dict) and (result.get("isError") or result.get("status") == "error"))
            or isinstance(result, Exception)
        )
        entry: dict = {"name": name, "decision": "permit"}
        if is_error:
            error_text = _extract_error(result)
            entry["error"] = error_text
            low = error_text.lower()
            auth_markers = (
                "unauthorized", "access denied", "accessdenied",
                "authorization", "forbidden", "not authorized",
                "policy denied", "cedar", "403",
                "authorizeactionexception",     # Cedar AuthorizeAction DENY
                "tool execution denied",         # Gateway literal response
                "policy enforcement",            # Cedar ENFORCE mode
                # When an LLM tries to call a tool that Cedar filtered out
                # of the tools/list, the MCP runtime raises "Unknown tool"
                # (the tool isn't in the agent's tool_use catalog). This
                # is functionally equivalent to a Cedar DENY at list-time.
                "unknown tool", "tool not found",
            )
            entry["decision"] = "deny" if any(m in low for m in auth_markers) else "error"
        tools_called.append(entry)

    model_kwargs: dict[str, Any] = {
        "model_id": os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
    }
    guardrail_id = os.environ.get("BEDROCK_GUARDRAIL_ID", "")
    if guardrail_id:
        model_kwargs["guardrail_id"] = guardrail_id
        model_kwargs["guardrail_version"] = os.environ.get("BEDROCK_GUARDRAIL_VERSION", "DRAFT")
        model_kwargs["guardrail_trace"] = "enabled"

    mcp_client = MCPClient(lambda: _transport(gateway_url, user_jwt))
    with mcp_client:
        tools = mcp_client.list_tools_sync()
        visible = sorted(_tool_name(t) for t in tools)
        denied  = sorted(set(expected) - set(visible))

        logger.info(
            "[%s] visible=%d denied=%d (denied: %s)",
            agent_name, len(visible), len(denied), denied or "—",
        )

        session_manager = _make_memory_session_manager(
            actor_id=actor_id, session_id=session_id, retrieve_ltm=False,
        )
        agent_kwargs = {
            "model":         BedrockModel(**model_kwargs),
            "tools":         tools,
            "system_prompt": _enhance_prompt(system_prompt, visible, denied),
        }
        if session_manager is not None:
            agent_kwargs["session_manager"] = session_manager

        if session_manager is not None:
            with session_manager:
                agent = Agent(**agent_kwargs)
                agent.hooks.add_callback(AfterToolCallEvent, on_after_tool)
                response_text = str(agent(prompt))
        else:
            agent = Agent(**agent_kwargs)
            agent.hooks.add_callback(AfterToolCallEvent, on_after_tool)
            response_text = str(agent(prompt))

    return {
        "response":        response_text,
        "agent_name":      agent_name,
        "expected_tools":  sorted(expected),
        "visible_tools":   visible,
        "denied_by_cedar": denied,
        "tools_called":    tools_called,
        "cedar_verdict":   _summarize(tools_called, denied, response_text),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Internals
# ─────────────────────────────────────────────────────────────────────────────

def _tool_name(tool: Any) -> str:
    return getattr(tool, "tool_name", None) or getattr(tool, "name", None) or "?"


def _extract_error(result: Any) -> str:
    if isinstance(result, Exception):
        return str(result)[:400]
    if isinstance(result, dict):
        content = result.get("content", [])
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and "text" in first:
                return first["text"][:400]
        return json.dumps(result)[:400]
    return str(result)[:400]


def _summarize(calls: list[dict], denied: list[str], response_text: str = "") -> str:
    """Map per-tool decisions into a single verdict for the UI badge.

    Important: `denied` is the STATIC set of tools Cedar keeps invisible
    for the current user. By itself it doesn't tell us if THIS turn was
    Cedar-filtered. But if the agent didn't call any tool AND the response
    contains denial markers AND there are denied tools in scope, it's a
    strong signal that Cedar filtered the very tool the user wanted.

    The verdict reflects what happened IN THIS TURN:
      * tool called and denied   → "deny"           (Cedar blocked in-flight)
      * tool called and ok       → "permit"
      * mix of permit + deny     → "mixed"
      * no tool, denial language → "cedar-filtered" (tools/list filtered out)
      * no tool, regular reply   → "not-invoked"    (conversational)
    """
    if calls:
        permits = sum(1 for c in calls if c["decision"] in ("permit", "error"))
        denies  = sum(1 for c in calls if c["decision"] == "deny")
        if denies and not permits: return "deny"
        if permits and not denies: return "permit"
        return "mixed"

    # No tool was called. Distinguish "Cedar filtered the tool away" from
    # "user just said hello".
    if denied:
        denial_markers = (
            "politica de seguranca", "política de segurança",
            "nao permite", "não permite",
            "permissao apropriada", "permissão apropriada",
            "policy", "cedar",
            "bloqueada", "bloqueado",
            "perfil", "grupo",
        )
        low = (response_text or "").lower()
        if any(m in low for m in denial_markers):
            return "cedar-filtered"
    return "not-invoked"
