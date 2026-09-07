"""
MaintenanceAPI — Lambda tool for AgentCore Gateway (utility sector).

Tools:
    - create_work_order(asset_id, description, type?, priority?)
    - approve_work_order(work_order_id, notes?)         → restrita a managers (Cedar P2)
    - get_asset_history(asset_id)
"""
import json
import uuid
from datetime import datetime, timedelta, timezone


def _ok(data):  return {"statusCode": 200, "body": json.dumps(data)}
def _err(msg, code=400):  return {"statusCode": code, "body": json.dumps({"error": msg})}
def _now_iso():  return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def _past_iso(days):  return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


WORK_ORDERS = {
    "WO-2024-0041": {
        "id": "WO-2024-0041", "asset_id": "SE-LESTE-03", "type": "corrective",
        "description": "Substituição de transformador de potência 138/13.8kV",
        "priority": "high", "status": "pending_approval",
        "created_by": "ana.operadora@workshop.local", "created_at": _past_iso(2),
        "approved_by": None, "approved_at": None, "estimated_hours": 8,
    },
    "WO-2024-0038": {
        "id": "WO-2024-0038", "asset_id": "LT-NORTE-01", "type": "preventive",
        "description": "Inspeção termográfica linha de transmissão 138kV",
        "priority": "medium", "status": "approved",
        "created_by": "ana.operadora@workshop.local", "created_at": _past_iso(5),
        "approved_by": "carlos.gestor@workshop.local", "approved_at": _past_iso(4),
        "estimated_hours": 4,
    },
}

ASSET_HISTORY = {
    "SE-LESTE-03": [
        {"date": _past_iso(30), "event": "Inspeção visual", "technician": "João Silva", "result": "ok"},
        {"date": _past_iso(90), "event": "Troca de óleo isolante", "technician": "Maria Santos", "result": "ok"},
        {"date": _past_iso(180), "event": "Teste de proteção", "technician": "João Silva", "result": "anomaly_detected"},
    ],
    "LT-NORTE-01": [
        {"date": _past_iso(15), "event": "Inspeção termográfica", "technician": "Carlos Lima", "result": "ok"},
    ],
}


def create_work_order(asset_id, description, type="corrective", priority="medium"):
    if not asset_id or not description:
        return _err("asset_id e description são obrigatórios")
    wo_id = f"WO-2024-{str(uuid.uuid4())[:4].upper()}"
    WORK_ORDERS[wo_id] = {
        "id": wo_id, "asset_id": asset_id, "type": type, "description": description,
        "priority": priority, "status": "pending_approval",
        "created_by": "current_user", "created_at": _now_iso(),
        "approved_by": None, "approved_at": None, "estimated_hours": None,
    }
    return _ok({"message": "Work order criada", "work_order": WORK_ORDERS[wo_id]})


def approve_work_order(work_order_id, notes=""):
    """Cedar policy P2 (Lab 03) garante que apenas managers chamam esta função."""
    wo = WORK_ORDERS.get(work_order_id)
    if not wo:
        return _err(f"Work order '{work_order_id}' não encontrada", 404)
    if wo["status"] != "pending_approval":
        return _err(f"Work order está '{wo['status']}', não pending_approval")
    wo.update({
        "status": "approved",
        "approved_by": "authenticated_manager",  # identidade garantida por Cedar P2
        "approved_at": _now_iso(),
        "approval_notes": notes,
    })
    return _ok({"message": "Work order aprovada", "work_order": wo})


def get_asset_history(asset_id):
    history = ASSET_HISTORY.get(asset_id)
    if history is None:
        return _ok({"asset_id": asset_id, "history": [], "message": "Sem histórico"})
    return _ok({"asset_id": asset_id, "record_count": len(history), "history": history})


def lambda_handler(event, context):
    tool_name = context.client_context.custom.get("bedrockAgentCoreToolName", "")
    tool = tool_name.split("___")[-1] if "___" in tool_name else tool_name

    if tool == "create_work_order":
        return create_work_order(
            event.get("asset_id"), event.get("description"),
            event.get("type", "corrective"), event.get("priority", "medium"),
        )
    if tool == "approve_work_order":
        return approve_work_order(event.get("work_order_id"), event.get("notes", ""))
    if tool == "get_asset_history":
        return get_asset_history(event.get("asset_id"))
    return _err(f"Tool desconhecida: '{tool}'", 404)
