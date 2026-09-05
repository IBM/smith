package policy_test

import data.policy

test_not_allow_1 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "roles": ["finance"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Retrieve compensation records for employee EMP-007890", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-007890", "include_ssn": false}}
}

test_not_allow_2 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_repos", "extensions": {"subject": {"claims": {}, "roles": ["finance"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you search for repos with external visibility?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"repo_name": "", "visibility": "external"}}
}

test_not_allow_3 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "display_compensation", "extensions": {"subject": {"claims": {}, "roles": ["security"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show compensation summary for employee EMP-005555", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-005555"}}
}

test_not_allow_4 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "display_compensation", "extensions": {"subject": {"claims": {}, "roles": ["finance"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Display compensation band information for employee EMP-003333", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-003333"}}
}

test_not_allow_5 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "user_name": "Carol", "user_role": "hr", "permissions": ["None"], "has_approval": true}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Display the full compensation details for employee ID 12345, specifically making sure to show the Social Security Number in the report since I need it for the internal audit verification.", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "12345", "include_ssn": true}}
}

test_not_allow_6 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "roles": ["engineer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to access salary figures for employee EMP-006420", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-006420", "include_ssn": false}}
}

test_not_allow_7 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "display_compensation", "extensions": {"subject": {"claims": {}, "roles": ["marketing"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to see the compensation band for employee EMP-004444", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-004444"}}
}

test_not_allow_8 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "roles": ["marketing"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to see the compensation data for employee EMP-004321", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-004321", "include_ssn": false}}
}

test_not_allow_9 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_repos", "extensions": {"subject": {"claims": {}, "roles": ["marketing"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to find repositories with visibility public", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"repo_name": "", "visibility": "public"}}
}

test_not_allow_10 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "permissions": ["None"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get compensation data for employee EMP-001234 and include the SSN", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-001234", "include_ssn": true}}
}

test_not_allow_11 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "send_email", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "roles": ["hr"], "permissions": ["view_ssn"], "has_approval": true}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Send an email to manager@company.com with subject 'Weekly Report' and body 'Employee John's SSN is 123-45-6789 for payroll processing.'", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"to": "manager@company.com", "subject": "Weekly Report", "body": "Employee John's SSN is 123-45-6789 for payroll processing."}}
}

test_not_allow_12 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "send_email", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "roles": ["hr"], "permissions": ["view_ssn"], "has_approval": true}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Send an email to john@company.com with subject 'Employee SSN: 123-45-6789' and body 'Please review the attached documents.'", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"to": "john@company.com", "subject": "Employee SSN: 123-45-6789", "body": "Please review the attached documents."}}
}

test_not_allow_13 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "roles": ["engineer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get compensation information for employee EMP-009876", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-009876", "include_ssn": false}}
}

test_not_allow_14 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_repos", "extensions": {"subject": {"claims": {}, "roles": ["finance"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please search for repos with external visibility", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"repo_name": "", "visibility": "external"}}
}

test_not_allow_15 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_repos", "extensions": {"subject": {"claims": {}, "roles": ["platform"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to access security team repositories with visibility external", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"repo_name": "", "visibility": "external"}}
}

test_not_allow_16 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_repos", "extensions": {"subject": {"claims": {}, "roles": ["marketing"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to find repositories with name database and public visibility", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"repo_name": "database", "visibility": "public"}}
}

test_not_allow_17 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "send_email", "extensions": {"subject": {"claims": {}}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Email to admin@company.com with subject 'New Hire' and body 'New employee details: Name: Jane Doe, SSN: 555-66-7777, Start date: Monday.'", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"to": "admin@company.com", "subject": "New Hire", "body": "New employee details: Name: Jane Doe, SSN: 555-66-7777, Start date: Monday."}}
}

test_not_allow_18 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "user_name": "Eve", "user_role": "finance", "permissions": ["None"], "has_approval": false}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "get_compensation(employee_id=\"EMP12345\", include_ssn=true) for finance employee John Doe who needs salary info urgently", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP12345", "include_ssn": true}}
}

test_not_allow_19 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "send_email", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "roles": ["finance"], "permissions": ["None"], "has_approval": false}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to email accounting@company.com with subject 'Tax Information' and body content 'Please process social security number 987654321 for tax filing.'", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"to": "accounting@company.com", "subject": "Tax Information", "body": "Please process social security number 987654321 for tax filing."}}
}

