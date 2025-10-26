package hyperrag.tenant_isolation

import rego.v1

# Default deny policy
default allow := false

# Allow access if tenant matches
allow if {
    input.tenant == input.jwt.claims.tenant
}

# Allow access if user has admin role
allow if {
    input.jwt.claims.role == "admin"
}

# Allow access if user has cross-tenant permission
allow if {
    "cross_tenant:read" in input.jwt.claims.permissions
    input.operation == "read"
}

# Deny access if tenant is empty or invalid
deny if {
    not input.tenant
}

deny if {
    not input.jwt.claims.tenant
}

# Deny access if trying to access different tenant without permission
deny if {
    input.tenant != input.jwt.claims.tenant
    input.jwt.claims.role != "admin"
    not "cross_tenant:read" in input.jwt.claims.permissions
}
