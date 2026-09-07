"""
GridAPI — Lambda tool for AgentCore Gateway (utility sector).

Tools expostas via MCP:
    - get_grid_status(sector?)        → status da rede por setor
    - get_outage_alerts(severity?, status?)  → alertas de blackouts

AgentCore Gateway passa parâmetros direto no event dict.
Tool name vem em context.client_context.custom['bedrockAgentCoreToolName'].
"""
import json
from datetime import datetime, timedelta, timezone


# ── helpers ─────────────────────────────────────────────────────────
def _ok(data):  return {"statusCode": 200, "body": json.dumps(data)}
def _err(msg, code=400):  return {"statusCode": code, "body": json.dumps({"error": msg})}
def _now_iso():  return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def _past_iso(days):  return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── mock data ───────────────────────────────────────────────────────
SECTORS = {
    "norte": {"load_mw": 142.3, "voltage_kv": 138.0, "status": "normal", "substations": 4},
    "sul":   {"load_mw": 98.7,  "voltage_kv": 135.2, "status": "normal", "substations": 3},
    "leste": {"load_mw": 210.5, "voltage_kv": 137.8, "status": "alert",  "substations": 6},
    "oeste": {"load_mw": 75.1,  "voltage_kv": 138.5, "status": "normal", "substations": 2},
}

OUTAGES = [
    {
        "alert_id": "OT-2024-0312", "sector": "leste", "type": "voltage_deviation",
        "severity": "high",
        "description": "Tensão abaixo do limite regulatório (ANEEL Módulo 8) na subestação SE-Leste-03",
        "started_at": _past_iso(0), "affected_customers": 1240, "status": "active",
    },
    {
        "alert_id": "OT-2024-0298", "sector": "norte", "type": "planned_maintenance",
        "severity": "low",
        "description": "Manutenção preventiva programada — linha 138kV trecho Norte-Centro",
        "started_at": _past_iso(1), "affected_customers": 0, "status": "resolved",
    },
]


# ── tool implementations ───────────────────────────────────────────
def get_grid_status(sector=None):
    if sector:
        sector = sector.lower()
        if sector not in SECTORS:
            return _err(f"Setor '{sector}' inválido. Válidos: {list(SECTORS.keys())}")
        return _ok({"sector": sector, "timestamp": _now_iso(), **SECTORS[sector]})
    return _ok({
        "timestamp": _now_iso(),
        "sectors": {k: {"status": v["status"], "load_mw": v["load_mw"]} for k, v in SECTORS.items()},
        "total_load_mw": sum(v["load_mw"] for v in SECTORS.values()),
        "system_status": "alert" if any(v["status"] == "alert" for v in SECTORS.values()) else "normal",
    })


def get_outage_alerts(severity=None, status="active"):
    alerts = OUTAGES
    if status != "all":
        alerts = [a for a in alerts if a["status"] == status]
    if severity:
        alerts = [a for a in alerts if a["severity"] == severity]
    return _ok({"count": len(alerts), "alerts": alerts, "queried_at": _now_iso()})


def lambda_handler(event, context):
    tool_name = context.client_context.custom.get("bedrockAgentCoreToolName", "")
    tool = tool_name.split("___")[-1] if "___" in tool_name else tool_name

    if tool == "get_grid_status":
        return get_grid_status(sector=event.get("sector"))
    if tool == "get_outage_alerts":
        return get_outage_alerts(severity=event.get("severity"), status=event.get("status", "active"))
    return _err(f"Tool desconhecida: '{tool}'", 404)
