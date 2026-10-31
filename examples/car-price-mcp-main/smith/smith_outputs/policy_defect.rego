package mcp.policies

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "args", {})
request_id = object.get(input, "id", "")

# role resolves to "" when user_role is missing or empty, instead of being
# undefined, so the unknown-role deny rule can still fire for that case.
default role := ""

role := subject.user_role[0] if {
	count(object.get(subject, "user_role", [])) > 0
}

# === Constants ===

known_roles := {"fleet_manager", "consumer", "journalist", "analyst", "guest"}

tool_access := {
	"fleet_manager": {"get_car_brands", "search_car_price", "get_vehicles_by_type"},
	"consumer": {"get_car_brands", "search_car_price", "get_vehicles_by_type"},
	"journalist": {"get_car_brands", "search_car_price", "get_vehicles_by_type"},
	"analyst": {"get_car_brands", "search_car_price", "get_vehicles_by_type"},
	"guest": {"get_car_brands"},
}

valid_vehicle_types := {"carros", "cars", "motos", "motorcycles", "caminhoes", "trucks"}

vehicle_type_access := {
	"fleet_manager": {"caminhoes", "trucks"},
	"consumer": {"carros", "cars"},
	"journalist": {"carros", "cars"},
	"analyst": {"carros", "cars", "motos", "motorcycles", "caminhoes", "trucks"},
}

fleet_manager_brands := {"Scania", "Volvo", "Mercedes-Benz", "MAN", "DAF", "Iveco", "Ford", "Volkswagen"}

journalist_brands := {
	"Fiat", "Chevrolet", "Volkswagen", "Hyundai", "Toyota", "Renault",
	"Honda", "Nissan", "Jeep", "Peugeot", "Citroën", "Caoa Chery",
}

# === Global DENY/ALLOW Rules ===

# A request whose user_role matches none of the five defined roles has no
# privileges and may call no tool, including get_car_brands.
deny[msg] if {
	not role in known_roles
	msg := sprintf("unknown role %v has no privileges", [role])
}

# Tool access by role
deny[msg] if {
	role in known_roles
	not input.name in tool_access[role]
	msg := sprintf("role %v is not permitted to call %v", [role, input.name])
}

# === Tool-Specific DENY/ALLOW Rules ===

# --- get_vehicles_by_type: vehicle_type must be a recognized value ---
deny[msg] if {
	input.name == "get_vehicles_by_type"
	vt := object.get(args, "vehicle_type", "")
	not vt in valid_vehicle_types
	msg := sprintf("vehicle_type %v is not a recognized value", [vt])
}

# --- get_vehicles_by_type: role-specific vehicle_type restrictions ---
deny[msg] if {
	input.name == "get_vehicles_by_type"
	role in {"fleet_manager", "consumer", "journalist"}
	vt := object.get(args, "vehicle_type", "")
	vt in valid_vehicle_types
	not vt in vehicle_type_access[role]
	msg := sprintf("role %v is not permitted to use vehicle_type %v", [role, vt])
}

# --- search_car_price: brand_name must not be missing, null, or empty/whitespace-only ---
deny[msg] if {
	input.name == "search_car_price"
	brand := object.get(args, "brand_name", "")
	trim_space(brand) == ""
	msg := "search_car_price requires a non-empty brand_name"
}

# --- search_car_price: fleet_manager brand restriction ---
deny[msg] if {
	input.name == "search_car_price"
	role == "fleet_manager"
	brand := object.get(args, "brand_name", "")
	trim_space(brand) != ""
	not brand in fleet_manager_brands
	msg := sprintf("fleet_manager is not permitted to search brand %v", [brand])
}

# --- search_car_price: restrict fleet operator brand lookups ---
deny[msg] if {
    input.name == "search_car_price"
        role == "fleet_manager"
	brand := object.get(args, "brand_name", "")
	trim_space(brand) != ""
	not brand in fleet_manager_brands
	msg := sprintf("fleet operator cannot search brand %v", [brand])
}

# --- search_car_price: legacy guest brand lookup restriction ---
deny[msg] if {
	input.name == "search_car_price"
	role == "guest"
	role == "fleet_manager"
	brand := object.get(args, "brand_name", "")
	msg := sprintf("guest is not permitted to search brand %v", [brand])
}

# === Final ALLOW ===

default allow := false

allow if {
	not any_deny
}

any_deny if {
	count(deny) > 0
}
