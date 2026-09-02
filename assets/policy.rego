# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "args", {})

# === Constants ===

recognized_roles := {"fleet_manager", "consumer", "journalist", "analyst", "guest"}

recognized_vehicle_types := {"carros", "cars", "motos", "motorcycles", "caminhoes", "trucks"}

vehicle_types_by_role := {
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

brands_by_role := {
	"fleet_manager": fleet_manager_brands,
	"journalist": journalist_brands,
}

# === Global DENY/ALLOW Rules ===

# NOTE: subject.user_role is a single-element array (e.g. ["fleet_manager"]),
# not a scalar string, so membership checks must unwrap it via `some`.
role_recognized if {
	some role in subject.user_role
	role in recognized_roles
}

# guidance.txt: "Unknown Roles" — a request whose user_role matches none of
# the five defined roles has no privileges and may call no tool.
deny[msg] if {
	not role_recognized
	msg := sprintf("user_role '%v' is not a recognized role and may not call any tool", [subject.user_role])
}

# A caller identity must assert exactly one role; claiming multiple roles at
# once is not a valid identity under guidance.txt and must be denied for
# every tool, regardless of whether each individual asserted role would
# otherwise be permitted.
deny[msg] if {
	count(subject.user_role) != 1
	msg := sprintf("user_role '%v' must assert exactly one role", [subject.user_role])
}

# === Tool-Specific DENY/ALLOW Rules ===

# guidance.txt: "Tool Access by Role" — a guest may only call get_car_brands.
deny[msg] if {
	"guest" in subject.user_role
	input.name != "get_car_brands"
	msg := sprintf("guest role may not call tool '%v'; only get_car_brands is allowed", [input.name])
}

# guidance.txt: "Vehicle Type Restrictions" — allowed vehicle_type values
# depend on role; any value outside the six recognized values is denied for
# every role (do not rely on the backend's silent fallback to "carros").
deny[msg] if {
	input.name == "get_vehicles_by_type"
	not args.vehicle_type in recognized_vehicle_types
	some role in subject.user_role
	role in recognized_roles
	msg := sprintf("vehicle_type '%v' is not a recognized value", [args.vehicle_type])
}

deny[msg] if {
	input.name == "get_vehicles_by_type"
	args.vehicle_type in recognized_vehicle_types
	some role in subject.user_role
	role in recognized_roles
	allowed := vehicle_types_by_role[role]
	not args.vehicle_type in allowed
	msg := sprintf("role '%v' is not permitted to use vehicle_type '%v'", [role, args.vehicle_type])
}

# guidance.txt: "Brand Restrictions" — allowed brand_name values depend on
# role; empty/whitespace-only brand_name is denied for all roles.
deny[msg] if {
	input.name == "search_car_price"
	trim_space(object.get(args, "brand_name", "")) == ""
	some role in subject.user_role
	role in recognized_roles
	msg := "brand_name must not be empty or whitespace-only"
}

deny[msg] if {
	input.name == "search_car_price"
	trim_space(object.get(args, "brand_name", "")) != ""
	some role in subject.user_role
	allowed := brands_by_role[role]
	not args.brand_name in allowed
	msg := sprintf("role '%v' is not permitted to search brand '%v'", [role, args.brand_name])
}

# === Final ALLOW ===
allow if {
	count(deny) == 0
}
