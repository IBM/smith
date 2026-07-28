# SPDX-License-Identifier: Apache-2.0

package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "arguments", {})

# === Constants ===

known_roles := {"fleet_manager", "consumer", "journalist", "analyst", "guest"}

known_vehicle_types := {"carros", "cars", "motos", "motorcycles", "caminhoes", "trucks"}

fleet_manager_vehicle_types := {"caminhoes", "trucks"}

consumer_journalist_vehicle_types := {"carros", "cars"}

fleet_manager_brands := {
	"Scania", "Volvo", "Mercedes-Benz", "MAN", "DAF",
	"Iveco", "Ford", "Volkswagen",
}

journalist_allowed_brands := {
	"Fiat", "Chevrolet", "Volkswagen", "Hyundai", "Toyota",
	"Renault", "Honda", "Nissan", "Jeep", "Peugeot",
	"Citroën", "Caoa Chery",
}

# === Tool Argument Keys ===
allowed_arg_keys := {
	"get_car_brands": set(),
	"search_car_price": {"brand_name"},
	"get_vehicles_by_type": {"vehicle_type"},
}

# === Envelope Validation ===
valid_envelope if {
	input.kind == "tool_call"
	input.action == "execute"
	input.name != ""
}

# user_role is an array; resolve the effective role
effective_role := role if {
	some role in subject.user_role
	role in known_roles
}

# === DENY: Unknown role ===
deny["Unknown role: access denied"] if {
	not effective_role
}

# === DENY: Guest restricted to get_car_brands only ===
deny["Guests may only call get_car_brands"] if {
	effective_role == "guest"
	input.name != "get_car_brands"
}

# === DENY: search_car_price — empty or whitespace brand_name ===
deny["brand_name must not be empty or whitespace"] if {
	input.name == "search_car_price"
	brand := object.get(args, "brand_name", "")
	trim_space(brand) == ""
}

# === DENY: search_car_price — fleet_manager brand restriction ===
deny["fleet_manager may only search truck-relevant brands"] if {
	input.name == "search_car_price"
	effective_role == "fleet_manager"
	brand := object.get(args, "brand_name", "")
	not brand in fleet_manager_brands
}

# === DENY: search_car_price — journalist brand restriction (domestic-market only) ===
deny["journalist may only search domestic-market brands"] if {
	input.name == "search_car_price"
	effective_role == "journalist"
	brand := object.get(args, "brand_name", "")
	not brand in journalist_allowed_brands
}

# === DENY: get_vehicles_by_type — unrecognized vehicle_type for all roles ===
deny["vehicle_type must be a recognized value"] if {
	input.name == "get_vehicles_by_type"
	vtype := object.get(args, "vehicle_type", "")
	not vtype in known_vehicle_types
}

# === DENY: get_vehicles_by_type — fleet_manager restricted to trucks ===
deny["fleet_manager may only use caminhoes or trucks vehicle_type"] if {
	input.name == "get_vehicles_by_type"
	effective_role == "fleet_manager"
	vtype := object.get(args, "vehicle_type", "")
	vtype in known_vehicle_types
	not vtype in fleet_manager_vehicle_types
}

# === DENY: get_vehicles_by_type — consumer restricted to cars ===
deny["consumer may only use carros or cars vehicle_type"] if {
	input.name == "get_vehicles_by_type"
	effective_role == "consumer"
	vtype := object.get(args, "vehicle_type", "")
	vtype in known_vehicle_types
	not vtype in consumer_journalist_vehicle_types
}

# === DENY: get_vehicles_by_type — journalist restricted to cars ===
deny["journalist may only use carros or cars vehicle_type"] if {
	input.name == "get_vehicles_by_type"
	effective_role == "journalist"
	vtype := object.get(args, "vehicle_type", "")
	vtype in known_vehicle_types
	not vtype in consumer_journalist_vehicle_types
}

# === Final ALLOW ===
any_deny if {
	deny[_]
}

allow if {
	valid_envelope
	not any_deny
	effective_role
}
