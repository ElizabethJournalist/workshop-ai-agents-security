"""
04-AgentCore-Memory/utils.py — helpers de AgentCore Memory.

Funções:
    create_memory_resource()    → cria memory com 3 estratégias (semantic + prefs + summary)
    wait_memory_active()        → aguarda status ACTIVE
    create_event()              → grava um evento (STM)
    list_events()               → lista eventos da sessão
    retrieve_memories()         → busca semântica em LTM
    cleanup_memory()            → remove memory resource
"""
from __future__ import annotations

import time
from typing import Any

import boto3
from botocore.exceptions import ClientError


def find_existing_memory(name: str, *, region: str = "us-east-1") -> dict | None:
    """Lista memories e retorna o dict que casa com o nome (prefixo '<name>-')."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    token = None
    while True:
        kw = {"maxResults": 50}
        if token:
            kw["nextToken"] = token
        resp = client.list_memories(**kw)
        for m in resp.get("memories", []):
            if m.get("id", "").startswith(f"{name}-"):
                return m
        token = resp.get("nextToken")
        if not token:
            return None


def create_memory_resource(
    name: str = "workshop_memory",
    *,
    sector: str = "utility",
    event_expiry_days: int = 30,
    region: str = "us-east-1",
) -> dict:
    """
    Cria Memory com 3 estratégias LTM:
      * SemanticMemoryStrategy   — fatos extraídos de conversas
      * UserPreferenceMemoryStrategy — preferências do usuário
      * SummaryMemoryStrategy    — resumo rolante por sessão

    Namespaces escopados por `{actorId}` (multi-tenant — Ana não vê memória de Carlos).

    Returns:
        Dict com memory_id, memory_arn.
    """
    client = boto3.client("bedrock-agentcore-control", region_name=region)

    existing = find_existing_memory(name, region=region)
    if existing:
        print(f"  ~ Memory já existe: {existing['id']}")
        return {"memory_id": existing["id"], "memory_arn": existing["arn"]}

    resp = client.create_memory(
        name=name,
        description=(
            f"Workshop AI Agents Security ({sector}) — STM + LTM unificados, "
            f"compartilhados entre router e specialists."
        ),
        eventExpiryDuration=event_expiry_days,
        memoryStrategies=[
            {
                "semanticMemoryStrategy": {
                    "name": f"{sector.capitalize()}Facts",
                    "description": "Fatos extraídos de conversas (ativos, setores, incidentes).",
                    "namespaces": [f"/{sector}/facts/{{actorId}}"],
                },
            },
            {
                "userPreferenceMemoryStrategy": {
                    "name": f"{sector.capitalize()}UserPrefs",
                    "description": "Preferências (estilo de resposta, setores favoritos).",
                    "namespaces": [f"/{sector}/preferences/{{actorId}}"],
                },
            },
            {
                "summaryMemoryStrategy": {
                    "name": f"{sector.capitalize()}SessionSummaries",
                    "description": "Resumo rolante por sessão.",
                    "namespaces": [f"/{sector}/summaries/{{actorId}}/{{sessionId}}"],
                },
            },
        ],
    )
    print(f"  ✓ Memory criado: {resp['memory']['id']}")
    return {"memory_id": resp["memory"]["id"], "memory_arn": resp["memory"]["arn"]}


def wait_memory_active(memory_id: str, *, region: str = "us-east-1", timeout: int = 240) -> str:
    """Aguarda memory atingir ACTIVE."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get_memory(memoryId=memory_id)
        status = resp.get("memory", {}).get("status")
        print(f"  Memory status: {status}")
        if status in ("ACTIVE", "READY"):
            return status
        if status in ("FAILED", "DELETED"):
            raise RuntimeError(f"Memory atingiu estado {status}")
        time.sleep(5)
    raise TimeoutError(f"Memory {memory_id} não ficou ACTIVE em {timeout}s")


def create_event(
    memory_id: str,
    *,
    actor_id: str,
    session_id: str,
    payload: list[dict],
    region: str = "us-east-1",
) -> str:
    """
    Grava um evento em STM.

    Args:
        memory_id: ID do memory.
        actor_id: ID do usuário. Só [a-zA-Z0-9-_/] — ex: "ana-operadora" (sem @domínio).
        session_id: ID da sessão.
        payload: Lista de blocos {"conversational": {"role": "USER"|"ASSISTANT", "content": {"text": "..."}}}.
        region: Região AWS.

    Returns:
        event_id.
    """
    from datetime import datetime, timezone
    client = boto3.client("bedrock-agentcore", region_name=region)
    resp = client.create_event(
        memoryId=memory_id,
        actorId=actor_id,
        sessionId=session_id,
        eventTimestamp=datetime.now(timezone.utc),
        payload=payload,
    )
    return resp["event"]["eventId"]


def list_events(
    memory_id: str,
    *,
    actor_id: str,
    session_id: str,
    region: str = "us-east-1",
) -> list[dict]:
    """Lista todos os eventos de uma sessão (STM), com paginação."""
    client = boto3.client("bedrock-agentcore", region_name=region)
    events = []
    token = None
    while True:
        kw = {"memoryId": memory_id, "actorId": actor_id, "sessionId": session_id, "maxResults": 50}
        if token:
            kw["nextToken"] = token
        resp = client.list_events(**kw)
        events.extend(resp.get("events", []))
        token = resp.get("nextToken")
        if not token:
            return events


def retrieve_memories(
    memory_id: str,
    *,
    namespace: str,
    query: str,
    top_k: int = 5,
    region: str = "us-east-1",
) -> list[dict]:
    """
    Busca semântica em LTM.

    Args:
        memory_id: ID do memory.
        namespace: Ex: "/utility/facts/ana.operadora@workshop.local".
        query: Texto de busca.
        top_k: Número de resultados.
        region: Região AWS.

    Returns:
        Lista de memory records com score de similaridade.
    """
    client = boto3.client("bedrock-agentcore", region_name=region)
    return client.retrieve_memory_records(
        memoryId=memory_id,
        namespace=namespace,
        searchCriteria={"searchQuery": query, "topK": top_k},
    ).get("memoryRecordSummaries", [])


def cleanup_memory(memory_id: str, *, region: str = "us-east-1") -> bool:
    """Remove memory resource. Idempotente."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    try:
        client.delete_memory(memoryId=memory_id)
        print(f"  ✓ Memory deletado: {memory_id}")
        return True
    except ClientError as e:
        if "ResourceNotFoundException" in type(e).__name__:
            print(f"  ~ Memory não existe (ok): {memory_id}")
            return False
        raise
