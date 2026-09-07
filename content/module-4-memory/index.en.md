---
title: "Module 4: AgentCore Memory"
weight: 50
---

## The Problem

When multiple users interact with the same agent, their session data, extracted facts, and learned preferences must stay separate. If one user's context leaks into another user's session, that is a data exposure incident. Tenant isolation in agent memory is not a feature request — it is a requirement.

## What You Will Build

A managed AgentCore Memory resource with three strategies, all tenant-isolated by design:

- **Semantic Memory**, extracts facts from conversations (e.g., "Ana queried east sector on 05/07")
- **User Preference Memory**, learns user preferences (e.g., "prefers summarized responses")
- **Summary Memory**, rolling session summaries

Each strategy uses a namespace pattern that includes the `actorId` (the user), ensuring that Ana's memory is completely separate from Carlos's memory at the data level.

## Why This Matters

The `actorId` in the namespace is the tenant boundary. When the agent queries memory, it only retrieves data within that user's namespace. This is not application-level filtering, it is built into the data model. Combined with the identity controls from Module 1, the platform guarantees that a user's JWT identity maps to their memory namespace, and no cross-tenant access is possible.

## Labs

| Lab | Title | What You Do | Time |
|---|---|---|---|
| 04.1 | [Create Memory Resource](lab-04-1/) | Create a memory with 3 strategies, understand namespace isolation | 10 min |
| 04.2 | [STM vs LTM and Semantic Search](lab-04-2/) | Record events, search across short-term and long-term memory, test isolation | 10 min |

## Key Concepts

- **STM (Short-Term Memory)**, raw events from the current session, accessed via `create_event` / `list_events`
- **LTM (Long-Term Memory)**, facts and preferences extracted asynchronously by the memory pipeline
- **Namespace**, the path pattern (e.g., `/sector/facts/{actorId}`) that enforces tenant isolation
- **actorId**, maps to the authenticated user's identity, set at runtime from the JWT

➡️ After completing this module, proceed to [Module 5: AgentCore Runtime](/module-5-runtime)
