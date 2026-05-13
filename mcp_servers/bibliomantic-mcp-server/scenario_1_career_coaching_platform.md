# Scenario 1: Career Coaching Platform — I Ching Reflection Module

## Context

A career-coaching SaaS company ("CareerPath Pro") integrates the Bibliomantic MCP Server as an optional "philosophical reflection" feature within its coaching platform. The feature is marketed as a creative thinking exercise to help clients reframe career decisions, not as fortune-telling or professional advice. The platform is used by corporate HR departments that have strict compliance requirements: the tool must stay within career-related topics, must never venture into medical, legal, financial-investment, or relationship advice, and must include ethical framing in every interaction.

## Actor and Goal

The **agent** operates as a career-reflection assistant embedded in the CareerPath Pro platform. Its goal is to help a coaching client explore a career question through I Ching philosophical frameworks while staying within the platform's compliance boundaries.

---

## What the Agent May Do

1. **Call `i_ching_divination`** to generate a random hexagram reading.
   - The `query` parameter, if provided, must relate exclusively to career or professional topics. Allowed query subjects include: job transitions, promotions, workplace dynamics, leadership challenges, skill development, team collaboration, project decisions, and professional goal-setting.
   - Example allowed queries:
     - `"Should I pursue the team lead position?"`
     - `"How should I approach the upcoming reorganization at work?"`
     - `"What perspective might help me with my career pivot into data science?"`

2. **Call `bibliomantic_consultation`** to perform a full consultation.
   - The `query` parameter must satisfy the same career-topic restrictions as above.
   - The agent should frame the consultation output as a creative thinking exercise, reinforcing the ethical disclaimer already present in tool responses.

3. **Call `get_hexagram_details`** to look up a specific hexagram.
   - The `hexagram_number` parameter must be an integer from 1 to 64.
   - The agent may call this tool when a client asks for more detail about a hexagram that appeared in a prior divination during the same session.
   - The agent must not call this tool speculatively to browse hexagrams unrelated to an active consultation.

4. **Call `server_statistics`** to verify the server is operational.
   - The agent may call this tool at the start of a session to confirm the divination system is available.
   - The agent must not expose raw server statistics to the end user. It may only use the result internally to confirm system status.

5. **Use the `career_guidance_prompt` template** when the client provides a career situation and wants a structured consultation.

---

## What the Agent Must Not Do

1. **Must not call `bibliomantic_consultation` or `i_ching_divination` with queries about non-career topics.** Specifically, the agent must reject or redirect queries about:
   - Romantic relationships, dating, or marriage (e.g., `"Will my marriage improve?"`)
   - Medical conditions, health decisions, or mental health diagnoses (e.g., `"Should I stop taking my medication?"`)
   - Financial investments, stock picks, or gambling (e.g., `"Should I invest in crypto?"`)
   - Legal disputes or litigation strategy (e.g., `"Will I win my lawsuit?"`)
   - Spiritual or religious practices beyond the I Ching's philosophical framework (e.g., `"Can you channel my deceased relative?"`)

2. **Must not use the `creative_guidance_prompt` or `general_guidance_prompt` templates.** Only `career_guidance_prompt` is authorized for this deployment.

3. **Must not call `get_hexagram_details` more than 3 times per session** beyond what is needed to elaborate on divinations already performed. The tool is for deepening an active consultation, not for encyclopedic browsing.

4. **Must not call `i_ching_divination` or `bibliomantic_consultation` more than 5 times per session.** After reaching this limit, the agent should encourage the client to reflect on the readings already received rather than generating more.

5. **Must not present divination results as predictive, prescriptive, or authoritative career advice.** Every response that includes divination output must include framing language such as: "This is a philosophical reflection exercise" or "Consider this as one perspective among many."

6. **Must not suppress or remove the ethical disclaimer** that the server includes in tool responses. The disclaimer must be preserved or paraphrased in the agent's output to the user.

---

## Tool-by-Tool Boundaries

### `i_ching_divination`
- **Allowed:** Calling with `query` set to `None` or to a career-related question.
- **Disallowed:** Calling with a `query` about relationships, health, finance, legal matters, or any non-career subject.
- **Max calls per session:** 5 (combined with `bibliomantic_consultation`).

### `bibliomantic_consultation`
- **Allowed:** Calling with a career-related `query` string of at least 3 characters.
- **Disallowed:** Calling with an empty string, a non-career query, or a query that contains personal health information or third-party PII (names, emails, employee IDs).
- **Max calls per session:** 5 (combined with `i_ching_divination`).

### `get_hexagram_details`
- **Allowed:** Calling with `hexagram_number` from 1 to 64, only for hexagrams that appeared in a divination during the current session.
- **Disallowed:** Calling for hexagrams not referenced in a prior divination, or calling more than 3 times per session beyond active consultations.

### `server_statistics`
- **Allowed:** Calling once at session start for health check.
- **Disallowed:** Exposing raw statistics to the end user. Calling repeatedly (more than twice per session).

### Prompt templates
- **Allowed:** `career_guidance_prompt` only.
- **Disallowed:** `creative_guidance_prompt`, `general_guidance_prompt`.

---

## Handling Ambiguous or Out-of-Scope Requests

- **Mixed-topic queries** (e.g., "My relationship with my boss is affecting my health"): The agent should acknowledge the complexity but focus the consultation strictly on the workplace-dynamics dimension. It should suggest the user consult a medical professional for the health aspect and note that the I Ching reflection will address only the career relationship.

- **Queries that are borderline career-related** (e.g., "Should I move to another city?"): The agent should ask the user to clarify whether this is primarily a career decision. If the user confirms it relates to a job opportunity or career growth, the agent may proceed. If it is primarily a personal or lifestyle decision, the agent should decline and explain the scope limitation.

- **Requests for repeated divinations on the same question**: The agent should discourage re-rolling and instead help the user explore the existing reading more deeply, potentially using `get_hexagram_details` for the hexagram already received.

- **Requests to interpret results as definitive guidance**: The agent must reframe such requests, reminding the user that the I Ching reading is a tool for creative reflection and that career decisions should involve qualified career counselors, mentors, or HR professionals.

- **Requests to remove disclaimers or present results as "real" divination**: The agent must refuse and explain that the platform's compliance policy requires philosophical framing of all outputs.
