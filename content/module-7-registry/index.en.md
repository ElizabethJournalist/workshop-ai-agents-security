---
title: "Module 7: Agent Registry"
weight: 80
---

## The Problem

As the number of agents grows, the governance team needs to answer: *Which agents are approved for production? Who published them? When was the last review?* Without a registry, agents are deployed ad-hoc with no lifecycle management, no discoverability, and no way to deprecate an agent that should no longer run.

## What You Will Build

An Agent Registry that provides governance at scale:

- **Registry creation**, a catalog where agents are published with metadata
- **Agent publishing**, register agents with descriptions, capabilities, and status
- **Discovery**, search and browse available agents
- **Lifecycle management**, move agents through states (DRAFT → APPROVED → DEPRECATED)

## Why This Matters

The Registry is the governance layer. Before an agent runs in production, it must be published and approved. When an agent is retired, it is deprecated, the registry preserves the history for audit purposes without deleting the record. This gives the governance team visibility and control over the entire agent fleet.

## Labs

| Lab | Title | What You Do | Time |
|---|---|---|---|
| 07.1 | [Create Registry and Publish Agents](lab-07-1/) | Create a registry, publish agents with metadata | 10 min |
| 07.2 | [Discover and Lifecycle](lab-07-2/) | Search agents, change lifecycle status (APPROVED → DEPRECATED) | 5 min |

## Key Concepts

- **Agent Registry**, managed catalog of agents with metadata and lifecycle state
- **Publishing**, registering an agent with its description, capabilities, and version
- **Discovery**, searching the registry by name, capability, or status
- **Lifecycle States**, DRAFT → APPROVED → DEPRECATED (governance review before production)

➡️ After completing this module, proceed to [Module 8: Observability](/module-8-observability)
