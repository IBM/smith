package policy_test

import data.policy

test_not_allow_1 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you fetch all motos vehicles for me?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_2 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please look up current market prices for Jaguar cars", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Jaguar"}}
}

test_not_allow_3 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please look up Ford vehicle pricing for me", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Ford"}}
}

test_not_allow_4 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please find Audi pricing information", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Audi"}}
}

test_not_allow_5 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you retrieve truck listings from the database?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_not_allow_6 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you get vehicles by type trucks?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "trucks"}}
}

test_not_allow_7 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please get vehicles where vehicle_type is cars", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_not_allow_8 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to search for Toyota car prices for our fleet budget planning", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Toyota"}}
}

test_not_allow_9 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want vehicles of type automobiles", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_not_allow_10 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please provide current market prices for Bentley cars", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Bentley"}}
}

test_not_allow_11 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Could you search for Porsche models and their current market prices?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Porsche"}}
}

test_not_allow_12 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to look up Lexus car prices and models", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Lexus"}}
}

test_not_allow_13 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to get vehicles by type cars", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_not_allow_14 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to search for Mini car prices and models", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Mini"}}
}

test_not_allow_15 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you pull up pricing data for BMW X5 using the search_car_price tool with brand_name \"BMW\"?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "BMW"}}
}

test_not_allow_16 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me vehicles with vehicle_type set to carros", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_not_allow_17 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please search for current Rolls-Royce car prices from the database", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Rolls-Royce"}}
}

test_not_allow_18 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me Land Rover models and their current prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Land Rover"}}
}

test_not_allow_19 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to look up Porsche car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Porsche"}}
}

test_not_allow_20 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to search for Bentley vehicle pricing information", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Bentley"}}
}

test_not_allow_21 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you fetch all cars with vehicle_type cars", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "cars"}}
}

test_not_allow_22 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you get vehicles by type Cars for me?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "cars"}}
}

test_not_allow_23 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please retrieve truck information for my commercial vehicle story", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_not_allow_24 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me all motorcycles available in the system", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_25 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me the vehicle list with vehicle_type set to caminhoes", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_not_allow_26 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you search for Jaguar vehicle pricing information?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Jaguar"}}
}

test_not_allow_27 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to check BMW car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "BMW"}}
}

test_not_allow_28 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to get vehicles by type motos", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_29 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager", "consumer", "journalist", "analyst", "guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Search for car prices with brand name '   '", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": ""}}
}

test_not_allow_30 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to search for Honda car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Honda"}}
}

test_not_allow_31 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need pricing information for Audi cars", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Audi"}}
}

test_not_allow_32 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please fetch motorcycle inventory data", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_33 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you get vehicles by type trucks?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "trucks"}}
}

test_not_allow_34 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me current market prices for Ferrari vehicles", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Ferrari"}}
}

test_not_allow_35 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please search car prices for the brand Audi", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Audi"}}
}

test_not_allow_36 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please find current market prices for Lexus cars", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Lexus"}}
}

test_not_allow_37 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Carol", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "As a journalist covering domestic automotive trends, search for the price of BMW cars using search_car_price with brand_name \"BMW\".", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "BMW"}}
}

test_not_allow_38 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to search for Porsche car models and prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Porsche"}}
}

test_not_allow_39 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Could you show me all caminhoes in the system?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_not_allow_40 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please get me a list of trucks with vehicle_type set to caminhoes", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_not_allow_41 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to look up Ferrari car prices and models", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Ferrari"}}
}

test_not_allow_42 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you help me find pricing data for BMW vehicles?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "BMW"}}
}

test_not_allow_43 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to get vehicles by type cars", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "cars"}}
}

test_not_allow_44 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get vehicles by type motorcycles", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_45 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please look up Audi vehicle prices for me", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Audi"}}
}

test_not_allow_46 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to see your motos inventory", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_47 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please search car prices for the brand Maserati", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Maserati"}}
}

test_not_allow_48 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please search car prices for brand name BMW", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "BMW"}}
}

test_not_allow_49 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you show me motorcycles available for purchase?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_50 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to search for Mercedes car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Mercedes"}}
}

test_not_allow_51 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to get vehicle information for caminhoes", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_not_allow_52 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please retrieve cars from the vehicle database for fleet analysis", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_not_allow_53 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Carol", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I am a journalist investigating the Brazilian trucking industry", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_not_allow_54 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please find pricing data for Alfa Romeo vehicles", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Alfa Romeo"}}
}

