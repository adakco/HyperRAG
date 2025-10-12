package hyperrag.agent_policies

import rego.v1

# Default deny policy
default allow := false

# Allow agent execution if user has proper permissions
allow if {
    input.jwt.claims.role in ["admin", "agent_user", "developer"]
    input.operation == "execute_agent"
}

# Allow tool invocation if user has tool-specific permissions
allow if {
    input.jwt.claims.role in ["admin", "agent_user", "developer"]
    input.operation == "invoke_tool"
    input.tool_name in allowed_tools
}

# Define allowed tools based on user role
allowed_tools := {
    "retriever.mcp",
    "pack.longrag.mcp",
    "memory.memorag.mcp",
    "evaluator.ragas.mcp"
} if {
    input.jwt.claims.role in ["admin", "agent_user", "developer"]
}

# Restrict access to policy and costing tools for admin only
allowed_tools := {
    "retriever.mcp",
    "pack.longrag.mcp", 
    "memory.memorag.mcp",
    "evaluator.ragas.mcp",
    "policy.opa.mcp",
    "costing.billing.mcp"
} if {
    input.jwt.claims.role == "admin"
}

# Language-specific permissions
allow if {
    input.lang == "fa"
    "persian:read" in input.jwt.claims.permissions
    input.operation == "read"
}

allow if {
    input.lang == "en"
    "english:read" in input.jwt.claims.permissions
    input.operation == "read"
}

# Budget and rate limiting
allow if {
    input.token_budget <= max_token_budget
    input.max_steps <= max_agent_steps
}

max_token_budget := 8000 if {
    input.jwt.claims.role == "admin"
}

max_token_budget := 4000 if {
    input.jwt.claims.role == "agent_user"
}

max_token_budget := 2000 if {
    input.jwt.claims.role == "developer"
}

max_agent_steps := 20 if {
    input.jwt.claims.role == "admin"
}

max_agent_steps := 10 if {
    input.jwt.claims.role == "agent_user"
}

max_agent_steps := 5 if {
    input.jwt.claims.role == "developer"
}

# Deny access if budget exceeded
deny if {
    input.token_budget > max_token_budget
}

deny if {
    input.max_steps > max_agent_steps
}

# Deny access if user doesn't have required permissions
deny if {
    input.operation == "execute_agent"
    not input.jwt.claims.role in ["admin", "agent_user", "developer"]
}

deny if {
    input.operation == "invoke_tool"
    not input.tool_name in allowed_tools
}
