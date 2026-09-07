---
title: "Prerequisites"
weight: 11
---

## AWS Account Requirements

- An AWS account with administrator access (or sufficient IAM permissions for Cognito, Lambda, IAM, Bedrock, CloudWatch, X-Ray)
- Region: **us-east-1** (all labs use this region)
- Bedrock model access enabled for Claude Sonnet 4.5 (or the model specified in `config.env`)

## Tools

- Python 3.10 or later
- pip (Python package manager)
- JupyterLab or any Jupyter-compatible notebook environment
- AWS CLI configured with valid credentials (`aws configure`)
- Git (for cloning the workshop repository)

## Setup Steps

**1. Clone the workshop repository:**

:::code{language=bash showCopyAction=true showLineNumbers=false}
git clone <repository-url>
cd workshop-ai-agents-security
:::

**2. Install dependencies:**

:::code{language=bash showCopyAction=true showLineNumbers=false}
pip install -r requirements.txt
:::

**3. Configure your environment:**

:::code{language=bash showCopyAction=true showLineNumbers=false}
cp config.env.example config.env
:::

Edit `config.env` to set your AWS region and any other required values. The labs will populate this file with resource IDs as you progress.

**4. Start JupyterLab:**

:::code{language=bash showCopyAction=true showLineNumbers=false}
jupyter lab
:::

::alert[The first cell in every notebook installs and upgrades boto3 and AgentCore SDK packages. After running it for the first time, restart the kernel (Kernel → Restart) before continuing.]{type="info" header="First-time setup"}

## Knowledge Prerequisites

- Basic familiarity with AWS IAM (roles, policies)
- Basic Python skills (the notebooks are guided, but understanding function calls and JSON structures helps)
- Familiarity with JWT tokens is helpful but not required (Lab 01 explains the relevant concepts)

## No Prior AgentCore Experience Required

Each lab explains the AgentCore concepts before you build them. You do not need prior experience with AgentCore, Cedar, or Bedrock Guardrails.