test_not_allow_55 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you search for Lexus vehicle pricing information?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Lexus"}}
}

test_not_allow_56 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you help me find pricing information for Audi vehicles?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Audi"}}
}

test_not_allow_57 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Could you search for Ferrari pricing data from the FIPE database?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Ferrari"}}
}

test_not_allow_58 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please retrieve all trucks from the vehicle database", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "trucks"}}
}

test_not_allow_59 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you find Honda vehicle pricing information?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Honda"}}
}

test_not_allow_60 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to see all motorcycles in our fleet", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_61 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Could you search for Alfa Romeo models and their current prices?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Alfa Romeo"}}
}

test_not_allow_62 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to look up Mercedes-Benz car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Mercedes-Benz"}}
}

test_not_allow_63 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you help me find pricing information for Maserati vehicles?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Maserati"}}
}

test_not_allow_64 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Guest", "user_role": ["guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to buy a Ford truck for my business", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Ford"}}
}

test_not_allow_65 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to search for Audi car prices and models", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Audi"}}
}

test_not_allow_66 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to access truck vehicle data for my research", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_not_allow_67 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please find Lamborghini car models and their current prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Lamborghini"}}
}

test_not_allow_68 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get vehicles by type CARS", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "cars"}}
}

test_not_allow_69 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you show me motorcycles available in the system?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_70 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get vehicles by type motorcycles", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motorcycles"}}
}

test_not_allow_71 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you look up BMW car prices for me?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "BMW"}}
}

test_not_allow_72 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you look up Ford vehicle pricing information with brand_name Ford?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Ford"}}
}

test_not_allow_73 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need information about motorcycles you have", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_74 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Carol", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "My editor needs data on import motorcycles for an international feature", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_75 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you help me find Mercedes pricing information?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Mercedes"}}
}

test_not_allow_76 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please look up Mazda pricing information", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Mazda"}}
}

test_not_allow_77 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please search for Audi vehicle pricing information", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Audi"}}
}

test_not_allow_78 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please retrieve vehicles by type motorcycles", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_79 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me all motos available for purchase", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_80 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to search for Ford car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Ford"}}
}

test_not_allow_81 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_car_brands", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager", "consumer", "journalist", "analyst", "guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you provide me with all car manufacturers from the database", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {}}
}

test_not_allow_82 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you search for Ford car prices?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Ford"}}
}

test_not_allow_83 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get vehicles by type motos", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_84 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you fetch all motorcycle brands for my article?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_85 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to search for Kia car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Kia"}}
}

test_not_allow_86 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to search for BMW car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "BMW"}}
}

test_not_allow_87 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please fetch all motorcycles from your catalog", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_88 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to search for Toy car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Toyota"}}
}

test_not_allow_89 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to search for BMW car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "BMW"}}
}

test_not_allow_90 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me vehicles with vehicle_type set to motos", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_91 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need vehicles of type Motorcycles", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motorcycles"}}
}

test_not_allow_92 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Fetch vehicles with type set to caminhoes please", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_not_allow_93 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need pricing information for Lamborghini cars for my research", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Lamborghini"}}
}

test_not_allow_94 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Guest", "user_role": ["guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "As a guest user trying to compare options, please retrieve the vehicle list for motos and search for the price of Ferrari.", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_95 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me car prices for Mercedes-Benz brand please", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Mercedes-Benz"}}
}

test_not_allow_96 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Could you search for pricing information on Mercedes-Benz vehicles?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Mercedes-Benz"}}
}

test_not_allow_97 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to search for Maserati car prices for my article", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Maserati"}}
}

test_not_allow_98 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to look up Alfa Romeo car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Alfa Romeo"}}
}

test_not_allow_99 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please fetch all caminhoes vehicles for me", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_not_allow_100 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please retrieve all carros using vehicle_type carros", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_not_allow_101 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please find me Mazda vehicle pricing data", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Mazda"}}
}

test_not_allow_102 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to get a list of motorcycles from the vehicle database", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motorcycles"}}
}

test_not_allow_103 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you find Rolls-Royce vehicle prices and models for me?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Rolls-Royce"}}
}

test_not_allow_104 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to see all Motos available", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_105 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_car_brands", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager", "consumer", "journalist", "analyst", "guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to see the list of car brands available in the system", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {}}
}

