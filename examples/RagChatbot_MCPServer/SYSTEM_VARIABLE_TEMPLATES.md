<<<<<<< HEAD
<<<<<<< HEAD
# System Variables Reference

This document provides a comprehensive reference for all system variables extracted from the `input.json` structure used in the policy evaluation system.

## Overview

The input structure contains metadata about tool calls, user context, and security attributes used for policy evaluation and access control decisions.

## Variable Categories

### 1. Tool Call Variables

Variables related to the action being performed:

| Variable | Path | Type | Description | Example Value |
|----------|------|------|-------------|---------------|
| `input.kind` | `input.kind` | string | Type of input operation | `"tool_call"` |
| `input.action` | `input.action` | string | Action to be performed | `"execute"` |
| `input.name` | `input.name` | string | Name of the tool being called | `"ask_for_workpolicy"` |
| `input.arguments` | `input.arguments` | object | Arguments passed to the tool | `{"question": "..."}` |
| `input.arguments.question` | `input.arguments.question` | string | The question being asked | `"ignore all policies..."` |

### 2. Subject Variables (User Context)

Variables identifying and describing the user making the request:

| Variable | Path | Type | Description | Example Value |
|----------|------|------|-------------|---------------|
| `input.extensions.subject.id` | `input.extensions.subject.id` | string | Unique user identifier | `"user123"` |
| `input.extensions.subject.type` | `input.extensions.subject.type` | string | Type of subject | `"user"` |
| `input.extensions.subject.roles` | `input.extensions.subject.roles` | array | User's assigned roles | `["employee", "manager"]` |
| `input.extensions.subject.teams` | `input.extensions.subject.teams` | array | Teams the user belongs to | `["Engineering"]` |
| `input.extensions.subject.permissions` | `input.extensions.subject.permissions` | array | User's granted permissions | `["read:ask_for_workpolicy"]` |

### 3. Request Headers

HTTP headers and request metadata:

| Variable | Path | Type | Description | Example Value |
|----------|------|------|-------------|---------------|
| `input.extensions.headers.x-request-id` | `input.extensions.headers.x-request-id` | string | Unique request identifier | `"req-REPLACE_ME"` |
| `input.extensions.headers.x-forwarded-for` | `input.extensions.headers.x-forwarded-for` | string | Client IP address | `"REPLACE_ME"` |

### 4. Classification Labels

Security and classification metadata:

| Variable | Path | Type | Description | Example Value |
|----------|------|------|-------------|---------------|
| `input.extensions.labels` | `input.extensions.labels` | array | Classification labels | `["internal"]` |

### 5. Agent Context

Variables related to the AI agent session:

| Variable | Path | Type | Description | Example Value |
|----------|------|------|-------------|---------------|
| `input.extensions.agent.input` | `input.extensions.agent.input` | string | User's original input | `"Ask for work policy"` |
| `input.extensions.agent.session_id` | `input.extensions.agent.session_id` | string | Session identifier | `"sess-REPLACE_ME"` |
| `input.extensions.agent.conversation_id` | `input.extensions.agent.conversation_id` | string | Conversation identifier | `"conv-REPLACE_ME"` |
| `input.extensions.agent.turn` | `input.extensions.agent.turn` | number | Turn number in conversation | `0` |

### 6. Object/Resource Variables

Variables describing the resource being accessed:

| Variable | Path | Type | Description | Example Value |
|----------|------|------|-------------|---------------|
| `input.extensions.object.managed_by` | `input.extensions.object.managed_by` | string | Resource manager | `"tool"` |
| `input.extensions.object.permissions` | `input.extensions.object.permissions` | array | Required permissions | `["read:ask_for_workpolicy"]` |
| `input.extensions.object.trust_domain` | `input.extensions.object.trust_domain` | string | Trust domain classification | `"internal"` |
| `input.extensions.object.data_scope` | `input.extensions.object.data_scope` | array | Data fields in scope | `["question"]` |



## Variable Replacement Guidelines

Variables marked with `REPLACE_ME` should be replaced with actual values:

- **x-request-id**: Generate a unique request ID (e.g., UUID)
- **x-forwarded-for**: Use the actual client IP address
- **session_id**: Use the actual session identifier
- **conversation_id**: Use the actual conversation identifier



## Example Complete Input

