---
title: "Securing AI Agents at Scale with Amazon Bedrock AgentCore"
weight: 0
---

Build a governed AI agent platform, one security layer at a time. You start with ungoverned agents making direct model API calls. By the end, every agent operation goes through authentication, authorization, content filtering, and audit logging before it executes.

Each lab solves a real security problem that comes up when enterprises scale agentic AI.

![Architecture: 9 security layers from Identity Foundation through Observability, building up to a fully governed agent platform](/static/architecture.svg)

## The Problem

As the number of AI agents grows, the DIY approach stops working. Direct model API calls without a managed runtime leave gaps:

- No enforcement of what agents can invoke or what data they can access
- No audit trail when something goes wrong
- No way to tell which agents are approved for production versus still in testing
- Prompt injection and data exfiltration risks with no content filtering layer

This workshop builds the controls that close those gaps.

## What You Will Build

| Module | Labs | Security Problem Solved | Time |
|---|---|---|---|
| [Identity Foundation](/module-1-identity) | 2 | Who is this user and what are they authorized to do? | 15 min |
| [AgentCore Gateway](/module-2-gateway) | 3 | How do we enforce authenticated access to all agent operations? | 25 min |
| [AgentCore Policy (Cedar)](/module-3-policy) | 4 | How do we control which users can call which tools? | 30 min |
| [AgentCore Memory](/module-4-memory) | 2 | How do we isolate agent memory across tenants? | 20 min |
| [AgentCore Runtime](/module-5-runtime) | 3 | How do we deploy agents with security controls baked in? | 30 min |
| [Bedrock Guardrails](/module-6-guardrails) | 1 | How do we filter content and prevent data exfiltration? | 15 min |
| [Agent Registry](/module-7-registry) | 2 | How do we govern which agents are approved for production? | 15 min |
| [Observability](/module-8-observability) | 2 | How do we audit every agent decision and detect anomalies? | 20 min |
| [End-to-End](/module-9-end-to-end) | 1 | Full platform demo with all controls active | 15 min |

**Total estimated time:** 3 hours

## How It Works

Each module has a Workshop Studio page explaining the security problem and why it matters, followed by Jupyter notebooks with hands-on labs. The notebooks are self-contained: run the cells, see the results, understand the security control.

The labs build on each other. Identity (Module 1) creates the users that Gateway (Module 2) authenticates, that Policy (Module 3) authorizes, that Runtime (Module 5) executes, and that Observability (Module 8) audits. You can run them in order for the full story, or jump to a specific module if you need a targeted deep dive.
