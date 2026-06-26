# Security Policy

## Supported Versions

| Version | Supported                          |
| ------- | ---------------------------------- |
| `0.1.x` | Yes (current development line)     |
| `< 0.1` | No                                 |

Only the latest patch release of the supported minor version receives fixes.
Smith is pre-`1.0`; APIs and the security model may change between minor versions.

## Reporting a Vulnerability

**Please do not open a public issue for security vulnerabilities.**

Report privately through GitHub's **Private Vulnerability Reporting**:

1. Go to the [Security tab](https://github.com/IBM/smith/security) of the repository.
2. Click **Report a vulnerability** (or use
   <https://github.com/IBM/smith/security/advisories/new>).
3. Provide the details below.

This opens a private advisory visible only to you and the maintainers.

Please include:

- A description of the vulnerability and its impact.
- Steps to reproduce (a minimal proof of concept helps).
- Affected versions and configuration (e.g. which pipeline stage, target agent,
  or model provider).
- Any mitigations or workarounds you have identified.

## Response Process

- We will acknowledge your report, typically within a few business days.
- We will investigate, keep you updated on progress, and coordinate a fix and
  disclosure timeline with you.
- Prior to `v1.0.0` we work with reporters individually on timelines; we will
  credit you in the advisory unless you prefer to remain anonymous.

## Severity Classification

- **Critical** — Remote code execution, or a policy-generation/enforcement bypass
  that defeats Smith's core guarantees (e.g. a generated policy that silently
  permits actions guidance forbids) without user interaction.
- **High** — Privilege escalation, significant data exposure, or leakage of
  secrets/credentials (e.g. API keys from `.env`).
- **Medium** — Information disclosure of limited scope, or denial of service
  requiring sustained effort.
- **Low** — Issues requiring unlikely configurations or with minimal impact.

## Safe Harbor

We consider security research conducted in good faith under this policy to be
authorized. We will not pursue legal action against researchers who follow it
and report findings responsibly. Thank you for helping keep Smith secure.
