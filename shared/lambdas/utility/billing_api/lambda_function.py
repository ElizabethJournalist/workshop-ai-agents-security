"""
BillingAPI — Lambda tool for AgentCore Gateway (utility sector).

Tools:
    - get_invoice(invoice_id)                          → restrito por Cedar P4
    - get_consumption_history(customer_id, months?)    → restrito por Cedar P4

Contém PII e dados financeiros — segregação por Cedar policy.
"""
import json
from datetime import datetime, timezone


def _ok(data):  return {"statusCode": 200, "body": json.dumps(data)}
def _err(msg, code=400):  return {"statusCode": code, "body": json.dumps({"error": msg})}
def _now_iso():  return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


INVOICES = {
    "INV-2024-03-0091": {
        "invoice_id": "INV-2024-03-0091", "customer_id": "CLI-00234",
        "customer_name": "Petroquímica Vale do Paraíba S.A.",
        "customer_cnpj": "12.345.678/0001-90",
        "period": "2024-03", "consumption_kwh": 1_842_300, "demand_kw": 3_200,
        "amount_brl": 987_432.50, "due_date": "2024-04-10",
        "status": "paid", "tariff_class": "A4",
    },
    "INV-2024-03-0092": {
        "invoice_id": "INV-2024-03-0092", "customer_id": "CLI-00891",
        "customer_name": "Indústrias Têxteis Nordeste Ltda",
        "customer_cnpj": "98.765.432/0001-11",
        "period": "2024-03", "consumption_kwh": 412_800, "demand_kw": 800,
        "amount_brl": 218_640.00, "due_date": "2024-04-10",
        "status": "overdue", "tariff_class": "A4",
    },
}

CONSUMPTION_HISTORY = {
    "CLI-00234": [
        {"period": "2024-01", "consumption_kwh": 1_780_000, "demand_kw": 3_100, "amount_brl": 952_000.00},
        {"period": "2024-02", "consumption_kwh": 1_810_000, "demand_kw": 3_150, "amount_brl": 968_000.00},
        {"period": "2024-03", "consumption_kwh": 1_842_300, "demand_kw": 3_200, "amount_brl": 987_432.50},
    ],
    "CLI-00891": [
        {"period": "2024-01", "consumption_kwh": 398_000, "demand_kw": 780, "amount_brl": 210_000.00},
        {"period": "2024-02", "consumption_kwh": 405_000, "demand_kw": 790, "amount_brl": 214_000.00},
        {"period": "2024-03", "consumption_kwh": 412_800, "demand_kw": 800, "amount_brl": 218_640.00},
    ],
}


def get_invoice(invoice_id):
    invoice = INVOICES.get(invoice_id)
    if not invoice:
        return _err(f"Fatura '{invoice_id}' não encontrada", 404)
    return _ok(invoice)


def get_consumption_history(customer_id, months=3):
    history = CONSUMPTION_HISTORY.get(customer_id)
    if history is None:
        return _err(f"Cliente '{customer_id}' não encontrado", 404)
    return _ok({
        "customer_id": customer_id,
        "months_requested": months,
        "records": history[-months:],
        "queried_at": _now_iso(),
    })


def lambda_handler(event, context):
    tool_name = context.client_context.custom.get("bedrockAgentCoreToolName", "")
    tool = tool_name.split("___")[-1] if "___" in tool_name else tool_name

    if tool == "get_invoice":
        return get_invoice(event.get("invoice_id"))
    if tool == "get_consumption_history":
        return get_consumption_history(event.get("customer_id"), int(event.get("months", 3)))
    return _err(f"Tool desconhecida: '{tool}'", 404)