test_not_allow_106 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please retrieve vehicles with vehicle_type trucks", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "trucks"}}
}

test_not_allow_107 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please search car prices for the brand Mini", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Mini"}}
}

test_not_allow_108 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please use get_vehicles_by_type to list all available \"cars\" that match my criteria, specifically looking for models under 200k.", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_not_allow_109 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Could you help me find pricing data for Land Rover vehicles?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Land Rover"}}
}

test_not_allow_110 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please search for Mercedes pricing data", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Mercedes-Benz"}}
}

test_not_allow_111 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to find Jaguar car prices and models", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Jaguar"}}
}

test_not_allow_112 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you look up Bentley car prices for me?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Bentley"}}
}

test_not_allow_113 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me vehicles with type TRUCKS", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "trucks"}}
}

test_not_allow_114 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please retrieve all motos using vehicle_type motos", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_115 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Search for Toyota car prices and models", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Toyota"}}
}

test_not_allow_116 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get me motorcycle brands for my article on two-wheelers with vehicle_type motos", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_117 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to find Honda vehicle pricing information", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Honda"}}
}

test_not_allow_118 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to get vehicles by type motos", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_119 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Search for Lamborghini vehicle pricing data", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Lamborghini"}}
}

test_not_allow_120 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me pricing data for Porsche vehicles", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Porsche"}}
}

test_not_allow_121 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to search for Land Rover car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Land Rover"}}
}

test_not_allow_122 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to see all trucks using get_vehicles_by_type", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_not_allow_123 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you help me find pricing information for Mini vehicles?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Mini"}}
}

test_not_allow_124 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Alice", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get vehicle listings for trucks.", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_not_allow_125 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_car_brands", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager", "consumer", "journalist", "analyst", "guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me all available car brands", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {}}
}

test_not_allow_126 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please retrieve vehicles with vehicle_type motos", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_not_allow_127 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to search for Rolls-Royce car pricing data", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Rolls-Royce"}}
}

test_not_allow_128 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to find Subaru car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Subaru"}}
}

test_not_allow_129 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to get vehicles by type caminhoes", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_not_allow_130 if {
    not policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to get vehicles by type carros", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_1 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please search for Mercedes-Benz car models and prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Mercedes-Benz"}}
}

test_allow_2 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you help me find Honda vehicle pricing information?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Honda"}}
}

test_allow_3 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please search for Iveco car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Iveco"}}
}

test_allow_4 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get vehicles by type motorcycles", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motorcycles"}}
}

test_allow_5 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you find pricing for Mer vehicles?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Mercedes-Benz"}}
}

test_allow_6 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to see all caminhoes vehicles", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_allow_7 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please look up Ford car models and their current market prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Ford"}}
}

test_allow_8 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_car_brands", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I require all car brand data for my market analysis report", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {}}
}

test_allow_9 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please fetch vehicles by type Trucks", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "trucks"}}
}

test_allow_10 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_car_brands", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "What car brands are available for purchase?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {}}
}

test_allow_11 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me all carros available", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_12 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you help me find pricing information for Toyota vehicles?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Toyota"}}
}

test_allow_13 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please look up pricing data for MAN brand", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "MAN"}}
}

test_allow_14 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to check Volkswagen car prices and models", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Volkswagen"}}
}

test_allow_15 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_car_brands", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I'm looking to buy a car and need to see all available brands", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {}}
}

test_allow_16 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you look up Honda vehicle prices?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Honda"}}
}

test_allow_17 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need Honda car price information for my story", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Honda"}}
}

test_allow_18 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Could you help me find Ford car prices from the database?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Ford"}}
}

test_allow_19 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Search for MAN vehicle prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "MAN"}}
}

test_allow_20 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to search for Toyota car prices for my article", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Toyota"}}
}

test_allow_21 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to browse carros in your inventory", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_22 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_car_brands", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Could you help me get the list of car manufacturers?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {}}
}

test_allow_23 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to look up Chevrolet car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Chevrolet"}}
}

test_allow_24 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to get vehicles by type carros", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_25 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me vehicles of type caminhoes", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_allow_26 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you look up pricing information for DAF vehicles?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "DAF"}}
}

test_allow_27 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to fetch all motorcycles from the vehicle database", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_allow_28 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get vehicles by type Caminhoes", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_allow_29 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to search for Toyota car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Toyota"}}
}

test_allow_30 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you help me find BMW vehicle pricing information?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "BMW"}}
}

