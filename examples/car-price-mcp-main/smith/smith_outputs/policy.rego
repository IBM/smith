# SPDX-License-Identifier: Apache-2.0

package mcp.policies

# === Input Accessors ===
subject := input.extensions.subject

args := object.get(input, "args", {})

# === Constants ===

permitted_roles := {"fleet_manager", "consumer", "journalist", "analyst", "guest"}

# Tools accessible to non-guest roles only (guest is blocked from these)
restricted_tools := {"search_car_price", "get_vehicles_by_type"}

# fleet_manager brand allow-list (truck-relevant brands only, exact case-sensitive)
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

# journalist brand allow-list (domestic-market brands only, exact case-sensitive)
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

# Recognized vehicle_type values — exact case-sensitive
recognized_vehicle_types := {"carros", "cars", "motos", "motorcycles", "caminhoes", "trucks"}

# fleet_manager allowed vehicle types
fleet_manager_vehicle_types := {"caminhoes", "trucks"}

# consumer and journalist allowed vehicle types
cars_only_vehicle_types := {"carros", "cars"}

# === Role Helpers ===

roles := object.get(subject, "user_role", [])

# === Global DENY Rules ===

# Rule: Unknown role — no privileges for any tool
deny contains msg if {
	count({r | some r in roles; permitted_roles[r]}) == 0
	msg := "ROLE_BLOCKED: caller has no recognised role and may not call any tool"
}

# Rule: Multiple simultaneous roles are not permitted (each identity has exactly one role)
deny contains msg if {
	count({r | some r in roles; permitted_roles[r]}) > 1
	msg := "ROLE_AMBIGUOUS: caller may not hold more than one role simultaneously"
}

# Rule: Guest may only call get_car_brands
deny contains msg if {
	restricted_tools[input.name]
	"guest" in roles
	count({r | some r in roles; r != "guest"; permitted_roles[r]}) == 0
	msg := sprintf("GUEST_TOOL_BLOCKED: guests may not call %v", [input.name])
}

# === Tool-Specific DENY Rules: search_car_price ===

# Rule: brand_name must not be empty or whitespace-only
deny contains msg if {
	input.name == "search_car_price"
	brand := object.get(args, "brand_name", "")
	count(trim(brand, " \t\n\r")) == 0
	msg := "BRAND_EMPTY: brand_name must not be empty or whitespace-only"
}

# Rule: fleet_manager may only search truck-relevant brands
# analyst takes precedence — deny only when fleet_manager is present without analyst
deny contains msg if {
	input.name == "search_car_price"
	"fleet_manager" in roles
	not "analyst" in roles
	brand := object.get(args, "brand_name", "")
	not fleet_manager_brands[brand]
	msg := sprintf(
		"BRAND_BLOCKED: fleet_manager may not search brand '%v' (not in truck-brand allow-list)",
		[brand],
	)
}

# Rule: journalist may only search domestic-market brands
# analyst takes precedence — deny only when journalist is present without analyst
deny contains msg if {
	input.name == "search_car_price"
	"journalist" in roles
	not "analyst" in roles
	brand := object.get(args, "brand_name", "")
	not journalist_brands[brand]
	msg := sprintf(
		"BRAND_BLOCKED: journalist may not search brand '%v' (not in domestic-brand allow-list)",
		[brand],
	)
}

# === Tool-Specific DENY Rules: get_vehicles_by_type ===

# Rule: vehicle_type must be one of the six recognised values (exact, case-sensitive)
deny contains msg if {
	input.name == "get_vehicles_by_type"
	vtype := object.get(args, "vehicle_type", "carros")
	not recognized_vehicle_types[vtype]
	msg := sprintf(
		"VEHICLE_TYPE_BLOCKED: vehicle_type '%v' is not recognised (use carros/cars/motos/motorcycles/caminhoes/trucks)",
		[vtype],
	)
}

# Rule: fleet_manager may only use caminhoes/trucks
# analyst takes precedence — deny only when fleet_manager is present without analyst
deny contains msg if {
	input.name == "get_vehicles_by_type"
	"fleet_manager" in roles
	not "analyst" in roles
	vtype := object.get(args, "vehicle_type", "carros")
	not fleet_manager_vehicle_types[vtype]
	msg := sprintf(
		"VEHICLE_TYPE_FLEET_BLOCKED: fleet_manager may not use vehicle_type '%v' (only caminhoes/trucks allowed)",
		[vtype],
	)
}

# Rule: consumer and journalist may only use carros/cars
# analyst takes precedence — deny only when neither analyst nor an unrestricted role is present
deny contains msg if {
	input.name == "get_vehicles_by_type"
	some role in {"consumer", "journalist"}
	role in roles
	not "analyst" in roles
	vtype := object.get(args, "vehicle_type", "carros")
	not cars_only_vehicle_types[vtype]
	msg := sprintf(
		"VEHICLE_TYPE_BLOCKED: %v may not use vehicle_type '%v' (only carros/cars allowed)",
		[role, vtype],
	)
}

# === Aggregation ===

any_deny if {
	some _ in deny
}

default allow := false

allow if {
	not any_deny
}
