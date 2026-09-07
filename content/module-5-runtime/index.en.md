---
title: "Module 5: AgentCore Runtime"
weight: 60
---

## The Problem

You have identity, a gateway, authorization policies, and isolated memory. Now you need to deploy actual agents that use all of these controls. The challenge: how do you deploy agents where the IAM role scope is bounded by the user's authorization context, not just the agent's own role? How does a router agent delegate to specialist agents while propagating the user's JWT end to end?

## What You Will Build

A multi-agent deployment on AgentCore Runtime with proper security scoping:

- **Router Agent**, receives user requests and delegates to the right specialist
- **Specialist Agents**, domain-specific agents (billing, grid operations) each with their own IAM role
- **SSE Streaming**, invoke agents via HTTPS with Server-Sent Events, passing the bearer token for authentication

## Why This Matters

The Runtime is where Identity, Gateway, Policy, and Memory converge in a running system. The router agent receives a JWT-authenticated request through the Gateway, Cedar authorizes the tool call, the agent executes with a scoped IAM role, memory is accessed within the user's namespace, and the response streams back through the same authenticated channel. Every security control from Modules 1-4 is active simultaneously.

## Labs

| Lab | Title | What You Do | Time |
|---|---|---|---|
| 05.1 | [Deploy Router Agent](lab-05-1/) | Deploy the router agent on AgentCore Runtime with IAM role and tracing | 15 min |
| 05.2 | [Deploy Specialists](lab-05-2/) | Deploy domain-specific specialist agents with scoped permissions | 10 min |
| 05.3 | [Invoke Runtime with SSE Streaming](lab-05-3/) | Call the agent end-to-end with a bearer token and see the streamed response | 5 min |

## Key Concepts

- **AgentCore Runtime**, managed runtime for deploying and executing agents
- **Router Agent**, receives all requests and routes to the appropriate specialist
- **Specialist Agent**, handles a specific domain (billing, operations, etc.) with its own IAM role
- **JWT Propagation**, the user's identity token flows from the Gateway through the router to the specialist

➡️ After completing this module, proceed to [Module 6: Bedrock Guardrails](/module-6-guardrails)