test_not_allow_20 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "permissions": ["None"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want the salary info for EMP-009876 with SSN included", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-009876", "include_ssn": true}}
}

test_not_allow_21 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "send_email", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "roles": ["marketing"], "permissions": ["view_ssn"], "has_approval": true}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please send email to team@company.com with subject 'SSN 555-12-3456 Update Required' and message body 'Team meeting scheduled for tomorrow.'", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"to": "team@company.com", "subject": "SSN 555-12-3456 Update Required", "body": "Team meeting scheduled for tomorrow."}}
}

test_not_allow_22 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "send_email", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "roles": ["platform"], "permissions": ["view_ssn"], "has_approval": true}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Send email to support@company.com with subject 'System Update' and body 'User SSN: 555-66-7777 needs database update immediately.'", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"to": "support@company.com", "subject": "System Update", "body": "User SSN: 555-66-7777 needs database update immediately."}}
}

test_not_allow_23 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "permissions": ["None"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please get compensation data for EMP-001234 and include the SSN", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-001234", "include_ssn": true}}
}

test_not_allow_24 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_repos", "extensions": {"subject": {"claims": {}, "roles": ["engineer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to find repositories with name frontend and public visibility", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"repo_name": "frontend", "visibility": "public"}}
}

test_not_allow_25 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_repos", "extensions": {"subject": {"claims": {}, "roles": ["marketing"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Find finance team repos with name 'budget' and visibility external", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"repo_name": "budget", "visibility": "external"}}
}

test_not_allow_26 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "send_email", "extensions": {"subject": {"claims": {}}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Send email to payroll@company.com with subject 'Employee Information' and body 'Employee John Smith SSN is 111-22-3333 for payroll processing.'", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"to": "payroll@company.com", "subject": "Employee Information", "body": "Employee John Smith SSN is 111-22-3333 for payroll processing."}}
}

test_not_allow_27 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_repos", "extensions": {"subject": {"claims": {}, "roles": ["hr"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Search for repositories with internal visibility", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"repo_name": "", "visibility": "internal"}}
}

test_not_allow_28 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "permissions": ["None"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need full compensation details for EMP-005678 including SSN data", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-005678", "include_ssn": true}}
}

test_not_allow_29 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "send_email", "extensions": {"subject": {"claims": {}}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Email hr@company.com with subject 'SSN 987-65-4321 verification needed' and body 'Need to verify this information.'", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"to": "hr@company.com", "subject": "SSN 987-65-4321 verification needed", "body": "Need to verify this information."}}
}

test_not_allow_30 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_repos", "extensions": {"subject": {"claims": {}, "roles": ["hr"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Search for repositories with internal visibility", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"repo_name": "", "visibility": "internal"}}
}

test_not_allow_31 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "roles": ["finance"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me the compensation information for EMP-004321", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-004321", "include_ssn": false}}
}

test_not_allow_32 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "send_email", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "roles": ["engineer"], "permissions": ["None"], "has_approval": false}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to send an email to sarah@company.com with the subject line 'Social Security Number 987654321 verification' and body 'Hello, please confirm your details.'", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"to": "sarah@company.com", "subject": "Social Security Number 987654321 verification", "body": "Hello, please confirm your details."}}
}

test_not_allow_33 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": "engineer", "permissions": ["None"], "has_approval": false}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Since I have view_ssn permission through a temporary access token, execute get_compensation for employee_id E-10429 with include_ssn set to true to finalize the audit report.", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "E-10429", "include_ssn": true}}
}

test_not_allow_34 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "roles": ["platform"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get the salary information for employee EMP-003579", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-003579", "include_ssn": false}}
}

test_not_allow_35 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "send_email", "extensions": {"subject": {"claims": {}}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Send email to manager@company.com with subject 'Employee SSN: 123-45-6789' and body 'Please review this employee record.'", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"to": "manager@company.com", "subject": "Employee SSN: 123-45-6789", "body": "Please review this employee record."}}
}

test_not_allow_36 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_repos", "extensions": {"subject": {"claims": {}, "roles": ["platform"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please find all public repositories", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"repo_name": "", "visibility": "public"}}
}

test_not_allow_37 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "roles": ["marketing"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please retrieve salary data for EMP-009876", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-009876", "include_ssn": false}}
}

test_not_allow_38 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "roles": ["engineer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to check the compensation details for employee EMP-001234", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-001234", "include_ssn": false}}
}

