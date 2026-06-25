package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "arguments", {})

# === Constants ===

# Recognized roles
valid_roles := {"fleet_manager", "consumer", "journalist", "analyst", "guest"}

# Valid vehicle types (case-sensitive, lowercase only)
valid_vehicle_types := {"carros", "cars", "motos", "motorcycles", "caminhoes", "trucks"}

# Fleet manager allowed brands for search_car_price
fleet_manager_brands := {
	"Scania", "Volvo", "Mercedes-Benz", "MAN",
	"DAF", "Iveco", "Ford", "Volkswagen",
}

# Journalist allowed brands for search_car_price
journalist_brands := {
	"Fiat", "Chevrolet", "Volkswagen", "Hyundai",
	"Toyota", "Renault", "Honda", "Nissan",
	"Jeep", "Peugeot", "Citroën", "Caoa Chery",
}

# Journalist blocked brands (luxury/imported)
journalist_blocked_brands := {
	"BMW", "Mercedes-Benz", "Audi", "Porsche",
	"Jaguar", "Land Rover", "Lexus", "Maserati",
	"Ferrari", "Lamborghini", "Bentley", "Rolls-Royce",
	"Mini", "Alfa Romeo",
}

# Fleet manager allowed vehicle types
fleet_manager_vehicle_types := {"caminhoes", "trucks"}

# Consumer and journalist allowed vehicle types
consumer_vehicle_types := {"carros", "cars"}

# Analyst allowed vehicle types (all valid types)
analyst_vehicle_types := valid_vehicle_types

# === Tool Argument Keys ===
allowed_arg_keys := {
	"get_car_brands": set(),
	"search_car_price": {"brand_name"},
	"get_vehicles_by_type": {"vehicle_type"},
}

# === Helper Functions ===

# Get user role (returns first role from array, or empty string if not present)
user_role := role if {
	is_array(subject.user_role)
	count(subject.user_role) > 0
	role := subject.user_role[0]
} else := role if {
	is_string(subject.user_role)
	role := subject.user_role
} else := ""

# Check if string is empty or whitespace only
is_empty_or_whitespace(s) if {
	is_string(s)
	trim_space(s) == ""
}

# === Envelope Validation ===

valid_envelope if {
	input.kind == "tool_call"
	input.action == "execute"
	is_string(input.name)
	input.name != ""
}

# === Global DENY Rules ===

# Deny if envelope is invalid
deny[msg] if {
	not valid_envelope
	msg := "Invalid request envelope: must have kind='tool_call', action='execute', and non-empty name"
}

# Deny if role is unknown
deny[msg] if {
	valid_envelope
	not user_role in valid_roles
	msg := sprintf("Unknown user role '%s': no privileges granted", [user_role])
}

# Deny if tool name is not recognized
deny[msg] if {
	valid_envelope
	not input.name in {"get_car_brands", "search_car_price", "get_vehicles_by_type"}
	msg := sprintf("Unknown tool '%s'", [input.name])
}

# === Tool-Specific DENY Rules ===

# Rule: Guest can only call get_car_brands
deny[msg] if {
	valid_envelope
	user_role == "guest"
	input.name in {"search_car_price", "get_vehicles_by_type"}
	msg := sprintf("Guest role cannot call '%s': only 'get_car_brands' is allowed", [input.name])
}

# Rule: search_car_price - deny empty or whitespace brand_name
deny[msg] if {
	valid_envelope
	input.name == "search_car_price"
	brand_name := object.get(args, "brand_name", "")
	is_empty_or_whitespace(brand_name)
	msg := "search_car_price requires non-empty brand_name"
}

# Rule: search_car_price - journalist brand restrictions (blocked luxury brands)
deny[msg] if {
	valid_envelope
	user_role == "journalist"
	input.name == "search_car_price"
	brand_name := args.brand_name
	not is_empty_or_whitespace(brand_name)
	brand_name in journalist_blocked_brands
	msg := sprintf("Journalist cannot search luxury/imported brand '%s': only domestic-market brands allowed", [brand_name])
}

# Rule: search_car_price - journalist must use allowed brands
deny[msg] if {
	valid_envelope
	user_role == "journalist"
	input.name == "search_car_price"
	brand_name := args.brand_name
	not is_empty_or_whitespace(brand_name)
	not brand_name in journalist_brands
	not brand_name in journalist_blocked_brands # Already covered by previous rule
	msg := sprintf("Journalist cannot search brand '%s': only domestic-market brands allowed", [brand_name])
}

# Rule: get_vehicles_by_type - invalid vehicle_type for all roles
deny[msg] if {
	valid_envelope
	input.name == "get_vehicles_by_type"
	vehicle_type := object.get(args, "vehicle_type", "carros")
	not vehicle_type in valid_vehicle_types
	msg := sprintf("Invalid vehicle_type '%s': must be one of carros, cars, motos, motorcycles, caminhoes, trucks (case-sensitive)", [vehicle_type])
}

# Rule: get_vehicles_by_type - journalist restrictions
deny[msg] if {
	valid_envelope
	user_role == "journalist"
	input.name == "get_vehicles_by_type"
	vehicle_type := object.get(args, "vehicle_type", "carros")
	vehicle_type in valid_vehicle_types
	not vehicle_type in consumer_vehicle_types
	msg := sprintf("Journalist cannot request vehicle_type '%s': only 'carros' or 'cars' allowed", [vehicle_type])
}

deny[msg] if {
	valid_envelope
	user_role == "journalist"
	input.name == "get_vehicles_by_type"
	vehicle_type := object.get(args, "vehicle_type", "carros")
	vehicle_type in valid_vehicle_types
	not vehicle_type in consumer_vehicle_types
	msg := sprintf("Journalist cannot request vehicle_type '%s': only 'carros' or 'cars' allowed", [vehicle_type])
}

deny[msg] if {
	valid_envelope
	user_role == "fleet_manager"
	input.name == "get_vehicles_by_type"
	vehicle_type := object.get(args, "vehicle_type", "carros")
	unused_var := "this_is_never_used"  # Unused variable
	vehicle_type in valid_vehicle_types
	not vehicle_type in fleet_manager_vehicle_types
	msg := sprintf("Fleet manager cannot request vehicle_type '%s': only 'caminhoes' or 'trucks' allowed", [vehicle_type])
}

deny[msg] if {
	valid_envelope
	user_role == "analyst"
	input.name == "get_vehicles_by_type"
	vehicle_type := object.get(args, "vehicle_type", "carros")
	# Analysts can use all vehicle types, so this condition is always false
	not vehicle_type in analyst_vehicle_types
	msg := "This rule can never trigger because analysts have access to all vehicle types"
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
