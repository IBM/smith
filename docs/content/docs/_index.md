---
title: "Documentation"
weight: 1
bookFlatSection: true
---

# Smith Documentation

Smith is a skill (plugin) for AI code agents that manages the full lifecycle of [Open Policy Agent (OPA)](https://www.openpolicyagent.org/) policies. It enables agents to:

- **Create** OPA policies from natural language guidance and an agent description.
- **Generate** both synthetic legitimate and adversarial test cases using LLM-based fuzzing and red-teaming tools.
- **Test** policies against generated and custom test suites.
- **Refine** policies automatically through iterative feedback loops.

```
Guidance (NLP) + Agent Description → Policy Creation → Test Generation → Policy Testing ⇄ Policy Refinement
```

## Getting Started

- [Overview]({{< relref "/docs/overview" >}}) — What Smith is and how it works
- [Quickstart]({{< relref "/docs/quickstart" >}}) — Install and run your first policy lifecycle
- [Configuration]({{< relref "/docs/configuration" >}}) — Environment variables and setup
