---
title: "Module 1: Identity Foundation"
weight: 20
---

## The Problem

When federated users trigger agent executions, the platform needs to know exactly who they are and what groups they belong to. Without a centralized identity layer, every agent makes its own assumptions about the user, and there is no consistent source of truth for authorization decisions downstream.

In a DIY agent setup, authentication is often handled per-agent or per-tool, creating fragmented identity management that cannot scale. The first step toward governed agentic AI is establishing a single identity foundation that every other component trusts.

## What You Will Build

An Amazon Cognito User Pool that serves as the single source of truth for user identity across the entire agent platform:

- **User Pool** with OAuth 2.0 / OpenID Connect
- **Groups** (`operators`, `managers`, `governance`) that map to JWT claims
- **Test users** with group memberships that produce real JWT tokens
- **Custom claims and scopes** that the Gateway and Cedar will consume in later modules

## Why This Matters

The `cognito:groups` claim in the JWT is what every downstream component depends on. The Gateway checks it during authentication, Cedar uses it for authorization, and the Runtime passes it through to the agent. If this step is wrong, nothing else works.

## Labs

| Lab | Title | What You Do | Time |
|---|---|---|---|
| 01.1 | [Create Cognito User Pool with Groups](lab-01-1/) | Create the pool, groups, and test users programmatically | 5 min |
| 01.2 | [Custom Claims and Allowed Scopes](lab-01-2/) | Create the OAuth app client, examine JWT structure, configure scopes | 10 min |

## Key Concepts

- **Cognito User Pool**, managed identity provider that issues JWTs
- **Groups**, organize users by role; the group name becomes a claim in the token
- **App Client**, the application identity that requests tokens on behalf of users
- **OIDC Discovery**, the endpoint that other services use to validate tokens

➡️ After completing this module, proceed to [Module 2: AgentCore Gateway](/module-2-gateway)
