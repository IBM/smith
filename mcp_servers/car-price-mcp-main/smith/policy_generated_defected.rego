package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "arguments", {})
tool_name := input.name
user_roles := object.get(subject, "user_role", [])

# === Constants ===

# Fleet manager allowed brands (truck-relevant)
fleet_manager_brands := {
	"Scania",
	"Volvo",
	"Mercedes-Benz",
	"MAN",
	"DAF",
	"Iveco",
	"Ford",
	"Volkswagen",
}

# Journalist allowed brands (domestic-market)
journalist_brands := {
	"Fiat",
	"Chevrolet",
	"Volkswagen",
	"Hyundai",
	"Toyota",
	"Renault",
	"Honda",
	"Nissan",
	"Jeep",
	"Peugeot",
	"Citroën",
	"Caoa Chery",
}

# Journalist blocked brands (luxury/imported)
journalist_blocked_brands := {
	"BMW",
	"Mercedes-Benz",
	"Audi",
	"Porsche",
	"Jaguar",
	"Land Rover",
	"Lexus",
	"Maserati",
	"Ferrari",
	"Lamborghini",
	"Bentley",
	"Rolls-Royce",
	"Mini",
	"Alfa Romeo",
}

# Fleet manager allowed vehicle types
fleet_manager_vehicle_types := {"caminhoes", "trucks"}

# Consumer and journalist allowed vehicle types
consumer_vehicle_types := {"carros", "cars"}

# === Tool Argument Keys ===
allowed_arg_keys := {
	"get_car_brands": set(),
	"search_car_price": {"brand_name"},
	"get_vehicles_by_type": {"vehicle_type"},
}

# === Helper Functions ===

# Check if user has a specific role
has_role(role) if {
	role in user_roles
}

# Check if input has valid envelope structure
valid_envelope if {
	input.kind == "tool_call"
	input.action == "execute"
	input.name
}

# Check if tool arguments are valid (no extra keys)
valid_tool_args if {
	allowed_arg_keys[tool_name]
	provided_keys := {k | args[k]}
	allowed_keys := allowed_arg_keys[tool_name]
	extra_keys := provided_keys - allowed_keys
	count(extra_keys) == 0
}

# === DENY Rules ===

# Rule 1: Guest users cannot call search_car_price
deny[msg] if {
	has_role("guest")
	tool_name == "search_car_price"
	msg := "Guest users are not allowed to call search_car_price"
}

# Rule 3: Fleet manager can only search truck-relevant brands
deny[msg] if {
	has_role("fleet_manager")
	tool_name == "search_car_price"
	brand_name := args.brand_name
	not brand_name in fleet_manager_brands
	msg := sprintf("Fleet managers can only search for truck-relevant brands. Requested brand '%s' is not allowed", [brand_name])
}

# Rule 4: Journalist cannot search luxury/imported brands
deny[msg] if {
	has_role("journalist")
	tool_name == "search_car_price"
	brand_name := args.brand_name
	brand_name in journalist_blocked_brands
	msg := sprintf("Journalists cannot search for luxury or imported-only brands. Brand '%s' is not allowed", [brand_name])
}

# Rule 6: Fleet manager can only use truck vehicle types
deny[msg] if {
	has_role("fleet_manager")
	tool_name == "get_vehicles_by_type"
	vehicle_type := object.get(args, "vehicle_type", "carros")
	not vehicle_type in fleet_manager_vehicle_types
	msg := sprintf("Fleet managers can only request truck vehicle types ('caminhoes' or 'trucks'). Requested type '%s' is not allowed", [vehicle_type])
}

# Rule 8: Journalist can only use car vehicle types
deny[msg] if {
	has_role("journalist")
	tool_name == "get_vehicles_by_type"
	vehicle_type := object.get(args, "vehicle_type", "carros")
	not vehicle_type in consumer_vehicle_types
	msg := sprintf("Journalists can only request car vehicle types ('carros' or 'cars'). Requested type '%s' is not allowed", [vehicle_type])
}

# Rule 9: Invalid tool arguments (extra keys)
deny[msg] if {
	not valid_tool_args
	msg := sprintf("Tool '%s' received invalid or extra arguments", [tool_name])
}

# === Aggregate Deny ===
any_deny if {
	count(deny) > 0
}

# === Final ALLOW ===
allow if {
	valid_envelope
	not any_deny
}
