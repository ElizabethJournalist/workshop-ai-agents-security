---
title: "Module 3: AgentCore Policy (Cedar)"
weight: 40
---

## The Problem

Authentication tells you who the user is. But it does not tell you what they are allowed to do. Without fine-grained authorization, every authenticated user has the same access to every tool, an operator can approve purchase orders, a governance auditor can modify production data, and there is no way to enforce least privilege.

The question enterprises ask: *How do I control which users can call which tools, at the policy level, without hardcoding authorization logic into every agent?*

## What You Will Build

A Cedar-based authorization layer that enforces role-based access control over agent tools:

- **Cedar language fundamentals**, permit/deny policies, conditions, and how Cedar evaluates
- **Policy attachment**, connect Cedar policies to the Gateway so every request is authorized
- **Persona-based testing**, prove that Ana (operator) can access field tools but not management reports, while Carlos (manager) can do the reverse
- **Context-based control**, advanced policies that use runtime context (time of day, request attributes) to make authorization decisions

## Why This Matters

Cedar is the authorization engine for AgentCore. It evaluates every tool invocation against the user's identity (from Module 1), the requested action, and optional context. It runs at the Gateway level (Module 2), so authorization is enforced before the agent even sees the request. This is layered security: Cognito authenticates, Cedar authorizes, and the agent only processes what passes both gates.

## Labs

| Lab | Title | What You Do | Time |
|---|---|---|---|
| 03.1 | [Cedar Language Basics](lab-03-1/) | Learn Cedar syntax, permit, deny, conditions, evaluation order | 10 min |
| 03.2 | [Attach Policies and Enforce](lab-03-2/) | Create and attach Cedar policies to the Gateway | 8 min |
| 03.3 | [Test PERMIT/DENY by Persona](lab-03-3/) | Prove authorization works, Ana vs Carlos accessing different tools | 7 min |
| 03.4 | [Context-Based Control](lab-03-4/) | Advanced: policies that use runtime context for authorization decisions | 5 min |

## Key Concepts

- **Cedar**, AWS's open-source policy language for fine-grained authorization
- **Principal**, the user or agent making the request (identified by JWT claims)
- **Action**, the operation being requested (e.g., `CallTool`)
- **Resource**, the specific tool or target being accessed
- **Context**, additional runtime attributes (time, location, request metadata)

➡️ After completing this module, proceed to [Module 4: AgentCore Memory](/module-4-memory)
