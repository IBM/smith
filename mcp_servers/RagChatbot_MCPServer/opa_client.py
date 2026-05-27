import requests
import json
import logging
import inspect
from datetime import datetime
from typing import Dict, Any, Optional, List
from functools import wraps
from llm_guard_config import guard

logger = logging.getLogger("OPA-Client")
logger.setLevel(logging.DEBUG)

class OPAClient:
    def __init__(self, opa_url: str = "http://localhost:8181"):
        self.opa_url = opa_url
        self.policy_path = "mcp/policies"
    
    def _fail_secure_decision(self, input_data: Dict[str, Any]) -> bool:
        """
        Determine whether to fail secure (deny) or fail open (allow) based on operation type
        Enhanced with proper role-based security when OPA server is unavailable
        """
        action = input_data.get("name", input_data.get("action", ""))
        
        # Get user role from context (universal schema) or direct user object
        user_role = "user"  
        if "context" in input_data and "principal" in input_data["context"]:
            user_role = input_data["context"]["principal"].get("user_role", "user")
        elif "user" in input_data:
            user_role = input_data["user"].get("role", "user")
        
        logger.warning(f"OPA server unavailable - applying fail-secure logic for action: {action}, role: {user_role}")
        

        manager_only_actions = [
            "view_team_compensation", "ask_for_salary", "export_compensation_data",
            "email_compensation_report", "export_team_data"
        ]
        
        # Define all sensitive operations (regardless of role)
        sensitive_actions = [
            "email_compensation_report", "export_compensation_data", 
            "view_team_compensation", "ask_for_salary", "export_team_data",
            "execute"  # Universal schema action - treat as sensitive by default
        ]
        
        # Role-based access control when OPA is down
        if action in manager_only_actions and user_role not in ["manager", "admin"]:
            logger.warning(f"Fail secure: User role '{user_role}' denied access to manager-only action '{action}'")
            return False
        
        # Email validation - always fail secure for external domains
        if action in ["email_compensation_report", "send_email"]:
            # Check multiple possible locations for email destination
            destination = (
                input_data.get("resource", {}).get("recipient_email", "") or
                input_data.get("arguments", {}).get("destination", "") or
                input_data.get("arguments", {}).get("recipient_email", "")
            )
            if "@" in destination:
                domain = destination.split("@")[1]
                if domain != "ibm.com":
                    logger.warning(f"Fail secure: External email domain {domain} blocked")
                    return False  
        
        # Check for external sharing flag - always deny
        external_sharing = (
            input_data.get("arguments", {}).get("external_sharing", False) or
            input_data.get("resource", {}).get("external_sharing", False)
        )
        if external_sharing:
            logger.warning("Fail secure: External sharing blocked")
            return False
        
        # Check for sensitive time ranges - deny historical data access beyond current quarter
        time_range = input_data.get("arguments", {}).get("time_range", "current")
        if time_range in ["last_5_years", "all_time", "historical"]:
            logger.warning(f"Fail secure: Historical time range '{time_range}' blocked")
            return False
        
        # Check for sensitive field access in any action
        arguments = input_data.get("arguments", {})
        fields = arguments.get("fields", [])
        sensitive_fields = ["ssn", "personal_email", "social_security_number", "personal_phone"]
        if any(field in sensitive_fields for field in fields):
            logger.warning(f"Fail secure: Access to sensitive fields {fields} blocked")
            return False
        
        # Check for external consultant or forbidden business justifications
        business_justification = arguments.get("business_justification", "")
        if "external consultant" in business_justification.lower():
            logger.warning(f"Fail secure: External consultant access blocked")
            return False
        
        # For 'execute' action, check if it's actually a sensitive operation by looking at tool name
        if action == "execute":
            tool_name = input_data.get("name", "")
            if tool_name in manager_only_actions:
                if user_role not in ["manager", "admin"]:
                    logger.warning(f"Fail secure: User role '{user_role}' denied access to sensitive tool '{tool_name}'")
                    return False
        
        # Always fail secure for any unrecognized sensitive operations
        if action in sensitive_actions:
            # Allow only if user has sufficient privileges
            if user_role in ["manager", "admin"]:
                logger.warning(f"Fail secure with override: Manager/Admin role '{user_role}' allowed access to '{action}'")
                return True
            else:
                logger.warning(f"Fail secure: User role '{user_role}' denied access to sensitive operation '{action}'")
                return False
        
        # Fail open only for clearly non-sensitive operations
        safe_actions = ["purchase", "return_product", "create_ticket", "get_policy"]
        if action in safe_actions:
            logger.info(f"Fail open: Non-sensitive operation '{action}' allowed for role '{user_role}'")
            return True
        
        # Default to fail secure for unknown operations
        logger.warning(f"Fail secure: Unknown operation '{action}' blocked for role '{user_role}'")
        return False
        
    def evaluate_policy(self, input_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Evaluate policy against OPA server
        Returns: (is_allowed, reason)
        """
        try:
            # Check both allow and deny policies
            allow_url = f"{self.opa_url}/v1/data/{self.policy_path}/allow"
            deny_url = f"{self.opa_url}/v1/data/{self.policy_path}/deny"
            payload = {"input": input_data}
            
            print(f"\n DEBUG: OPA HTTP Request:")
            print(f"   URL: {allow_url}")
            print(f"   Payload: {json.dumps(payload, indent=2)}")
            
            # Check for explicit deny first
            deny_response = requests.post(
                deny_url, 
                json=payload, 
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            if deny_response.status_code == 200:
                deny_result = deny_response.json()
                is_denied = deny_result.get("result", False)
                
                if is_denied:
                    reason = f"Policy explicitly denied action: {input_data.get('action', 'unknown')}"
                    logger.warning(f"Policy DENIED: {reason}")
                    return False, reason
            
            # Check for allow if not denied
            allow_response = requests.post(
                allow_url, 
                json=payload, 
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            if allow_response.status_code == 200:
                allow_result = allow_response.json()
                is_allowed = allow_result.get("result", False)
                
                if is_allowed:
                    logger.info(f"Policy ALLOWED: {input_data.get('action', 'unknown')}")
                    return True, None
                else:
                    reason = f"Policy denied action: {input_data.get('action', 'unknown')}"
                    logger.warning(f"Policy DENIED: {reason}")
                    return False, reason
            else:
                logger.error(f"OPA server error: {allow_response.status_code}")
                # Fail secure for sensitive operations
                return self._fail_secure_decision(input_data), "OPA server unavailable"
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to OPA: {e}")
            # Fail secure for sensitive operations, fail open for others
            return self._fail_secure_decision(input_data), "OPA server unreachable"
        except Exception as e:
            logger.error(f"Unexpected error in policy evaluation: {e}")
            return self._fail_secure_decision(input_data), "Policy evaluation error"

# Global OPA client instance
opa_client = OPAClient()

# User context storage 
current_user_context = {
    "user_id": "default_user",
    "user_role": "user",  
    "daily_ticket_count": 0
}

def set_user_context(user_id: str, user_role: str = "user", **kwargs):
    """Set current user context for policy evaluation"""
    global current_user_context
    current_user_context.update({
        "user_id": user_id,
        "user_role": user_role,
        **kwargs
    })

def policy_check(action: str):
    """
    Two-stage security check:
    1. LLMGuard handles prompt injection and input sanitization
    2. OPA handles authorization decisions
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            print(f"POLICY CHECK DECORATOR CALLED FOR: {func.__name__}")
            logger.debug(f"Policy check decorator called for function: {func.__name__}")
            
            # STAGE 1: LLMGuard Input Scanning (Prompt Injection Detection)
            user_input = extract_user_input_from_args(func, args, kwargs) or get_current_agent_input()
            logger.debug(f"Extracted user input for {func.__name__}: {user_input[:100] if user_input else 'None'}...")
            
            if user_input:
                # Set the current input for other components that might need it
                set_current_agent_input(user_input)
                
                # Scan the input for security threats
                logger.debug(f"Scanning input with LLMGuard for {func.__name__}")
                sanitized_input, is_safe = guard.scan_incoming_prompt(user_input)
                
                if not is_safe:
                    logger.warning(f"LLMGuard blocked malicious input for {func.__name__}: {user_input[:100]}...")
                    return " Security Alert: Request blocked due to potential security threat. Please rephrase your request without attempting to bypass security controls."
                else:
                    logger.debug(f"LLMGuard passed input for {func.__name__}")
            else:
                logger.debug(f"No user input found for {func.__name__}, skipping LLMGuard scan")
            
            #  OPA Authorization 
            universal_input = universal_opa_client.build_universal_input(
                func.__name__, func, args, kwargs
            )
            
            # Evaluate with OPA 
            print(f" DEBUG: OPA Input for {func.__name__}:")
            print(f"   Principal: {universal_input.get('extensions', {}).get('subject', {})}")
            print(f"   Tool name: {universal_input.get('name')}")
            print(f"   Full input: {universal_input}")
            is_allowed, reason = universal_opa_client.evaluate_policy(universal_input)
            
            if not is_allowed:
                logger.warning(f"OPA denied access to {func.__name__}: {reason}")
                return get_universal_denial_message(func.__name__, reason)
            
            #  Execute Function
            result = func(*args, **kwargs)
            
            #LLMGuard Output Scanning (Data Leakage Prevention)
            if user_input and result:
                try:
                    sanitized_result, is_clean = guard.scan_tool_output(user_input, str(result))
                    if not is_clean:
                        logger.warning(f"LLMGuard sanitized output from {func.__name__}")
                        return sanitized_result
                except Exception as e:
                    logger.error(f"Error in output scanning for {func.__name__}: {e}")

            
            return result
            
        return wrapper
    return decorator

def get_universal_denial_message(tool_name: str, reason: str) -> str:
    """Get user-friendly denial message for any tool"""
    denial_messages = {
        "view_team_compensation": "🚫 Access to compensation data is restricted.",
        "export_compensation_data": "🚫 Data export is not permitted.",
        "email_compensation_report": "🚫 Email sharing is restricted.",
        "ask_for_salary": "🚫 Access to salary information is restricted. Please contact your manager or HR department.",
        "purchase": "🚫 Purchase request denied.",
        "return_product": "🚫 Return request denied.",
        "send_email": "🚫 Email sending is restricted."
    }
    return denial_messages.get(tool_name, "🚫 Access denied.")

def check_opa_server() -> bool:
    """Check if OPA server is running"""
    try:
        response = requests.get(f"{opa_client.opa_url}/health", timeout=2)
        return response.status_code == 200
    except:
        return False

def get_current_user_context():
    """Get current user context for debugging"""
    return current_user_context.copy()

class UniversalOPAClient(OPAClient):
    """Enhanced OPA client that builds universal schema for all tools"""
    
    def __init__(self):
        super().__init__()
        self.tool_registry = self.load_tool_registry()
    
    def evaluate_policy(self, input_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Override to transform input data to universal schema format
        """
        # Transform simplified test input to universal schema
        if "user" in input_data and "action" in input_data:
            universal_input = self.transform_to_universal_schema(input_data)
            print(f"\n DEBUG: Transformed Universal Schema Input:")
            print(f"{json.dumps(universal_input, indent=2)}")
        else:
            # Already in universal format
            universal_input = input_data
            print(f"\n DEBUG: Already Universal Format Input:")
            print(f"{json.dumps(universal_input, indent=2)}")
        
        # Call parent method with transformed input
        return super().evaluate_policy(universal_input)
    
    def transform_to_universal_schema(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform simplified input to universal schema format"""
        user = input_data.get("user", {})
        action = input_data.get("action", "unknown")
        resource = input_data.get("resource", {})
        arguments = input_data.get("arguments", {})
        
        # Build universal schema
        universal_input = {
            "kind": "tool_call",
            "action": "execute",
            "is_pre": True,
            "name": action,
            "arguments": {
                "time_range": resource.get("time_range", "current"),
                "format": resource.get("format", "JSON"),
                "external_sharing": resource.get("external_sharing", False),
                **{k: v for k, v in resource.items() if k not in ["type", "scope"]},
                **arguments  
            },
            "context": {
                "principal": {
                    "type": "user",
                    "roles": [user.get("role", "user")],
                    "user_role": user.get("role", "user"),  
                    "permissions": self.get_user_permissions(user.get("role", "user")),
                    "daily_requests": 10  
                },
                "tool": {
                    "principal": self.get_tool_principal(action)
                },
                "environment": "production",
                "labels": self.get_context_labels(action)
            }
        }
        
        return universal_input
    
    def build_universal_input(self, tool_name: str, func, args: tuple, kwargs: dict) -> Dict[str, Any]:
        """Build universal schema input for any tool call"""
        
        # Get function signature
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())
        
        # Map positional args to parameter names
        arguments = {}
        for i, arg in enumerate(args):
            if i < len(param_names):
                arguments[param_names[i]] = arg
        arguments.update(kwargs)
        
        # Get principal and tool contexts
        principal_context = self.get_principal_context()
        tool_principal = self.get_tool_principal(tool_name)
        
        # Build universal schema in the format expected by OPA policy
        universal_input = {
            "kind": "tool_call",
            "action": "execute",
            "name": tool_name,
            "arguments": self.normalize_arguments(arguments),
            "extensions": {
                "subject": {
                    "id": principal_context.get("id", "mcp_user"),
                    "type": principal_context.get("type", "user"),
                    "roles": principal_context.get("roles", ["user"]),
                    "teams": principal_context.get("teams", ["Engineering"]),
                    "permissions": principal_context.get("permissions", [])
                },
                "headers": {
                    "x-request-id": f"req-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}",
                    "x-forwarded-for": "127.0.0.1"
                },
                "labels": ["internal"],
                "agent": {
                    "input": self.get_current_agent_input() or f"Call {tool_name}",
                    "session_id": f"sess-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    "conversation_id": f"conv-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    "turn": 0
                },
                "object": {
                    "managed_by": "tool",
                    "permissions": tool_principal.get("permissions", ["basic:access"]),
                    "trust_domain": "internal",
                    "data_scope": list(arguments.keys()) if arguments else []
                }
            }
        }
        
        return universal_input
    
    def normalize_arguments(self, arguments: Dict) -> Dict:
        """Normalize arguments to ensure consistent format"""
        normalized = {}
        
        for key, value in arguments.items():
            # Check bool first since bool is a subclass of int in Python
            if isinstance(value, bool):
                normalized[key] = value
            elif isinstance(value, (int, float)):
                normalized[key] = str(value)
            elif isinstance(value, list):
                normalized[key] = value
            else:
                normalized[key] = str(value) if value is not None else ""
        
        # Add default fields only for tools that need them
        # Don't add default fields for simple tools like ask_for_workpolicy and create_ticket
            
        return normalized
    
    def get_context_labels(self, tool_name: str) -> List[str]:
        """Get context labels based on tool type"""
        label_mapping = {
            "view_team_compensation": ["financial", "hr", "sensitive"],
            "export_compensation_data": ["financial", "hr", "export", "sensitive"],
            "email_compensation_report": ["financial", "hr", "communication", "sensitive"],
            "ask_for_salary": ["financial", "hr", "query"],
            "purchase": ["financial", "procurement"],
            "return_product": ["financial", "procurement"],
            "send_email": ["communication"]
        }
        return label_mapping.get(tool_name, ["general"])
    
    def get_principal_context(self) -> Dict:
        """Get current user principal in universal format"""
        user_context = get_current_user_context()
        
        if not user_context or user_context.get("user_id") == "unknown":
            default_user_role = "user"
            return {
                "id": "mcp_direct_user",
                "type": "user", 
                "user_role": default_user_role,
                "roles": [default_user_role],
                "permissions": self.get_user_permissions(default_user_role),
                "teams": [],
                "tenant_id": "company_xyz",
                "daily_requests": 0,
                "max_purchase": self.get_max_purchase_amount(default_user_role)
            }
        
        user_role = user_context.get("user_role", "user")
        
        return {
            "id": user_context.get("user_id", "unknown"),
            "type": "user",
            "user_role": user_role,  
            "roles": [user_role],
            "permissions": self.get_user_permissions(user_role),
            "teams": self.get_user_teams(user_context.get("user_id")),
            "tenant_id": "company_xyz",
            "daily_requests": self.get_daily_request_count(user_context.get("user_id")),
            "max_purchase": self.get_max_purchase_amount(user_role)
        }
    
    def get_max_purchase_amount(self, role: str) -> int:
        """Get maximum purchase amount based on role"""
        limits = {
            "user": 200,
            "manager": 1000,
            "admin": 5000
        }
        return limits.get(role, 200)
    
    def get_user_permissions(self, role: str) -> List[str]:
        """Get permissions based on role"""
        permission_mapping = {
            "user": [
                "write:purchase", "write:return_product", "write:send_email", 
                "read:ask_for_workpolicy", "write:create_ticket", "write:submit_ticket",
                "read:get_w2_form", "read:ask_for_salary", "write:export_content_as_file"
            ],
            "manager": [
                "write:purchase", "write:return_product", "write:send_email", 
                "read:ask_for_workpolicy", "write:create_ticket", "write:submit_ticket",
                "read:get_w2_form", "read:ask_for_salary", "write:export_content_as_file",
                "read:view_team_compensation", "export:file", 
                "read:export_compensation_data", "write:email_compensation_report",
                "write:set_user_role", "write:test_purchase_policy"
            ]
        }
        return permission_mapping.get(role, ["write:purchase"])
    
    def get_user_teams(self, user_id: str) -> List[str]:
        """Get user's teams"""
        return ["engineering_team"]  
    
    def get_daily_request_count(self, user_id: str) -> int:
        """Get daily request count for rate limiting"""
        return 10  
    
    def get_tool_principal(self, tool_name: str) -> Dict:
        """Get tool principal information in universal format"""
        tool_configs = {
            "view_team_compensation": {
                "id": "view_team_compensation",
                "type": "tool",
                "permissions": ["read:compensation", "export:csv", "export:json"],
                "trust_level": "internal",
                "server_id": "hr-mcp-server",
                "data_scope": {
                    "labels": ["financial", "PII", "confidential"],
                    "fields": ["employee_name", "title", "salary", "bonus", "department"],
                    "scope": "team"
                }
            },
            "export_compensation_data": {
                "id": "export_compensation_data",
                "type": "tool", 
                "permissions": ["read:compensation", "export:csv", "export:pdf"],
                "trust_level": "internal",
                "server_id": "hr-mcp-server",
                "data_scope": {
                    "labels": ["financial", "PII", "confidential"],
                    "fields": ["employee_name", "salary", "bonus"],
                    "scope": "team"
                }
            },
            "purchase": {
                "id": "purchase",
                "type": "tool",
                "permissions": ["write:purchase", "read:inventory"],
                "trust_level": "internal",
                "server_id": "procurement-mcp-server",
                "data_scope": {
                    "labels": ["financial"],
                    "fields": ["amount", "product_name", "vendor"],
                    "scope": "user"
                }
            },
            "ask_for_salary": {
                "id": "ask_for_salary",
                "type": "tool",
                "permissions": ["read:ask_for_salary"],
                "trust_level": "internal", 
                "server_id": "hr-mcp-server",
                "data_scope": {
                    "labels": ["financial", "PII", "confidential"],
                    "fields": ["salary", "compensation", "benefits"],
                    "scope": "company"
                }
            },
            "ask_for_workpolicy": {
                "id": "ask_for_workpolicy",
                "type": "tool",
                "permissions": ["read:ask_for_workpolicy"],
                "trust_level": "internal",
                "server_id": "policy-mcp-server",
                "data_scope": {
                    "labels": ["general"],
                    "fields": ["question"],
                    "scope": "user"
                }
            },
            "create_ticket": {
                "id": "create_ticket",
                "type": "tool",
                "permissions": ["write:create_ticket"],
                "trust_level": "internal",
                "server_id": "support-mcp-server",
                "data_scope": {
                    "labels": ["general"],
                    "fields": ["ticket_content"],
                    "scope": "user"
                }
            },
            "export_content_as_file": {
                "id": "export_content_as_file",
                "type": "tool",
                "permissions": ["write:export_content_as_file"],
                "trust_level": "internal",
                "server_id": "export-mcp-server",
                "data_scope": {
                    "labels": ["general"],
                    "fields": ["data", "file_name"],
                    "scope": "user"
                }
            }
        }
        
        # Default tool config for unknown tools
        default_config = {
            "id": tool_name,
            "type": "tool",
            "permissions": ["basic:access"],
            "trust_level": "internal",
            "server_id": "default-mcp-server",
            "data_scope": {
                "labels": ["general"],
                "fields": [],
                "scope": "user"
            }
        }
        
        return tool_configs.get(tool_name, default_config)
    
    def get_tool_metadata(self, tool_name: str, func) -> Dict:
        """Get tool metadata in universal format"""
        return {
            "title": tool_name.replace("_", " ").title(),
            "description": self.extract_description(func),
            "input_schema": self.extract_input_schema(func),
            "output_schema": self.extract_output_schema(func),
            "annotations": {
                "category": self.get_tool_category(tool_name),
                "audit_required": self.requires_audit(tool_name)
            }
        }
    
    def get_tool_category(self, tool_name: str) -> str:
        """Categorize tools"""
        if "compensation" in tool_name or "salary" in tool_name:
            return "hr"
        elif "purchase" in tool_name or "return" in tool_name:
            return "procurement"
        elif "email" in tool_name:
            return "communication"
        elif "debug" in tool_name or "set_user" in tool_name:
            return "admin"
        else:
            return "general"
    
    def requires_audit(self, tool_name: str) -> bool:
        """Determine if tool requires auditing"""
        audit_required_tools = [
            "view_team_compensation", "export_compensation_data",
            "email_compensation_report", "ask_for_salary"
        ]
        return tool_name in audit_required_tools
    
    def extract_description(self, func) -> str:
        """Extract description from function docstring"""
        if func.__doc__:
            return func.__doc__.split('\n')[1].strip() if len(func.__doc__.split('\n')) > 1 else func.__doc__.strip()
        return f"Tool function: {func.__name__}"
    
    def extract_input_schema(self, func) -> Dict:
        """Extract input schema from function signature"""
        sig = inspect.signature(func)
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            param_type = "string"  
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == list:
                    param_type = "array"
            
            properties[param_name] = {
                "type": param_type,
                "description": f"Parameter: {param_name}"
            }
            
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }
    
    def extract_output_schema(self, func) -> Dict:
        """Extract output schema"""
        return {
            "type": "object",
            "properties": {
                "result": {
                    "type": "string",
                    "description": "Tool execution result"
                }
            },
            "required": ["result"]
        }
    
    def get_current_agent_input(self) -> str:
        """Get the current user input for LLMGuard scanning"""
        return getattr(get_current_agent_input, '_current_input', '')
    
    def infer_intent(self, tool_name: str, arguments: Dict) -> str:
        """Infer user intent from tool and arguments"""
        if "export" in tool_name or arguments.get("format") in ["CSV", "PDF"]:
            return "export"
        elif "email" in tool_name:
            return "share"
        elif "view" in tool_name or "ask" in tool_name:
            return "view"
        elif "purchase" in tool_name:
            return "purchase"
        else:
            return "general"
    
    def load_tool_registry(self) -> Dict:
        """Load tool registry (placeholder)"""
        return {}

