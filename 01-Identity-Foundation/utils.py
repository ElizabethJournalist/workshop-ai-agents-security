"""
01-Identity-Foundation/utils.py — helpers de Cognito específicos deste lab.

Funções:
    create_user_pool_with_groups()  → User Pool + grupos + usuários
    create_app_client()             → app client OAuth com PKCE
    create_resource_server()        → resource server com scopes (para Gateway)
    add_user_to_groups()            → adiciona um user a múltiplos grupos
    get_bearer_token()              → autentica via USER_PASSWORD_AUTH e retorna token
    decode_jwt()                    → decodifica e mostra claims (sem validar)
    cleanup_user_pool()             → remove user pool

Os usuários e grupos são extraídos do demo agents-governance-demo:
    - operators  : Ana Operadora — campo, vê grid, cria work orders
    - managers   : Carlos Gestor — aprova work orders, gera relatórios
    - governance : (opcional) — compliance, auditoria
"""
from __future__ import annotations

import json
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError


# ─────────────────────────────────────────────────────────────────────────────
# Default users & groups (extraídos do demo)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_GROUPS = [
    {
        "name": "operators",
        "description": "Operadores de campo — visualizam rede, criam ordens de serviço",
    },
    {
        "name": "managers",
        "description": "Gestores — aprovam ordens, geram relatórios",
    },
    {
        "name": "governance",
        "description": "Equipe de governança — auditoria, compliance",
    },
]