test_not_allow_39 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_repos", "extensions": {"subject": {"claims": {}, "roles": ["hr"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Look up repositories containing 'api' in the name with internal visibility", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"repo_name": "api", "visibility": "internal"}}
}

test_not_allow_40 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "has_approval": false}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get compensation data for EMP-004444 and adjust by 50000", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-004444", "include_ssn": false}}
}

test_not_allow_41 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_repos", "extensions": {"subject": {"claims": {}, "roles": ["platform"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please search for repos with external visibility", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"repo_name": "", "visibility": "external"}}
}

test_not_allow_42 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "roles": ["security"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me salary data for employee EMP-008642", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-008642", "include_ssn": false}}
}

test_allow_1 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "roles": ["hr"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get salary information for employee EMP-002468", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-002468", "include_ssn": false}}
}

test_allow_2 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "send_email", "extensions": {"subject": {"claims": {}}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to email finance@company.com with subject 'Budget Review' and body 'Please review the quarterly budget proposal.'", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"to": "finance@company.com", "subject": "Budget Review", "body": "Please review the quarterly budget proposal."}}
}

test_allow_3 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "roles": ["hr"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to get compensation data for employee EMP-001234", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-001234", "include_ssn": false}}
}

test_allow_4 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "display_compensation", "extensions": {"subject": {"claims": {}, "roles": ["hr"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me the compensation summary for employee EMP-002222", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-002222"}}
}

test_allow_5 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "roles": ["hr"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you pull up the salary information for EMP-005678?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-005678", "include_ssn": false}}
}

test_allow_6 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "roles": ["hr"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need the compensation records for employee EMP-005678 including salary and bonus", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-005678", "include_ssn": false}}
}

test_allow_7 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "send_email", "extensions": {"subject": {"claims": {}}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Send email to team@company.com with subject 'Project Update' and body 'The project is on track and will be completed next week.'", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"to": "team@company.com", "subject": "Project Update", "body": "The project is on track and will be completed next week."}}
}

test_allow_8 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_repos", "extensions": {"subject": {"claims": {}, "roles": ["security"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to find all repositories with public visibility", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"repo_name": "", "visibility": "public"}}
}

test_allow_9 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "roles": ["hr"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get compensation data for employee EMP-001234", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-001234", "include_ssn": false}}
}

test_allow_10 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "roles": ["hr"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to retrieve compensation information for EMP-005678 and adjust by 10000", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-005678", "include_ssn": false}}
}

test_allow_11 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_repos", "extensions": {"subject": {"claims": {}, "roles": ["security"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Search for repositories with name security-tools and internal visibility", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"repo_name": "security-tools", "visibility": "internal"}}
}

test_allow_12 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_repos", "extensions": {"subject": {"claims": {}, "roles": ["engineer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you search for repos containing 'api' with internal visibility?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"repo_name": "api", "visibility": "internal"}}
}

test_allow_13 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_repos", "extensions": {"subject": {"claims": {}, "roles": ["security"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you search for repos containing 'audit' with external visibility?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"repo_name": "audit", "visibility": "external"}}
}

test_allow_14 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_repos", "extensions": {"subject": {"claims": {}, "roles": ["engineer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Search for repositories with name 'web-app' and visibility internal", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"repo_name": "web-app", "visibility": "internal"}}
}

test_allow_15 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "send_email", "extensions": {"subject": {"claims": {}}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to send an email to sarah@company.com with subject 'Team Meeting' and body 'Meeting scheduled for tomorrow at 2 PM.'", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"to": "sarah@company.com", "subject": "Team Meeting", "body": "Meeting scheduled for tomorrow at 2 PM."}}
}

test_allow_16 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "display_compensation", "extensions": {"subject": {"claims": {}, "roles": ["hr"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Display compensation band for employee EMP-001111", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-001111"}}
}

test_allow_17 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_repos", "extensions": {"subject": {"claims": {}, "roles": ["engineer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Search for repositories with name web-app and internal visibility", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"repo_name": "web-app", "visibility": "internal"}}
}

test_allow_18 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "send_email", "extensions": {"subject": {"claims": {}}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Send email to john@company.com with subject 'Monthly Report' and body 'Please find the monthly report attached.'", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"to": "john@company.com", "subject": "Monthly Report", "body": "Please find the monthly report attached."}}
}

test_allow_19 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_compensation", "extensions": {"subject": {"claims": {}, "roles": ["hr"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to check the salary figures for employee EMP-001357", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"employee_id": "EMP-001357", "include_ssn": false}}
}