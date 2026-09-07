---
title: "Introduction"
weight: 10
---

## Why This Workshop Exists

Enterprise teams adopting agentic AI hit the same wall. The first agent works. Five agents work. Then the security team shows up with questions nobody has answers to:

- What happens when an agent calls an MCP server connected to a production database?
- How do you stop a compromised MCP server from moving data where it should not go?
- When a federated user triggers an agent, what controls govern the IAM roles the agent assumes?
- How do you enforce that Agent A can query inventory but not approve purchase orders?

These questions come directly from enterprise customers evaluating Bedrock for production. This workshop builds the answers.

## What You Will Learn

By the end of this workshop, you will be able to:

- Set up federated identity with Cognito User Pools and map groups to JWT claims for agent authorization
- Deploy an AgentCore Gateway with JWT validation as the single entry point for all agent operations
- Write Cedar policies that enforce fine-grained, role-based access control over agent tools
- Configure tenant-isolated agent memory (STM and LTM) with namespace-based separation
- Deploy a router agent with specialist agents on AgentCore Runtime with proper IAM role scoping
- Apply Bedrock Guardrails to filter prompt injection, PII leakage, and sensitive content
- Manage agent lifecycle through the Agent Registry (publish, discover, deprecate)
- Set up CloudTrail logging, Cedar decision spans, and CloudWatch alarms for agent governance
- Run a full end-to-end demo with all security layers active

## The Scenario

You are building an internal operations platform where field operators, managers, and governance staff interact with AI agents. Each team needs different access levels. The agents read operational data, generate reports, and execute workflows. Your job is to lock this down: authenticated users only reach the tools appropriate to their role, agent memory stays isolated per user, outputs are filtered for sensitive content, and every action gets logged.

## Target Audience

- Solutions Architects evaluating Bedrock AgentCore security for customer engagements
- Technical Account Managers preparing security deep dives for AI-native customers
- Security engineers assessing agentic AI platforms for enterprise deployment
- Developers building multi-agent systems who need production-grade security controls
