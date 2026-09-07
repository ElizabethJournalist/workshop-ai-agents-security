"""
ContractAPI — Lambda tool for AgentCore Gateway (utility sector).

Tools:
    - search_contracts(category?, status?, supplier?)
    - extract_clause(contract_id, clause_type)
"""
import json
from datetime import datetime, timezone


def _ok(data):  return {"statusCode": 200, "body": json.dumps(data)}
def _err(msg, code=400):  return {"statusCode": code, "body": json.dumps({"error": msg})}


CONTRACTS = {
    "CT-2023-0087": {
        "contract_id": "CT-2023-0087", "category": "equipment_supply",
        "supplier": "ABB Power Systems", "supplier_cnpj": "11.111.111/0001-11",
        "value_brl": 4_500_000.00, "start_date": "2023-06-01", "end_date": "2026-05-31",
        "status": "active", "title": "Fornecimento de transformadores 138/13.8kV",
    },
    "CT-2024-0012": {
        "contract_id": "CT-2024-0012", "category": "maintenance_services",
        "supplier": "Engemak Engenharia Ltda", "supplier_cnpj": "22.222.222/0001-22",
        "value_brl": 1_200_000.00, "start_date": "2024-01-15", "end_date": "2025-01-14",
        "status": "active", "title": "Serviços de manutenção preventiva em LT 138kV",
    },
}

CLAUSES = {
    ("CT-2023-0087", "penalty"): "Cláusula 12.3 — Atraso na entrega: multa de 0,5% por dia, limitada a 10% do valor total.",
    ("CT-2023-0087", "sla"): "Cláusula 8.1 — Suporte técnico em até 4h em horário comercial; 8h fora do horário.",
    ("CT-2024-0012", "termination"): "Cláusula 15 — Rescisão com aviso prévio de 30 dias; multa de 5% do valor restante.",
    ("CT-2024-0012", "sla"): "Cláusula 7 — Resposta em 2h para emergências; 24h para inspeções programadas.",
}


def search_contracts(category=None, status="active", supplier=None):
    contracts = list(CONTRACTS.values())
    if status != "all":
        contracts = [c for c in contracts if c["status"] == status]
    if category:
        contracts = [c for c in contracts if c["category"] == category]
    if supplier:
        contracts = [c for c in contracts if supplier.lower() in c["supplier"].lower()]
    return _ok({"count": len(contracts), "contracts": contracts})


def extract_clause(contract_id, clause_type):
    if contract_id not in CONTRACTS:
        return _err(f"Contrato '{contract_id}' não encontrado", 404)
    clause = CLAUSES.get((contract_id, clause_type))
    if not clause:
        return _ok({
            "contract_id": contract_id,
            "clause_type": clause_type,
            "found": False,
            "message": f"Cláusula '{clause_type}' não disponível para {contract_id}",
        })
    return _ok({"contract_id": contract_id, "clause_type": clause_type, "found": True, "text": clause})


def lambda_handler(event, context):
    tool_name = context.client_context.custom.get("bedrockAgentCoreToolName", "")
    tool = tool_name.split("___")[-1] if "___" in tool_name else tool_name

    if tool == "search_contracts":
        return search_contracts(event.get("category"), event.get("status", "active"), event.get("supplier"))
    if tool == "extract_clause":
        return extract_clause(event.get("contract_id"), event.get("clause_type"))
    return _err(f"Tool desconhecida: '{tool}'", 404)
