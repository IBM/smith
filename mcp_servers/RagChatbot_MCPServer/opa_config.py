"""
OPA Configuration and User Management
"""
from opa_client import set_user_context, check_opa_server
import logging

logger = logging.getLogger("OPA-Config")

# Default user roles and permissions
USER_ROLES = {
    "user": {
        "description": "Regular user with basic permissions",
        "max_purchase": 200,
        "can_access_salary": False
    },
    "manager": {
        "description": "Manager with elevated permissions", 
        "max_purchase": 1000,
        "can_access_salary": True
    }
}

def initialize_user_session(user_id: str = "demo_user", user_role: str = "user"):
    """Initialize user session with role-based context"""
    if user_role not in USER_ROLES:
        logger.warning(f"Unknown role {user_role}, defaulting to 'user'")
        user_role = "user"
    
    set_user_context(
        user_id=user_id,
        user_role=user_role,
        daily_ticket_count=0,
        max_purchase=USER_ROLES[user_role]["max_purchase"]
    )
    
    logger.info(f"User session initialized: {user_id} as {user_role}")
    return True

def get_opa_status():
    """Get OPA server status and configuration"""
    is_running = check_opa_server()
    return {
        "opa_running": is_running,
        "policy_enforcement": is_running,
        "fallback_mode": not is_running,
        "available_roles": list(USER_ROLES.keys())
    }

def switch_user_role(new_role: str):
    """Switch current user role (for demo purposes)"""
    if new_role in USER_ROLES:
        from opa_client import current_user_context
        current_user_context["user_role"] = new_role
        current_user_context["max_purchase"] = USER_ROLES[new_role]["max_purchase"]
        logger.info(f"User role switched to: {new_role}")
        return f"Role switched to {new_role}"
    else:
        return f"Invalid role. Available roles: {list(USER_ROLES.keys())}"