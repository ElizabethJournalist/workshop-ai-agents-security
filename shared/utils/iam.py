"""
shared.utils.iam — IAM roles para os componentes do workshop.

Funções:
    create_lambda_role(name)            → role básico de execução para Lambda mocks
    create_gateway_role(name)           → role do AgentCore Gateway (invoke Lambda + bedrock-agentcore)
    create_runtime_role(agent_name)     → role do AgentCore Runtime (Bedrock + Memory + Workload Identity)
    delete_role(role_name)              → cleanup (detach managed + delete inline + delete role)

Convenções:
    - Funções são idempotentes: se a role já existe, retornam o ARN.
    - Wait curto (3-10s) após criar para propagação do IAM (eventual consistency).
    - Tags padrão: project=workshop-ai-agents-security
"""
from __future__ import annotations

import json
import time

import boto3
from botocore.exceptions import ClientError


PROJECT_TAG = [
    {"Key": "project", "Value": "workshop-ai-agents-security"},
    {"Key": "ManagedBy", "Value": "shared.utils.iam"},
]


# ─────────────────────────────────────────────────────────────────────────────
# Lambda execution role (para as 5 mocks do shared/lambdas/<setor>/)
# ─────────────────────────────────────────────────────────────────────────────

LAMBDA_TRUST = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole",
    }],
}

LAMBDA_INLINE_LOGS = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
        "Resource": "arn:aws:logs:*:*:*",
    }],
}


def create_lambda_role(role_name: str = "workshop-lambda-role") -> str:
    """
    Cria (ou retorna se já existe) a IAM role de execução para Lambdas.

    Args:
        role_name: Nome da role. Default: 'workshop-lambda-role'.

    Returns:
        ARN da role.
    """
    iam = boto3.client("iam")

    try:
        resp = iam.get_role(RoleName=role_name)
        print(f"  ~ Role já existe: {role_name}")
        return resp["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        pass

    resp = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(LAMBDA_TRUST),
        Description="Lambda execution role for Workshop-AI-Agents-Security mocks",
        Tags=PROJECT_TAG,
    )
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="cloudwatch-logs",
        PolicyDocument=json.dumps(LAMBDA_INLINE_LOGS),
    )
    time.sleep(8)  # IAM eventual consistency
    print(f"  ✓ Role criada: {role_name}")
    return resp["Role"]["Arn"]


# ─────────────────────────────────────────────────────────────────────────────
# AgentCore Gateway role (assume bedrock-agentcore, invoca Lambdas dos targets)
# ─────────────────────────────────────────────────────────────────────────────

def _gateway_trust_doc(account_id: str, region: str) -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "AssumeRoleByAgentCore",
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {"aws:SourceAccount": account_id},
                "ArnLike": {
                    "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                },
            },
        }],
    }


GATEWAY_INLINE = {
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "GatewayCorePermissions",
        "Effect": "Allow",
        "Action": [
            "bedrock-agentcore:*",
            "bedrock:InvokeModel",
            "bedrock:InvokeModelWithResponseStream",
            "agent-credential-provider:*",
            "iam:PassRole",
            "secretsmanager:GetSecretValue",
            "lambda:InvokeFunction",
        ],
        "Resource": "*",
    }],
}


def create_gateway_role(role_name: str = "workshop-gateway-role", *, region: str | None = None) -> str:
    """
    Cria role para o AgentCore Gateway. Permissões:
    - Assume role por bedrock-agentcore.amazonaws.com (apenas da própria account)
    - Invoke Lambda dos targets
    - Acesso ao Bedrock para modelos (semantic search opcional)
    - agent-credential-provider para outbound auth
    - secretsmanager para credenciais armazenadas

    Args:
        role_name: Nome da role. Default: 'workshop-gateway-role'.
        region: Região AWS. Default: lê de AWS_REGION env ou us-east-1.

    Returns:
        ARN da role.
    """
    import os
    iam = boto3.client("iam")
    sts = boto3.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    region = region or os.environ.get("AWS_REGION") or boto3.session.Session().region_name or "us-east-1"

    trust = _gateway_trust_doc(account_id, region)

    try:
        resp = iam.get_role(RoleName=role_name)
        print(f"  ~ Role já existe: {role_name}")
        # garante trust + inline atualizados
        iam.update_assume_role_policy(
            RoleName=role_name,
            PolicyDocument=json.dumps(trust),
        )
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="GatewayCorePolicy",
            PolicyDocument=json.dumps(GATEWAY_INLINE),
        )
        return resp["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        pass

    resp = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(trust),
        Description="AgentCore Gateway role for Workshop-AI-Agents-Security",
        Tags=PROJECT_TAG,
    )
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="GatewayCorePolicy",
        PolicyDocument=json.dumps(GATEWAY_INLINE),
    )
    time.sleep(10)
    print(f"  ✓ Role criada: {role_name}")
    return resp["Role"]["Arn"]