DEFAULT_USERS = [
    {
        "username": "ana.operadora",
        "email": "ana.operadora@workshop.local",
        "groups": ["operators"],
        "given_name": "Ana",
        "family_name": "Operadora",
    },
    {
        "username": "carlos.gestor",
        "email": "carlos.gestor@workshop.local",
        "groups": ["managers", "governance"],
        "given_name": "Carlos",
        "family_name": "Gestor",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# User Pool
# ─────────────────────────────────────────────────────────────────────────────

def find_existing_pool(client, pool_name: str) -> dict | None:
    """Retorna o pool dict se já existir, senão None."""
    paginator = client.get_paginator("list_user_pools")
    for page in paginator.paginate(MaxResults=60):
        for p in page["UserPools"]:
            if p["Name"] == pool_name:
                return p
    return None


def create_user_pool_with_groups(
    pool_name: str = "workshop-ai-agents-pool",
    *,
    groups: list[dict] | None = None,
    users: list[dict] | None = None,
    user_password: str = "Workshop@2025!",
    region: str = "us-east-1",
) -> dict:
    """
    Cria um User Pool com grupos e usuários — idempotente.

    Args:
        pool_name: Nome do pool. Default: 'workshop-ai-agents-pool'.
        groups:    Lista de {name, description}. Default: DEFAULT_GROUPS.
        users:     Lista de {username, email, groups, given_name, family_name}.
                   Default: DEFAULT_USERS (Ana e Carlos).
        user_password: Senha permanente para todos os usuários (workshop apenas).
        region:    Região AWS.

    Returns:
        Dict com pool_id, pool_arn, e listas de groups/users criados.
    """
    cognito = boto3.client("cognito-idp", region_name=region)
    groups = groups or DEFAULT_GROUPS
    users = users or DEFAULT_USERS

    # 1. User Pool
    existing = find_existing_pool(cognito, pool_name)
    if existing:
        pool_id = existing["Id"]
        print(f"  ~ User Pool já existe: {pool_id}")
    else:
        resp = cognito.create_user_pool(
            PoolName=pool_name,
            Policies={
                "PasswordPolicy": {
                    "MinimumLength": 8,
                    "RequireUppercase": True,
                    "RequireLowercase": True,
                    "RequireNumbers": True,
                    "RequireSymbols": True,
                }
            },
            Schema=[
                {"Name": "email", "AttributeDataType": "String", "Required": True, "Mutable": True},
                {"Name": "given_name", "AttributeDataType": "String", "Mutable": True},
                {"Name": "family_name", "AttributeDataType": "String", "Mutable": True},
            ],
            UsernameAttributes=["email"],
            AutoVerifiedAttributes=["email"],
            UserPoolTags={"project": "workshop-ai-agents-security"},
        )
        pool_id = resp["UserPool"]["Id"]
        print(f"  ✓ User Pool criado: {pool_id}")

    pool_desc = cognito.describe_user_pool(UserPoolId=pool_id)["UserPool"]
    pool_arn = pool_desc["Arn"]

    # 2. Grupos
    for g in groups:
        try:
            cognito.create_group(
                GroupName=g["name"],
                UserPoolId=pool_id,
                Description=g["description"],
            )
            print(f"  ✓ Grupo criado: {g['name']}")
        except cognito.exceptions.GroupExistsException:
            print(f"  ~ Grupo já existe: {g['name']}")

    # 3. Usuários
    created_users = []
    for u in users:
        newly_created = False
        try:
            cognito.admin_create_user(
                UserPoolId=pool_id,
                Username=u["email"],
                UserAttributes=[
                    {"Name": "email", "Value": u["email"]},
                    {"Name": "email_verified", "Value": "true"},
                    {"Name": "given_name", "Value": u.get("given_name", "")},
                    {"Name": "family_name", "Value": u.get("family_name", "")},
                ],
                MessageAction="SUPPRESS",
                TemporaryPassword=user_password,
            )
            print(f"  ✓ Usuário criado: {u['email']}")
            newly_created = True
        except cognito.exceptions.UsernameExistsException:
            print(f"  ~ Usuário já existe: {u['email']}")

        # Senha permanente só em usuário recém-criado
        if newly_created:
            cognito.admin_set_user_password(
                UserPoolId=pool_id,
                Username=u["email"],
                Password=user_password,
                Permanent=True,
            )

        # Add to groups
        for group_name in u.get("groups", []):
            try:
                cognito.admin_add_user_to_group(
                    UserPoolId=pool_id,
                    Username=u["email"],
                    GroupName=group_name,
                )
                print(f"     → adicionado ao grupo: {group_name}")
            except ClientError as e:
                if e.response["Error"]["Code"] != "UserNotFoundException":
                    print(f"     ⚠ erro ao adicionar a {group_name}: {e}")

        created_users.append(u["email"])

    return {
        "pool_id": pool_id,
        "pool_arn": pool_arn,
        "groups": [g["name"] for g in groups],
        "users": created_users,
        "discovery_url": f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Domain (necessário para OAuth flow com hosted UI)
# ─────────────────────────────────────────────────────────────────────────────

def create_user_pool_domain(
    pool_id: str,
    *,
    domain_prefix: str | None = None,
    region: str = "us-east-1",
) -> str:
    """
    Cria um domain Cognito para o pool. Idempotente.

    Args:
        pool_id: ID do user pool.
        domain_prefix: Prefixo do domínio. Se None, deriva do pool_id (sem underscore, lowercase).
        region: Região AWS.

    Returns:
        URL completo (https://<prefix>.auth.<region>.amazoncognito.com).
    """
    cognito = boto3.client("cognito-idp", region_name=region)
    domain_prefix = domain_prefix or pool_id.replace("_", "").lower()

    pool = cognito.describe_user_pool(UserPoolId=pool_id)["UserPool"]
    if pool.get("Domain"):
        existing_domain = pool["Domain"]
        print(f"  ~ Domain já configurado: {existing_domain}")
        return f"https://{existing_domain}.auth.{region}.amazoncognito.com"

    cognito.create_user_pool_domain(Domain=domain_prefix, UserPoolId=pool_id)
    print(f"  ✓ Domain criado: {domain_prefix}")
    return f"https://{domain_prefix}.auth.{region}.amazoncognito.com"


# ─────────────────────────────────────────────────────────────────────────────
# App Client (para o portal — USER_PASSWORD_AUTH) e Resource Server (para o Gateway)
# ─────────────────────────────────────────────────────────────────────────────

def create_app_client_user_password(
    pool_id: str,
    *,
    client_name: str = "workshop-portal-client",
    region: str = "us-east-1",
) -> str:
    """
    Cria um app client com USER_PASSWORD_AUTH (usado pelo portal nos labs).

    Returns:
        client_id (sem secret — public client).
    """
    cognito = boto3.client("cognito-idp", region_name=region)

    existing = cognito.list_user_pool_clients(UserPoolId=pool_id, MaxResults=10)
    for c in existing.get("UserPoolClients", []):
        if c["ClientName"] == client_name:
            print(f"  ~ App client já existe: {c['ClientId']}")
            return c["ClientId"]

    resp = cognito.create_user_pool_client(
        UserPoolId=pool_id,
        ClientName=client_name,
        GenerateSecret=False,
        ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
        TokenValidityUnits={"AccessToken": "hours", "IdToken": "hours", "RefreshToken": "days"},
        AccessTokenValidity=1,
        IdTokenValidity=1,
        RefreshTokenValidity=7,
    )
    client_id = resp["UserPoolClient"]["ClientId"]
    print(f"  ✓ App client criado: {client_id}")
    return client_id


def create_resource_server_with_scopes(
    pool_id: str,
    *,
    identifier: str = "workshop/gateway",
    name: str = "WorkshopGatewayResource",
    scopes: list[dict] | None = None,
    region: str = "us-east-1",
) -> dict:
    """
    Cria resource server com scopes (usado pelo Gateway authorizer no Lab 02).

    Args:
        pool_id: User pool ID.
        identifier: Identificador único (vira prefixo do scope: '<id>/<scope>').
        name: Nome amigável.
        scopes: Lista de {ScopeName, ScopeDescription}.
                Default: gateway:read e gateway:invoke.

    Returns:
        Dict com identifier, full_scopes (lista de strings 'identifier/scope').
    """
    cognito = boto3.client("cognito-idp", region_name=region)
    scopes = scopes or [
        {"ScopeName": "read", "ScopeDescription": "Read MCP tools metadata"},
        {"ScopeName": "invoke", "ScopeDescription": "Invoke MCP tools"},
    ]

    try:
        existing = cognito.describe_resource_server(
            UserPoolId=pool_id,
            Identifier=identifier,
        )
        print(f"  ~ Resource server já existe: {identifier}")
    except cognito.exceptions.ResourceNotFoundException:
        cognito.create_resource_server(
            UserPoolId=pool_id,
            Identifier=identifier,
            Name=name,
            Scopes=scopes,
        )
        print(f"  ✓ Resource server criado: {identifier}")

    full_scopes = [f"{identifier}/{s['ScopeName']}" for s in scopes]
    return {"identifier": identifier, "full_scopes": full_scopes}


# ─────────────────────────────────────────────────────────────────────────────
# Bearer token (login programático)
# ─────────────────────────────────────────────────────────────────────────────

def get_bearer_token(
    pool_id: str,
    client_id: str,
    username: str,
    password: str,
    *,
    region: str = "us-east-1",
) -> dict:
    """
    Autentica usuário via USER_PASSWORD_AUTH e retorna os tokens.

    Args:
        pool_id, client_id, username, password: credenciais.
        region: região AWS.

    Returns:
        Dict com access_token, id_token, refresh_token, expires_in.
    """
    cognito = boto3.client("cognito-idp", region_name=region)

    resp = cognito.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": username, "PASSWORD": password},
    )
    auth = resp["AuthenticationResult"]
    return {
        "access_token": auth["AccessToken"],
        "id_token": auth["IdToken"],
        "refresh_token": auth.get("RefreshToken"),
        "expires_in": auth.get("ExpiresIn"),
    }


def decode_jwt(token: str, *, verify: bool = False) -> dict:
    """
    Decodifica um JWT e retorna o payload (claims).

    ⚠️ Por default NÃO valida assinatura — é só para visualização didática
    no notebook. Em produção use jwt.decode com algoritmo + chave pública.

    Args:
        token: JWT string.
        verify: Se True, valida assinatura (requer chave pública).

    Returns:
        Dict com claims do payload.
    """
    import jwt as pyjwt
    if verify:
        raise NotImplementedError("Validação de JWT é tema do Lab 02 (Gateway).")
    return pyjwt.decode(token, options={"verify_signature": False})


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────────────────

def cleanup_user_pool(pool_name: str = "workshop-ai-agents-pool", *, region: str = "us-east-1") -> bool:
    """Remove o User Pool e seu domain. Idempotente."""
    cognito = boto3.client("cognito-idp", region_name=region)
    pool = find_existing_pool(cognito, pool_name)
    if not pool:
        print(f"  ~ User Pool não existe (ok): {pool_name}")
        return False

    pool_id = pool["Id"]
    pool_desc = cognito.describe_user_pool(UserPoolId=pool_id)["UserPool"]
    if pool_desc.get("Domain"):
        try:
            cognito.delete_user_pool_domain(Domain=pool_desc["Domain"], UserPoolId=pool_id)
            print(f"  ✓ Domain deletado: {pool_desc['Domain']}")
        except ClientError as e:
            print(f"  ⚠ erro ao deletar domain: {e}")

    cognito.delete_user_pool(UserPoolId=pool_id)
    print(f"  ✓ User Pool deletado: {pool_id}")
    return True