test_allow_31 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please find Ford vehicle pricing information", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Ford"}}
}

test_allow_32 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please show me vehicles with vehicle_type set to cars", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_33 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please help me find Nissan vehicle pricing", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Nissan"}}
}

test_allow_34 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please retrieve vehicles with vehicle_type set to caminhoes", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_allow_35 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you search for Chevrolet vehicle pricing information?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Chevrolet"}}
}

test_allow_36 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you find pricing information for Mercedes-Benz models?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Mercedes-Benz"}}
}

test_allow_37 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to search for Toyota car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Toyota"}}
}

test_allow_38 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you help me find pricing information for Peugeot vehicles?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Peugeot"}}
}

test_allow_39 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me car prices for the Citroën brand please", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Citroën"}}
}

test_allow_40 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_car_brands", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you show me the list of car manufacturers?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {}}
}

test_allow_41 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to get vehicles by type cars for my report", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_42 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you help me find pricing information for Fiat vehicles?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Fiat"}}
}

test_allow_43 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to find pricing information for Scania vehicles", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Scania"}}
}

test_allow_44 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to search car prices for Toyota brand for my market analysis", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Toyota"}}
}

test_allow_45 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to search for Toyota car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Toyota"}}
}

test_allow_46 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_car_brands", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please retrieve all car manufacturer brands from the database", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {}}
}

test_allow_47 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_car_brands", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me all automotive brands in your database for research purposes", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {}}
}

test_allow_48 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to search for Fiat car prices for my article", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Fiat"}}
}

test_allow_49 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you look up current market prices for Scania models?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Scania"}}
}

test_allow_50 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you show me all cars in the vehicle database?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_51 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_car_brands", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I would like to see all available car brands", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {}}
}

test_allow_52 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Could you search for Citroën vehicle pricing data?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Citroën"}}
}

test_allow_53 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to search for car prices for the Peugeot brand", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Peugeot"}}
}

test_allow_54 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please look up pricing for Volkswagen vehicles", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Volkswagen"}}
}

test_allow_55 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need current market prices for Mercedes-Benz vehicles", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Mercedes-Benz"}}
}

test_allow_56 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to look up Chevrolet car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Chevrolet"}}
}

test_allow_57 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me the caminhoes vehicle type information", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_allow_58 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to get vehicles by type carros for my analysis", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_59 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you search for Jeep vehicle prices?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Jeep"}}
}

test_allow_60 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please find me Honda vehicle pricing data", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Honda"}}
}

test_allow_61 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Search for Volvo car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Volvo"}}
}

test_allow_62 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please search for BMW car models and their prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "BMW"}}
}

test_allow_63 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Search car prices for Mercedes-Benz", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Mercedes-Benz"}}
}

test_allow_64 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to get all vehicles by type caminhoes", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_allow_65 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you find me pricing data for Volkswagen vehicles?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Volkswagen"}}
}

test_allow_66 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to get vehicles by type trucks", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_allow_67 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you get vehicles by type cars for my research?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_68 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to look up car prices for Citroën brand", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Citroën"}}
}

test_allow_69 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_car_brands", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you show me the complete list of car brands available?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {}}
}

test_allow_70 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please fetch vehicles with type trucks", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_allow_71 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please fetch vehicle information for cars", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "cars"}}
}

test_allow_72 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please retrieve truck vehicle listings for my research", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_allow_73 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you find pricing information for Caoa Chery vehicles?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Caoa Chery", "vehicle_type": "carros"}}
}

test_allow_74 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_car_brands", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Could you provide me with the complete list of available car manufacturers?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {}}
}

test_allow_75 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Could you fetch all carros from the vehicle system?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_76 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please retrieve vehicle data with type carros", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_77 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to search car prices for Caoa Chery brand", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Caoa Chery"}}
}

test_allow_78 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_car_brands", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need all car brands for my automotive industry article", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {}}
}

test_allow_79 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me motorcycles from the vehicle database", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_allow_80 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please get vehicles by type motos", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_allow_81 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Search car prices for Scania brand", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Scania"}}
}

test_allow_82 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please find Honda car models and their current market prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Honda"}}
}

test_allow_83 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please search car prices for brand name Peugeot", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Peugeot"}}
}

test_allow_84 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_car_brands", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to get all available car brands for our fleet procurement", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {}}
}

test_allow_85 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please search for Mercedes-Benz vehicle pricing", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Mercedes-Benz"}}
}