# ─────────────────────────────────────────────────────────────────────────────
# AgentCore Runtime role (Bedrock + Memory + Workload Identity)
# ─────────────────────────────────────────────────────────────────────────────

def _runtime_trust_doc(account_id: str, region: str) -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "AssumeRoleByAgentCore",
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {"aws:SourceAccount": account_id},
                "ArnLike": {
                    "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                },
            },
        }],
    }


def _runtime_inline_doc(account_id: str, region: str, agent_name: str) -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BedrockInvoke",
                "Effect": "Allow",
                "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:ApplyGuardrail", "bedrock:CountTokens"],
                "Resource": "*",
            },
            {
                "Sid": "CloudWatchLogs",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                ],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*",
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*",
                    f"arn:aws:logs:{region}:{account_id}:log-group:*",
                ],
            },
            {
                "Sid": "XRayTracing",
                "Effect": "Allow",
                "Action": [
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                ],
                "Resource": "*",
            },
            {
                "Sid": "CloudWatchMetrics",
                "Effect": "Allow",
                "Action": "cloudwatch:PutMetricData",
                "Resource": "*",
                "Condition": {
                    "StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}
                },
            },
            {
                "Sid": "AgentCoreAPI",
                "Effect": "Allow",
                "Action": ["bedrock-agentcore:*", "iam:PassRole", "lambda:InvokeFunction"],
                "Resource": "*",
            },
            {
                "Sid": "WorkloadIdentity",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                ],
                "Resource": [
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default/workload-identity/{agent_name}-*",
                ],
            },
            {
                "Sid": "S3ReadArtifact",
                "Effect": "Allow",
                "Action": ["s3:GetObject"],
                "Resource": f"arn:aws:s3:::workshop-agents-{account_id}/*",
            },
        ],
    }


def create_runtime_role(agent_name: str, role_name: str | None = None, *, region: str | None = None) -> str:
    """
    Cria role para o AgentCore Runtime de um agente.

    Args:
        agent_name: Nome do agente (ex: 'smart_agent', 'grid_monitor').
                    Usado nas WorkloadIdentity ARNs.
        role_name: Nome da role. Default: 'workshop-runtime-{agent_name}'.
        region: Região AWS. Default: lê de AWS_REGION env ou us-east-1.

    Returns:
        ARN da role.
    """
    import os
    role_name = role_name or f"workshop-runtime-{agent_name}"
    iam = boto3.client("iam")
    sts = boto3.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    region = region or os.environ.get("AWS_REGION") or boto3.session.Session().region_name or "us-east-1"

    trust = _runtime_trust_doc(account_id, region)
    inline = _runtime_inline_doc(account_id, region, agent_name)

    try:
        resp = iam.get_role(RoleName=role_name)
        print(f"  ~ Role já existe: {role_name}")
        iam.update_assume_role_policy(
            RoleName=role_name,
            PolicyDocument=json.dumps(trust),
        )
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="RuntimeCorePolicy",
            PolicyDocument=json.dumps(inline),
        )
        return resp["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        pass

    resp = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(trust),
        Description=f"AgentCore Runtime role for {agent_name} (Workshop-AI-Agents-Security)",
        Tags=PROJECT_TAG + [{"Key": "agent", "Value": agent_name}],
    )
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="RuntimeCorePolicy",
        PolicyDocument=json.dumps(inline),
    )
    time.sleep(10)
    print(f"  ✓ Role criada: {role_name}")
    return resp["Role"]["Arn"]


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────────────────

def delete_role(role_name: str) -> bool:
    """
    Remove uma IAM role: detach managed policies + delete inline policies + delete role.

    Args:
        role_name: Nome da role.

    Returns:
        True se deletou com sucesso, False se a role não existia.
    """
    iam = boto3.client("iam")

    try:
        # Detach managed policies
        for p in iam.list_attached_role_policies(RoleName=role_name).get("AttachedPolicies", []):
            iam.detach_role_policy(RoleName=role_name, PolicyArn=p["PolicyArn"])

        # Delete inline policies
        for name in iam.list_role_policies(RoleName=role_name).get("PolicyNames", []):
            iam.delete_role_policy(RoleName=role_name, PolicyName=name)

        iam.delete_role(RoleName=role_name)
        print(f"  ✓ Role deletada: {role_name}")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            print(f"  ~ Role não existe (ok): {role_name}")
            return False
        raise
