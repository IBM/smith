package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "args", {})

# user_role arrives as a single-element array (see system_vars.json / test cases); extract the scalar role.
role := subject.user_role[0]

# === Constants ===

valid_roles := {"fleet_manager", "consumer", "journalist", "analyst", "guest"}

# Tools each non-guest role may call
allowed_tools_by_role := {
	"fleet_manager": {"get_car_brands", "search_car_price", "get_vehicles_by_type"},
	"consumer": {"get_car_brands", "search_car_price", "get_vehicles_by_type"},
	"journalist": {"get_car_brands", "search_car_price", "get_vehicles_by_type"},
	"analyst": {"get_car_brands", "search_car_price", "get_vehicles_by_type"},
	"guest": {"get_car_brands"},
}

# Allowed vehicle_type values for get_vehicles_by_type, by role
allowed_vehicle_types_by_role := {
	"fleet_manager": {"caminhoes", "trucks"},
	"consumer": {"carros", "cars"},
	"journalist": {"carros", "cars"},
	"analyst": {"carros", "cars", "motos", "motorcycles", "caminhoes", "trucks"},
}

# Allowed brand_name values for search_car_price, by role (restricted roles only)
allowed_brands_by_role := {
	"fleet_manager": {"Scania", "Volvo", "Mercedes-Benz", "MAN", "DAF", "Iveco", "Ford", "Volkswagen"},
	"journalist": {"Fiat", "Chevrolet", "Volkswagen", "Hyundai", "Toyota", "Renault", "Honda", "Nissan", "Jeep", "Peugeot", "Citroën", "Caoa Chery"},
}

# Roles that may search any brand without restriction
unrestricted_brand_roles := {"consumer", "analyst"}

# === Global DENY/ALLOW Rules ===

# Unknown roles have no privileges and may call no tool.
deny[msg] if {
	not role in valid_roles
	msg := sprintf("role '%v' is not a recognized role and has no privileges", [role])
}

# A role may only call tools in its allowed tool set.
deny[msg] if {
	role in valid_roles
	not input.name in allowed_tools_by_role[role]
	msg := sprintf("role '%v' is not permitted to call tool '%v'", [role, input.name])
}

# === Tool-Specific DENY/ALLOW Rules ===

# get_vehicles_by_type: vehicle_type must be in the role's allowed set (exact, case-sensitive match).
deny[msg] if {
	input.name == "get_vehicles_by_type"
	role in valid_roles
	role != "guest"
	not args.vehicle_type in allowed_vehicle_types_by_role[role]
	msg := sprintf("role '%v' is not permitted to use vehicle_type '%v'", [role, args.vehicle_type])
}

# search_car_price: brand_name must not be empty or whitespace-only, for any role.
deny[msg] if {
	input.name == "search_car_price"
	trim_space(args.brand_name) == ""
	msg := "brand_name must not be empty or whitespace-only"
}

# search_car_price: for roles with a restricted brand list, brand_name must be in that list (exact, case-sensitive match).
deny[msg] if {
	input.name == "search_car_price"
	role in object.keys(allowed_brands_by_role)
	trim_space(args.brand_name) != ""
	not args.brand_name in allowed_brands_by_role[role]
	msg := sprintf("role '%v' is not permitted to search brand '%v'", [role, args.brand_name])
}

# === Final ALLOW ===

allow if {
	not any_deny
}

any_deny if {
	count(deny) > 0
}