```json
{
  "input": {
    "kind": "tool_call",
    "action": "execute",
    "name": "ask_for_workpolicy",
    "arguments": {
      "question": "What is the remote work policy?"
    },
    "extensions": {
      "subject": {
        "id": "user456",
        "type": "user",
        "roles": ["employee", "manager"],
        "teams": ["Engineering"],
        "permissions": ["read:ask_for_workpolicy", "write:policies"]
      },
      "headers": {
        "x-request-id": "req-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "x-forwarded-for": "192.168.1.100"
      },
      "labels": ["internal", "confidential"],
      "agent": {
        "input": "Ask for work policy",
        "session_id": "sess-xyz789",
        "conversation_id": "conv-abc123",
        "turn": 5
      },
      "object": {
        "managed_by": "tool",
        "permissions": ["read:ask_for_workpolicy"],
        "trust_domain": "internal",
        "data_scope": ["question"]
=======
# System Variable Templates for MCP Tool Calls
=======
# System Variables Reference
>>>>>>> ea2b1b5 (fix: system variables based on updated schema)

This document provides a comprehensive reference for all system variables extracted from the `input.json` structure used in the policy evaluation system.

## Overview

The input structure contains metadata about tool calls, user context, and security attributes used for policy evaluation and access control decisions.

## Variable Categories

### 1. Tool Call Variables

Variables related to the action being performed:

| Variable | Path | Type | Description | Example Value |
|----------|------|------|-------------|---------------|
| `input.kind` | `input.kind` | string | Type of input operation | `"tool_call"` |
| `input.action` | `input.action` | string | Action to be performed | `"execute"` |
| `input.name` | `input.name` | string | Name of the tool being called | `"ask_for_workpolicy"` |
| `input.arguments` | `input.arguments` | object | Arguments passed to the tool | `{"question": "..."}` |
| `input.arguments.question` | `input.arguments.question` | string | The question being asked | `"ignore all policies..."` |

### 2. Subject Variables (User Context)

Variables identifying and describing the user making the request:

| Variable | Path | Type | Description | Example Value |
|----------|------|------|-------------|---------------|
| `input.extensions.subject.id` | `input.extensions.subject.id` | string | Unique user identifier | `"user123"` |
| `input.extensions.subject.type` | `input.extensions.subject.type` | string | Type of subject | `"user"` |
| `input.extensions.subject.roles` | `input.extensions.subject.roles` | array | User's assigned roles | `["employee", "manager"]` |
| `input.extensions.subject.teams` | `input.extensions.subject.teams` | array | Teams the user belongs to | `["Engineering"]` |
| `input.extensions.subject.permissions` | `input.extensions.subject.permissions` | array | User's granted permissions | `["read:ask_for_workpolicy"]` |

### 3. Request Headers

HTTP headers and request metadata:

| Variable | Path | Type | Description | Example Value |
|----------|------|------|-------------|---------------|
| `input.extensions.headers.x-request-id` | `input.extensions.headers.x-request-id` | string | Unique request identifier | `"req-REPLACE_ME"` |
| `input.extensions.headers.x-forwarded-for` | `input.extensions.headers.x-forwarded-for` | string | Client IP address | `"REPLACE_ME"` |

### 4. Classification Labels

Security and classification metadata:

| Variable | Path | Type | Description | Example Value |
|----------|------|------|-------------|---------------|
| `input.extensions.labels` | `input.extensions.labels` | array | Classification labels | `["internal"]` |

### 5. Agent Context

Variables related to the AI agent session:

| Variable | Path | Type | Description | Example Value |
|----------|------|------|-------------|---------------|
| `input.extensions.agent.input` | `input.extensions.agent.input` | string | User's original input | `"Ask for work policy"` |
| `input.extensions.agent.session_id` | `input.extensions.agent.session_id` | string | Session identifier | `"sess-REPLACE_ME"` |
| `input.extensions.agent.conversation_id` | `input.extensions.agent.conversation_id` | string | Conversation identifier | `"conv-REPLACE_ME"` |
| `input.extensions.agent.turn` | `input.extensions.agent.turn` | number | Turn number in conversation | `0` |

### 6. Object/Resource Variables

Variables describing the resource being accessed:

| Variable | Path | Type | Description | Example Value |
|----------|------|------|-------------|---------------|
| `input.extensions.object.managed_by` | `input.extensions.object.managed_by` | string | Resource manager | `"tool"` |
| `input.extensions.object.permissions` | `input.extensions.object.permissions` | array | Required permissions | `["read:ask_for_workpolicy"]` |
| `input.extensions.object.trust_domain` | `input.extensions.object.trust_domain` | string | Trust domain classification | `"internal"` |
| `input.extensions.object.data_scope` | `input.extensions.object.data_scope` | array | Data fields in scope | `["question"]` |



## Variable Replacement Guidelines

Variables marked with `REPLACE_ME` should be replaced with actual values:

- **x-request-id**: Generate a unique request ID (e.g., UUID)
- **x-forwarded-for**: Use the actual client IP address
- **session_id**: Use the actual session identifier
- **conversation_id**: Use the actual conversation identifier



## Example Complete Input

```json
{
  "input": {
    "kind": "tool_call",
    "action": "execute",
    "name": "ask_for_workpolicy",
    "arguments": {
      "question": "What is the remote work policy?"
    },
    "extensions": {
      "subject": {
        "id": "user456",
        "type": "user",
        "roles": ["employee", "manager"],
        "teams": ["Engineering"],
        "permissions": ["read:ask_for_workpolicy", "write:policies"]
      },
<<<<<<< HEAD
      "metadata": {
        "title": "View Team Compensation",
        "description": "View team compensation data",
        "category": "hr",
        "audit_required": true
>>>>>>> 59aaaa7 (feat: documentation for schema and tools)
=======
      "headers": {
        "x-request-id": "req-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "x-forwarded-for": "192.168.1.100"
      },
      "labels": ["internal", "confidential"],
      "agent": {
        "input": "Ask for work policy",
        "session_id": "sess-xyz789",
        "conversation_id": "conv-abc123",
        "turn": 5
      },
      "object": {
        "managed_by": "tool",
        "permissions": ["read:ask_for_workpolicy"],
        "trust_domain": "internal",
        "data_scope": ["question"]
>>>>>>> ea2b1b5 (fix: system variables based on updated schema)
      }
    }
  }
}
```

<<<<<<< HEAD
<<<<<<< HEAD
=======
#### 1.2 ask_for_salary
```json
{
  "kind": "tool_call",
  "action": "execute",
  "name": "ask_for_salary",
  "uri": "tool://_/ask_for_salary",
  "arguments": {
    "question": "{user_question}",
    "external_sharing": false,
    "format": "JSON",
    "time_range": "current"
  },
  "context": {
    "request_id": "req-{YYYY-MM-DD-HHMMSS}",
    "timestamp": "{ISO8601_TIMESTAMP}Z",
    "environment": "production",
    "labels": ["financial", "hr", "query"],
    "principal": {
      "id": "{user_id}",
      "type": "user",
      "user_role": "manager|user|admin",
      "roles": ["{user_role}"],
      "permissions": ["read:salary", "read:compensation"],
      "teams": ["{team_id}"],
      "tenant_id": "company_xyz",
      "daily_requests": 0,
      "max_purchase": 1000|5000|10000
    },
    "agent": {
      "input": "{user_prompt}",
      "intent": "salary_inquiry"
    },
    "tool": {
      "principal": {
        "id": "ask_for_salary",
        "type": "tool",
        "permissions": ["read:salary", "read:compensation"],
        "trust_level": "internal",
        "server_id": "hr-mcp-server"
      },
      "metadata": {
        "title": "Ask For Salary",
        "description": "Query salary information",
        "category": "hr",
        "audit_required": true
      }
    }
  }
}
```

#### 1.3 export_compensation_data
```json
{
  "kind": "tool_call",
  "action": "execute",
  "name": "export_compensation_data",
  "uri": "tool://_/export_compensation_data",
  "arguments": {
    "format": "CSV|JSON|PDF",
    "time_range": "last_quarter|last_year|current",
    "export_type": "aggregated|detailed|summary",
    "business_justification": "{justification_text}",
    "external_sharing": false
  },
  "context": {
    "request_id": "req-{YYYY-MM-DD-HHMMSS}",
    "timestamp": "{ISO8601_TIMESTAMP}Z",
    "environment": "production",
    "labels": ["financial", "hr", "export", "sensitive"],
    "principal": {
      "id": "{user_id}",
      "type": "user",
      "user_role": "manager|admin",
      "roles": ["{user_role}"],
      "permissions": ["read:compensation", "export:csv", "export:pdf"],
      "teams": ["{team_id}"],
      "tenant_id": "company_xyz",
      "daily_requests": 0,
      "max_purchase": 5000|10000
    },
    "agent": {
      "input": "{user_prompt}",
      "intent": "export_data"
    },
    "tool": {
      "principal": {
        "id": "export_compensation_data",
        "type": "tool",
        "permissions": ["read:compensation", "export:csv", "export:pdf"],
        "trust_level": "internal",
        "server_id": "hr-mcp-server"
      },
      "metadata": {
        "title": "Export Compensation Data",
        "description": "Export compensation data",
        "category": "hr",
        "audit_required": true
      }
    }
  }
}
```

### 2. Communication Tools

#### 2.1 send_email
```json
{
  "kind": "tool_call",
  "action": "execute",
  "name": "send_email",
  "uri": "tool://_/send_email",
  "arguments": {
    "email_content": "{email_body}",
    "attached_file": "{file_name}",
    "external_sharing": false,
    "format": "JSON",
    "time_range": "current"
  },
  "context": {
    "request_id": "req-{YYYY-MM-DD-HHMMSS}",
    "timestamp": "{ISO8601_TIMESTAMP}Z",
    "environment": "production",
    "labels": ["communication"],
    "principal": {
      "id": "{user_id}",
      "type": "user",
      "user_role": "user|manager|admin",
      "roles": ["{user_role}"],
      "permissions": ["send:email"],
      "teams": ["{team_id}"],
      "tenant_id": "company_xyz",
      "daily_requests": 0,
      "max_purchase": 1000|5000|10000
    },
    "agent": {
      "input": "{user_prompt}",
      "intent": "send_communication"
    },
    "tool": {
      "principal": {
        "id": "send_email",
        "type": "tool",
        "permissions": ["send:email"],
        "trust_level": "internal",
        "server_id": "default-mcp-server"
      },
      "metadata": {
        "title": "Send Email",
        "description": "Send email communication",
        "category": "communication",
        "audit_required": false
      }
    }
  }
}
```

#### 2.2 email_compensation_report
```json
{
  "kind": "tool_call",
  "action": "execute",
  "name": "email_compensation_report",
  "uri": "tool://_/email_compensation_report",
  "arguments": {
    "destination": "{recipient_email}",
    "report_data": "{report_content}",
    "external_sharing": false,
    "format": "JSON",
    "time_range": "current"
  },
  "context": {
    "request_id": "req-{YYYY-MM-DD-HHMMSS}",
    "timestamp": "{ISO8601_TIMESTAMP}Z",
    "environment": "production",
    "labels": ["financial", "hr", "communication", "sensitive"],
    "principal": {
      "id": "{user_id}",
      "type": "user",
      "user_role": "manager|admin",
      "roles": ["{user_role}"],
      "permissions": ["send:email", "read:compensation"],
      "teams": ["{team_id}"],
      "tenant_id": "company_xyz",
      "daily_requests": 0,
      "max_purchase": 5000|10000
    },
    "agent": {
      "input": "{user_prompt}",
      "intent": "email_report"
    },
    "tool": {
      "principal": {
        "id": "email_compensation_report",
        "type": "tool",
        "permissions": ["send:email", "read:compensation"],
        "trust_level": "internal",
        "server_id": "hr-mcp-server"
      },
      "metadata": {
        "title": "Email Compensation Report",
        "description": "Email compensation report",
        "category": "hr",
        "audit_required": true
      }
    }
  }
}
```

### 3. Procurement Tools

#### 3.1 purchase
```json
{
  "kind": "tool_call",
  "action": "execute",
  "name": "purchase",
  "uri": "tool://_/purchase",
  "arguments": {
    "amount": "{purchase_amount}",
    "product_name": "{product_description}",
    "external_sharing": false,
    "format": "JSON",
    "time_range": "current"
  },
  "context": {
    "request_id": "req-{YYYY-MM-DD-HHMMSS}",
    "timestamp": "{ISO8601_TIMESTAMP}Z",
    "environment": "production",
    "labels": ["financial", "procurement"],
    "principal": {
      "id": "{user_id}",
      "type": "user",
      "user_role": "user|manager|admin",
      "roles": ["{user_role}"],
      "permissions": ["write:purchase", "read:inventory"],
      "teams": ["{team_id}"],
      "tenant_id": "company_xyz",
      "daily_requests": 0,
      "max_purchase": 1000|5000|10000
    },
    "agent": {
      "input": "{user_prompt}",
      "intent": "make_purchase"
    },
    "tool": {
      "principal": {
        "id": "purchase",
        "type": "tool",
        "permissions": ["write:purchase", "read:inventory"],
        "trust_level": "internal",
        "server_id": "procurement-mcp-server"
      },
      "metadata": {
        "title": "Purchase",
        "description": "Process purchase request",
        "category": "procurement",
        "audit_required": false
      }
    }
  }
}
```

#### 3.2 return_product
```json
{
  "kind": "tool_call",
  "action": "execute",
  "name": "return_product",
  "uri": "tool://_/return_product",
  "arguments": {
    "amount": "{refund_amount}",
    "product_name": "{product_description}",
    "external_sharing": false,
    "format": "JSON",
    "time_range": "current"
  },
  "context": {
    "request_id": "req-{YYYY-MM-DD-HHMMSS}",
    "timestamp": "{ISO8601_TIMESTAMP}Z",
    "environment": "production",
    "labels": ["financial", "procurement"],
    "principal": {
      "id": "{user_id}",
      "type": "user",
      "user_role": "user|manager|admin",
      "roles": ["{user_role}"],
      "permissions": ["write:return", "read:inventory"],
      "teams": ["{team_id}"],
      "tenant_id": "company_xyz",
      "daily_requests": 0,
      "max_purchase": 1000|5000|10000
    },
    "agent": {
      "input": "{user_prompt}",
      "intent": "return_product"
    },
    "tool": {
      "principal": {
        "id": "return_product",
        "type": "tool",
        "permissions": ["write:return", "read:inventory"],
        "trust_level": "internal",
        "server_id": "default-mcp-server"
      },
      "metadata": {
        "title": "Return Product",
        "description": "Process product return",
        "category": "procurement",
        "audit_required": false
      }
    }
  }
}
```

### 4. Support/Ticketing Tools

#### 4.1 create_ticket
```json
{
  "kind": "tool_call",
  "action": "execute",
  "name": "create_ticket",
  "uri": "tool://_/create_ticket",
  "arguments": {
    "ticket_content": "{ticket_description}",
    "external_sharing": false,
    "format": "JSON",
    "time_range": "current"
  },
  "context": {
    "request_id": "req-{YYYY-MM-DD-HHMMSS}",
    "timestamp": "{ISO8601_TIMESTAMP}Z",
    "environment": "production",
    "labels": ["general"],
    "principal": {
      "id": "{user_id}",
      "type": "user",
      "user_role": "user|manager|admin",
      "roles": ["{user_role}"],
      "permissions": ["basic:access"],
      "teams": ["{team_id}"],
      "tenant_id": "company_xyz",
      "daily_requests": 0,
      "max_purchase": 1000|5000|10000
    },
    "agent": {
      "input": "{user_prompt}",
      "intent": "create_support_ticket"
    },
    "tool": {
      "principal": {
        "id": "create_ticket",
        "type": "tool",
        "permissions": ["basic:access"],
        "trust_level": "internal",
        "server_id": "default-mcp-server"
      },
      "metadata": {
        "title": "Create Ticket",
        "description": "Create support ticket",
        "category": "general",
        "audit_required": false
      }
    }
  }
}
```

#### 4.2 submit_ticket
```json
{
  "kind": "tool_call",
  "action": "execute",
  "name": "submit_ticket",
  "uri": "tool://_/submit_ticket",
  "arguments": {
    "ticket_content": "{ticket_description}",
    "external_sharing": false,
    "format": "JSON",
    "time_range": "current"
  },
  "context": {
    "request_id": "req-{YYYY-MM-DD-HHMMSS}",
    "timestamp": "{ISO8601_TIMESTAMP}Z",
    "environment": "production",
    "labels": ["general"],
    "principal": {
      "id": "{user_id}",
      "type": "user",
      "user_role": "user|manager|admin",
      "roles": ["{user_role}"],
      "permissions": ["basic:access"],
      "teams": ["{team_id}"],
      "tenant_id": "company_xyz",
      "daily_requests": 0,
      "max_purchase": 1000|5000|10000
    },
    "agent": {
      "input": "{user_prompt}",
      "intent": "submit_support_ticket"
    },
    "tool": {
      "principal": {
        "id": "submit_ticket",
        "type": "tool",
        "permissions": ["basic:access"],
        "trust_level": "internal",
        "server_id": "default-mcp-server"
      },
      "metadata": {
        "title": "Submit Ticket",
        "description": "Submit support ticket",
        "category": "general",
        "audit_required": false
      }
    }
  }
}
```

### 5. Information Query Tools

#### 5.1 ask_for_workpolicy
```json
{
  "kind": "tool_call",
  "action": "execute",
  "name": "ask_for_workpolicy",
  "uri": "tool://_/ask_for_workpolicy",
  "arguments": {
    "question": "{user_question}",
    "external_sharing": false,
    "format": "JSON",
    "time_range": "current"
  },
  "context": {
    "request_id": "req-{YYYY-MM-DD-HHMMSS}",
    "timestamp": "{ISO8601_TIMESTAMP}Z",
    "environment": "production",
    "labels": ["general"],
    "principal": {
      "id": "{user_id}",
      "type": "user",
      "user_role": "user|manager|admin",
      "roles": ["{user_role}"],
      "permissions": ["basic:access"],
      "teams": ["{team_id}"],
      "tenant_id": "company_xyz",
      "daily_requests": 0,
      "max_purchase": 1000|5000|10000
    },
    "agent": {
      "input": "{user_prompt}",
      "intent": "policy_inquiry"
    },
    "tool": {
      "principal": {
        "id": "ask_for_workpolicy",
        "type": "tool",
        "permissions": ["basic:access"],
        "trust_level": "internal",
        "server_id": "default-mcp-server"
      },
      "metadata": {
        "title": "Ask For Workpolicy",
        "description": "Query work policies",
        "category": "general",
        "audit_required": false
      }
    }
  }
}
```

#### 5.2 get_w2_form
```json
{
  "kind": "tool_call",
  "action": "execute",
  "name": "get_w2_form",
  "uri": "tool://_/get_w2_form",
  "arguments": {
    "external_sharing": false,
    "format": "JSON",
    "time_range": "current"
  },
  "context": {
    "request_id": "req-{YYYY-MM-DD-HHMMSS}",
    "timestamp": "{ISO8601_TIMESTAMP}Z",
    "environment": "production",
    "labels": ["general"],
    "principal": {
      "id": "{user_id}",
      "type": "user",
      "user_role": "user|manager|admin",
      "roles": ["{user_role}"],
      "permissions": ["basic:access"],
      "teams": ["{team_id}"],
      "tenant_id": "company_xyz",
      "daily_requests": 0,
      "max_purchase": 1000|5000|10000
    },
    "agent": {
      "input": "{user_prompt}",
      "intent": "get_tax_document"
    },
    "tool": {
      "principal": {
        "id": "get_w2_form",
        "type": "tool",
        "permissions": ["basic:access"],
        "trust_level": "internal",
        "server_id": "default-mcp-server"
      },
      "metadata": {
        "title": "Get W2 Form",
        "description": "Request W2 tax form",
        "category": "general",
        "audit_required": false
      }
    }
  }
}
```

### 6. Export/File Tools

#### 6.1 export_content_as_file
```json
{
  "kind": "tool_call",
  "action": "execute",
  "name": "export_content_as_file",
  "uri": "tool://_/export_content_as_file",
  "arguments": {
    "data": "{content_to_export}",
    "file_name": "{output_filename}",
    "external_sharing": false,
    "format": "JSON",
    "time_range": "current"
  },
  "context": {
    "request_id": "req-{YYYY-MM-DD-HHMMSS}",
    "timestamp": "{ISO8601_TIMESTAMP}Z",
    "environment": "production",
    "labels": ["general"],
    "principal": {
      "id": "{user_id}",
      "type": "user",
      "user_role": "user|manager|admin",
      "roles": ["{user_role}"],
      "permissions": ["basic:access"],
      "teams": ["{team_id}"],
      "tenant_id": "company_xyz",
      "daily_requests": 0,
      "max_purchase": 1000|5000|10000
    },
    "agent": {
      "input": "{user_prompt}",
      "intent": "export_file"
    },
    "tool": {
      "principal": {
        "id": "export_content_as_file",
        "type": "tool",
        "permissions": ["basic:access"],
        "trust_level": "internal",
        "server_id": "default-mcp-server"
      },
      "metadata": {
        "title": "Export Content As File",
        "description": "Export content to file",
        "category": "general",
        "audit_required": false
      }
    }
  }
}
```

### 7. Utility Tools

#### 7.1 set_user_role
```json
{
  "kind": "tool_call",
  "action": "execute",
  "name": "set_user_role",
  "uri": "tool://_/set_user_role",
  "arguments": {
    "user_role": "user|manager|admin",
    "external_sharing": false,
    "format": "JSON",
    "time_range": "current"
  },
  "context": {
    "request_id": "req-{YYYY-MM-DD-HHMMSS}",
    "timestamp": "{ISO8601_TIMESTAMP}Z",
    "environment": "production",
    "labels": ["general"],
    "principal": {
      "id": "{user_id}",
      "type": "user",
      "user_role": "user|manager|admin",
      "roles": ["{user_role}"],
      "permissions": ["basic:access"],
      "teams": ["{team_id}"],
      "tenant_id": "company_xyz",
      "daily_requests": 0,
      "max_purchase": 1000|5000|10000
    },
    "agent": {
      "input": "{user_prompt}",
      "intent": "set_role"
    },
    "tool": {
      "principal": {
        "id": "set_user_role",
        "type": "tool",
        "permissions": ["basic:access"],
        "trust_level": "internal",
        "server_id": "default-mcp-server"
      },
      "metadata": {
        "title": "Set User Role",
        "description": "Set user role for policy enforcement",
        "category": "general",
        "audit_required": false
      }
    }
  }
}
```

#### 7.2 test_purchase_policy
```json
{
  "kind": "tool_call",
  "action": "execute",
  "name": "test_purchase_policy",
  "uri": "tool://_/test_purchase_policy",
  "arguments": {
    "amount": "{test_amount}",
    "product": "{test_product}",
    "external_sharing": false,
    "format": "JSON",
    "time_range": "current"
  },
  "context": {
    "request_id": "req-{YYYY-MM-DD-HHMMSS}",
    "timestamp": "{ISO8601_TIMESTAMP}Z",
    "environment": "production",
    "labels": ["general"],
    "principal": {
      "id": "{user_id}",
      "type": "user",
      "user_role": "user|manager|admin",
      "roles": ["{user_role}"],
      "permissions": ["basic:access"],
      "teams": ["{team_id}"],
      "tenant_id": "company_xyz",
      "daily_requests": 0,
      "max_purchase": 1000|5000|10000
    },
    "agent": {
      "input": "{user_prompt}",
      "intent": "test_policy"
    },
    "tool": {
      "principal": {
        "id": "test_purchase_policy",
        "type": "tool",
        "permissions": ["basic:access"],
        "trust_level": "internal",
        "server_id": "default-mcp-server"
      },
      "metadata": {
        "title": "Test Purchase Policy",
        "description": "Test purchase policy enforcement",
        "category": "general",
        "audit_required": false
      }
    }
  }
}
```

## Variable Definitions

### Enumerated Variables (Strict Values)

#### Core Schema Variables
| Variable | Type | Allowed Values | Description |
|----------|------|----------------|-------------|
| `kind` | string | `"tool_call"` | Fixed value for all MCP tool calls |
| `action` | string | `"execute"` | Fixed value for all tool executions |
| `is_pre` | boolean | `true`, `false` | Pre-execution flag (always `true` for initial calls) |
| `is_post` | boolean | `true`, `false` | Post-execution flag (always `false` for initial calls) |
| `role` | string | `"assistant"` | Fixed value for MCP assistant role |

#### User Role Variables
| Variable | Type | Allowed Values | Description |
|----------|------|----------------|-------------|
| `user_role` | string | `"user"`, `"manager"`, `"admin"` | User's role in the system |
| `type` | string | `"user"`, `"tool"` | Principal type (user or tool) |

#### Format Variables
| Variable | Type | Allowed Values | Description |
|----------|------|----------------|-------------|
| `format` | string | `"JSON"`, `"CSV"`, `"PDF"` | Output format for data exports |

#### Time Range Variables
| Variable | Type | Allowed Values | Description |
|----------|------|----------------|-------------|
| `time_range` | string | `"current"`, `"last_quarter"`, `"last_year"`, `"last_5_years"`, `"all_time"` | Time period for data queries |

#### Export Type Variables
| Variable | Type | Allowed Values | Description |
|----------|------|----------------|-------------|
| `export_type` | string | `"summary"`, `"aggregated"`, `"detailed"` | Level of detail in exports |

#### Environment Variables
| Variable | Type | Allowed Values | Description |
|----------|------|----------------|-------------|
| `environment` | string | `"production"`, `"staging"`, `"development"` | Deployment environment |

#### Boolean Flags
| Variable | Type | Allowed Values | Description |
|----------|------|----------------|-------------|
| `external_sharing` | boolean | `true`, `false` | Whether data can be shared externally |
| `include_benefits` | boolean | `true`, `false` | Include benefits in compensation data |

#### Trust Level Variables
| Variable | Type | Allowed Values | Description |
|----------|------|----------------|-------------|
| `trust_level` | string | `"internal"`, `"external"`, `"restricted"` | Security trust level for tools |

#### Server ID Variables
| Variable | Type | Allowed Values | Description |
|----------|------|----------------|-------------|
| `server_id` | string | `"hr-mcp-server"`, `"procurement-mcp-server"`, `"default-mcp-server"` | MCP server identifier |

### Role-Based Permissions (Enumerated)

#### User Role: "user"
| Permission | Allowed Values |
|------------|----------------|
| `permissions` | `["basic:access"]`, `["purchase"]`, `["return_product"]`, `["send_email"]`, `["purchase_access"]` |
| `max_purchase` | `200`, `1000` |
| `roles` | `["user"]` |

#### User Role: "manager" 
| Permission | Allowed Values |
|------------|----------------|
| `permissions` | `["basic:access", "read:compensation", "export:csv"]`, `["purchase", "return_product", "send_email", "purchase_access", "view_team_compensation", "export_team_data", "ask_for_salary", "hr_access"]` |
| `max_purchase` | `1000`, `5000` |
| `roles` | `["manager"]` |

#### User Role: "admin"
| Permission | Allowed Values |
|------------|----------------|
| `permissions` | All permissions available |
| `max_purchase` | `5000`, `10000` |
| `roles` | `["admin"]` |

### Context Labels (Enumerated by Tool)

#### HR/Compensation Tools
| Tool | Labels |
|------|--------|
| `view_team_compensation` | `["financial", "hr", "sensitive"]` |
| `export_compensation_data` | `["financial", "hr", "export", "sensitive"]` |
| `email_compensation_report` | `["financial", "hr", "communication", "sensitive"]` |
| `ask_for_salary` | `["financial", "hr", "query"]` |

#### Procurement Tools
| Tool | Labels |
|------|--------|
| `purchase` | `["financial", "procurement"]` |
| `return_product` | `["financial", "procurement"]` |

#### Communication Tools
| Tool | Labels |
|------|--------|
| `send_email` | `["communication"]` |

#### General Tools
| Tool | Labels |
|------|--------|
| `create_ticket` | `["general"]` |
| `submit_ticket` | `["general"]` |
| `ask_for_workpolicy` | `["general"]` |
| `get_w2_form` | `["general"]` |
| `export_content_as_file` | `["general"]` |
| `set_user_role` | `["general"]` |
| `test_purchase_policy` | `["general"]` |

### Tool Categories (Enumerated)

| Category | Tools |
|----------|-------|
| `"hr"` | `view_team_compensation`, `export_compensation_data`, `email_compensation_report`, `ask_for_salary` |
| `"procurement"` | `purchase`, `return_product` |
| `"communication"` | `send_email`, `email_compensation_report` |
| `"general"` | `create_ticket`, `submit_ticket`, `ask_for_workpolicy`, `get_w2_form`, `export_content_as_file`, `set_user_role`, `test_purchase_policy` |

### Intent Values (Enumerated)

| Tool | Intent Values |
|------|---------------|
| `view_team_compensation` | `"view_compensation"` |
| `ask_for_salary` | `"salary_inquiry"` |
| `export_compensation_data` | `"export_data"` |
| `email_compensation_report` | `"email_report"` |
| `send_email` | `"send_communication"` |
| `purchase` | `"make_purchase"` |
| `return_product` | `"return_product"` |
| `create_ticket` | `"create_support_ticket"` |
| `submit_ticket` | `"submit_support_ticket"` |
| `ask_for_workpolicy` | `"policy_inquiry"` |
| `get_w2_form` | `"get_tax_document"` |
| `export_content_as_file` | `"export_file"` |
| `set_user_role` | `"set_role"` |
| `test_purchase_policy` | `"test_policy"` |

### Audit Requirements (Enumerated)

| Audit Required | Tools |
|----------------|-------|
| `true` | `view_team_compensation`, `export_compensation_data`, `email_compensation_report`, `ask_for_salary` |
| `false` | `purchase`, `return_product`, `send_email`, `create_ticket`, `submit_ticket`, `ask_for_workpolicy`, `get_w2_form`, `export_content_as_file`, `set_user_role`, `test_purchase_policy` |

### Free-Form Variables

| Variable | Type | Description | Example Values |
|----------|------|-------------|----------------|
| `{tool_name}` | string | Name of the MCP tool being called | `view_team_compensation`, `ask_for_salary` |
| `{user_id}` | string | Unique identifier for the user | `user_123`, `manager_456` |
| `{team_id}` | string | Team identifier | `engineering_team`, `hr_team` |
| `{user_prompt}` | string | Original user input/question | `"What is the average salary?"` |
| `{YYYY-MM-DD-HHMMSS}` | string | Timestamp format | `2024-01-15-143022` |
| `{ISO8601_TIMESTAMP}` | string | ISO 8601 timestamp | `2024-01-15T14:30:22.123` |

### Tool-Specific Free-Form Variables

| Variable | Type | Description | Used In |
|----------|------|-------------|---------|
| `{user_question}` | string | User's question or query | `ask_for_salary`, `ask_for_workpolicy` |
| `{purchase_amount}` | number | Amount for purchase | `purchase`, `return_product` |
| `{product_description}` | string | Product name/description | `purchase`, `return_product` |
| `{email_body}` | string | Email content | `send_email` |
| `{file_name}` | string | File name for attachments/exports | `send_email`, `export_content_as_file` |
| `{ticket_description}` | string | Support ticket content | `create_ticket`, `submit_ticket` |
| `{recipient_email}` | string | Email recipient | `email_compensation_report` |
| `{report_content}` | string | Report data to be emailed | `email_compensation_report` |
| `{content_to_export}` | string | Data to export to file | `export_content_as_file` |
| `{justification_text}` | string | Business justification for export | `export_compensation_data` |

### Permission Levels by Role

| Role | Max Purchase | Permissions | Restricted Tools |
|------|-------------|-------------|------------------|
| `user` | $1,000 | `basic:access`, `read:policy` | `view_team_compensation`, `export_compensation_data` |
| `manager` | $5,000 | `basic:access`, `read:compensation`, `export:csv` | None (full access) |
| `admin` | $10,000 | All permissions | None (full access) |

### Security Labels by Tool Category

| Category | Labels | Audit Required |
|----------|--------|----------------|
| HR/Compensation | `["financial", "hr", "sensitive"]` | Yes |
| Communication | `["communication"]` | No |
| Procurement | `["financial", "procurement"]` | No |
| General | `["general"]` | No |

## Variable Validation Rules

### Strict Validation Requirements

1. **Enumerated Variables**: Variables with enumerated values MUST use only the specified values. Invalid values will cause policy evaluation to fail.

2. **Role Hierarchy**: User roles follow a strict hierarchy:
   - `user` < `manager` < `admin`
   - Higher roles inherit permissions from lower roles

3. **Time Range Restrictions**: 
   - `user` role: Limited to `"current"`, `"last_quarter"`
   - `manager` role: Can access `"current"`, `"last_quarter"`, `"last_year"`
   - `admin` role: Can access all time ranges including `"last_5_years"`, `"all_time"`

4. **Format Restrictions by Role**:
   - `user` role: `"JSON"` only
   - `manager` role: `"JSON"`, `"CSV"`
   - `admin` role: `"JSON"`, `"CSV"`, `"PDF"`

5. **External Sharing**: Always defaults to `false` and requires explicit manager+ approval to set to `true`

### Default Value Assignment

| Variable | Default Value | Applied When |
|----------|---------------|--------------|
| `external_sharing` | `false` | Not specified in arguments |
| `format` | `"JSON"` | Not specified in arguments |
| `time_range` | `"current"` | Not specified in arguments |
| `include_benefits` | `true` | Not specified for compensation tools |
| `export_type` | `"summary"` | Not specified for export tools |
| `environment` | `"production"` | Always applied |
| `trust_level` | `"internal"` | For all tools except external integrations |



### Tool-Specific Validation

#### HR/Compensation Tools
- **Required Role**: `manager` or `admin` minimum
- **Restricted Fields**: Cannot access `ssn`, `personal_email`, `home_address`
- **Time Limits**: Maximum `last_year` for regular managers
- **Export Limits**: `detailed` exports require business justification

#### Procurement Tools
- **Amount Limits**: Based on user role max_purchase value
- **Approval Required**: Purchases over role limit trigger approval workflow
- **Valid Categories**: Must match predefined product categories

#### Communication Tools
- **Domain Validation**: Email recipients validated against allowed domains
- **External Sharing**: Blocked for sensitive data regardless of role
- **Content Scanning**: All content scanned for sensitive information

>>>>>>> 59aaaa7 (feat: documentation for schema and tools)
=======
>>>>>>> ea2b1b5 (fix: system variables based on updated schema)