test_allow_86 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to retrieve all cars using get_vehicles_by_type", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_87 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please find BMW vehicle prices and models for me", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "BMW"}}
}

test_allow_88 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you fetch all trucks using vehicle_type trucks", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "trucks"}}
}

test_allow_89 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_car_brands", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["guest"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please display the car brand options available", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {}}
}

test_allow_90 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to search for Volkswagen car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Volkswagen"}}
}

test_allow_91 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to check Volvo model prices from the FIPE database", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Volvo"}}
}

test_allow_92 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please get me pricing data for Volvo brand vehicles", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Volvo"}}
}

test_allow_93 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you help me find Honda vehicle pricing information?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Honda"}}
}

test_allow_94 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need Jeep car price information for my article", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Jeep"}}
}

test_allow_95 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get vehicles by type trucks", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_allow_96 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to retrieve all vehicles of type motos", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_allow_97 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to get vehicles by type cars", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_98 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Could you search for Renault vehicle pricing information?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Renault"}}
}

test_allow_99 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get vehicles by type cars", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "cars"}}
}

test_allow_100 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to search for Toyota car prices and models", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Toyota"}}
}

test_allow_101 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to look up honda pricing information", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Honda"}}
}

test_allow_102 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_car_brands", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me all available car manufacturers for my industry research", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {}}
}

test_allow_103 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Could you help me find Nissan vehicle pricing?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Nissan"}}
}

test_allow_104 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Search for Ford vehicle pricing information", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Ford"}}
}

test_allow_105 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please retrieve vehicles with type motorcycles", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_allow_106 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to search for DAF car prices and models", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "DAF"}}
}

test_allow_107 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you help me find pricing information for Hyundai vehicles?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Hyundai"}}
}

test_allow_108 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please get vehicles where vehicle_type is trucks", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "trucks"}}
}

test_allow_109 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you search for Volkswagen car pricing information?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Volkswagen"}}
}

test_allow_110 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please search for Hyundai pricing data", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Hyundai"}}
}

test_allow_111 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please fetch all carros vehicles for my article", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_112 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me vehicle data with vehicle_type carros", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_113 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to search for Honda car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Honda"}}
}

test_allow_114 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to look up Volkswagen pricing data", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Volkswagen"}}
}

test_allow_115 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to check Toyota prices before making a purchase decision", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Toyota"}}
}

test_allow_116 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get vehicles by type carros", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_117 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me vehicles of type CARROS", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_118 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to look up Hyundai car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Hyundai"}}
}

test_allow_119 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get vehicles by type caminhoes", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_allow_120 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to check current MAN model prices and specifications", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "MAN"}}
}

test_allow_121 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to find current market prices for Iveco models", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Iveco"}}
}

test_allow_122 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_car_brands", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Can you fetch the complete automotive brand list for statistical analysis?", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {}}
}

test_allow_123 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to search for Nissan car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Nissan"}}
}

test_allow_124 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please search for TOYOTA car models and prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Toyota"}}
}

test_allow_125 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please look up car prices for brand name Caoa Chery", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Caoa Chery"}}
}

test_allow_126 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to search for Volkswagen car prices", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Volkswagen"}}
}

test_allow_127 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["consumer"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please show me all cars you have", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_128 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Please look up Ford car model prices for my analysis", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Ford"}}
}

test_allow_129 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "search_car_price", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to find Renault car prices for my research", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"brand_name": "Renault"}}
}

test_allow_130 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Get vehicles by type bikes", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_allow_131 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "Show me the motos vehicle type data", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "motos"}}
}

test_allow_132 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["analyst"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I want to retrieve all trucks from the system", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}

test_allow_133 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["journalist"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need vehicle data by type for my transportation report - show me cars", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "carros"}}
}

test_allow_134 if {
    policy.allow with input as {"kind": "tool_call", "action": "execute", "name": "get_vehicles_by_type", "extensions": {"subject": {"claims": {}, "user_name": "Bob", "user_role": ["fleet_manager"]}, "headers": {"x-request-id": "req-7f2a", "x-forwarded-for": "10.0.1.5"}, "labels": ["internal"], "agent": {"input": "I need to get all trucks for our commercial fleet expansion", "session_id": "sess-9f3a", "conversation_id": "conv-17eb", "turn": 4}, "object": {"managed_by": "tool", "trust_domain": "internal"}}, "args": {"vehicle_type": "caminhoes"}}
}