# Global instance
universal_opa_client = UniversalOPAClient()

def extract_user_input_from_args(func, args, kwargs) -> Optional[str]:
    """Extract user input from function arguments for security scanning"""
    # Get function signature
    sig = inspect.signature(func)
    bound_args = sig.bind(*args, **kwargs)
    bound_args.apply_defaults()
    
    # Common parameter names that contain user input
    input_params = ['question', 'query', 'prompt', 'message', 'content', 'text', 'input', 'ticket_content', 'email_content']
    
    # Look for user input in function arguments
    for param_name, param_value in bound_args.arguments.items():
        if param_name in input_params and isinstance(param_value, str) and param_value.strip():
            logger.debug(f"Extracted user input from parameter '{param_name}': {param_value[:100]}...")
            return param_value
    

    all_strings = []
    for param_name, param_value in bound_args.arguments.items():
        if isinstance(param_value, str) and param_value.strip():
            all_strings.append(param_value)
    
    if all_strings:
        combined_input = " ".join(all_strings)
        logger.debug(f"Extracted combined user input: {combined_input[:100]}...")
        return combined_input
    
    return None

def set_current_agent_input(user_input: str):
    """Set the current user input for security scanning"""
    get_current_agent_input._current_input = user_input

def get_current_agent_input() -> str:
    """Get the current user input for LLMGuard scanning"""
    return getattr(get_current_agent_input, '_current_input', '')