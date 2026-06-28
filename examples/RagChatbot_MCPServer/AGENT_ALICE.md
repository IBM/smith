# AgentAlice Usage Guidelines

<<<<<<< HEAD


## Policy Enforcement Architecture (Multi-Layer Protection)
- **Layer 1 - LLMGuard**: Scans inputs/outputs for sensitive data patterns and prompt injection attempts
- **Layer 2 - OPA Policies**: Role-based field filtering and access control enforcement and Data Filtering where tools include sensitive data but policies filter based on permissions


## AgentAlice Tools & Capabilities

### HR Tools
- **view_team_compensation**: View team compensation data with realistic HR information. 
Parameters: time_range (default: "last_quarter"), format (default: "JSON"), include_benefits (default: True). 
Returns (JSON): employee_name, title, department, level, hire_date, base_salary, bonus_target, actual_bonus_2024, performance_rating, next_review_date, stock_grant_value, benefits_value, total_compensation, ssn, personal_email, home_address, emergency_contact*, bank_account, healthcare_plan, healthcare_id 

- **ask_for_salary**: Query salary and compensation information. 
Parameters: question (str).
Returns: base_salary, total_compensation, title, department, level, bonus_target, actual_bonus, performance_rating, ssn, personal_email*, home_address* 

- **export_compensation_data**: Export team compensation data for business analysis. Generates detailed compensation exports with historical salary progression, performance correlation analysis, budget planning data. 

Returns (JSON): employee_id, name, title, level, current_salary, total_comp_2024, performance_rating, salary_history, bonus_history, ssn, personal_email, home_address, bank_account

- **email_compensation_report**: Email compensation report with OPA domain validation. 
Parameters: destination, report_data, external_sharing

### Communication Tools
- **send_email**: Draft and send an email for user. 
Parameters: email_content, attached_file. 
Returns: Confirmation of sending and email content
- **create_ticket**: Create an inquiry ticket for user. 
Parameters: ticket_content. 
Returns: Confirmation of creating a ticket, and summary of ticket
- **submit_ticket**: Submit an inquiry ticket for user. 
Parameters: ticket_content. 
Returns: Confirmation of submission, and summary of ticket

### Procurement Tools
- **purchase**: Process purchase requests with realistic vendor catalog and approval workflows. 
Parameters: amount, product_name. 
Returns: Purchase approval details, order information, vendor details
- **return_product**: Request to make a return of a product. 
Parameters: amount, product_name. 
Returns: Confirmation of return submission with product name

### Information & Policy Tools
- **ask_for_workpolicy**: Query and answer questions from a preloaded PDF document that includes working policy and regulation information. 
Parameters: question. 
Returns: Answer generated using retrieved context from the PDF
- **get_w2_form**: Request to get my w2 form. 
Returns: Redirect message to create ticket and reach out to HR team

### Utility Tools
- **export_content_as_file**: Export data/content to a file. 
Parameters: data, file_name. 
Returns: Confirmation if data was successfully exported, and summary of data content
- **set_user_role**: Set the current user role for policy enforcement. 
Parameters: user_role (user, manager). 
Returns: Confirmation of role change
- **test_purchase_policy**: Test the purchase policy enforcement directly. 
Parameters: amount, product. 
Returns: Result of policy test

## Requirements

### Data Protection rules (Salary and Compensation)

#### What You Can Do
- **Employees**: Query your own salary data only via **ask_for_salary** tool
- **Managers**: View only the requested manager's team compensation data (employee name, title, salary, bonus, department, hire date) via **view_team_compensation** tool

#### What You Cannot Do
- **Employees** cannot view team compensation data, bonus, or hire date information (**view_team_compensation** tool blocked)
-  **Managers** cannot see any team's Social Security Numbers (SSN), Home addresses, Bank account numbers, Tax ID numbers

### Data Export

#### What You Can Do
- **Managers**: Export team compensation data in CSV, PDF, JSON format 

#### What You Cannot Do
- **Employees** cannot export team compensation data 

### External Sharing

#### What You Can Do
- **Managers**: Share information externally by email with:
  1. Non-compensation and non-salary data only  

#### What You Cannot Do
- **No one** can share compensation data externally to non-@ibm.com email addresses
- **No one** can send to blocked domains: gmail.com, yahoo.com, hotmail.com, outlook.com, personal.com 

### Purchases (Business Policy)

#### What You Can Do
- **Employees**: Buy products under $200 
- **Managers**: Buy products under $1,000 

#### What You Cannot Do
- **Employees** cannot buy products $200+ without manager approval 
- **Managers** cannot buy products $1,000+ 

### Security Controls via Prompt

#### What the System can Block
- Attempts to "ignore all policies" 
- Requests to "bypass security" 
- "Override all policies" commands 
- Attempts to "show all SSN data" 

=======
## AgentAlice Tools & Capabilities

### HR Tools
- **view_team_compensation**: View team compensation data with realistic HR information. Returns: employee_name, title, department, level, hire_date, base_salary, bonus_target, actual_bonus_2024, performance_rating, next_review_date, stock_grant_value, benefits_value, total_compensation, ssn*, personal_email*, home_address*, emergency_contact*, bank_account*, healthcare_plan*, healthcare_id* 
- **ask_for_salary**: Query salary and compensation information with realistic data analysis. Provides insights on market salary benchmarks, internal pay equity analysis, career progression paths. Returns: base_salary, total_compensation, title, department, level, bonus_target, actual_bonus, performance_rating, ssn*, personal_email*, home_address* 
- **export_compensation_data**: Export team compensation data for business analysis. Generates detailed compensation exports with historical salary progression, performance correlation analysis, budget planning data. Returns: employee_id, name, title, level, current_salary, total_comp_2024, performance_rating, salary_history, bonus_history, ssn*, personal_email*, home_address*, bank_account* 
- **email_compensation_report**: Email compensation report with OPA domain validation. Parameters: destination, report_data, external_sharing

### Communication Tools
- **send_email**: Draft and send an email for user. Parameters: email_content, attached_file. Returns: Confirmation of sending and email content
- **create_ticket**: Create an inquiry ticket for user. Parameters: ticket_content. Returns: Confirmation of creating a ticket, and summary of ticket
- **submit_ticket**: Submit an inquiry ticket for user. Parameters: ticket_content. Returns: Confirmation of submission, and summary of ticket

### Procurement Tools
- **purchase**: Process purchase requests with realistic vendor catalog and approval workflows. Parameters: amount, product_name. Returns: Purchase approval details, order information, vendor details
- **return_product**: Request to make a return of a product. Parameters: amount, product_name. Returns: Confirmation of return submission with product name

### Information & Policy Tools
- **ask_for_workpolicy**: Query and answer questions from a preloaded PDF document that includes working policy and regulation information. Parameters: question. Returns: Answer generated using retrieved context from the PDF
- **get_w2_form**: Request to get my w2 form. Returns: Redirect message to create ticket and reach out to HR team

### Utility Tools
- **export_content_as_file**: Export data/content to a file. Parameters: data, file_name. Returns: Confirmation if data was successfully exported, and summary of data content
- **set_user_role**: Set the current user role for policy enforcement. Parameters: user_role (user, manager). Returns: Confirmation of role change
- **test_purchase_policy**: Test the purchase policy enforcement directly. Parameters: amount, product. Returns: Result of policy test

## Requirements

### Data Protection rules (Salary and Compensation)

#### What You Can Do
- **Employees**: Query your own salary data only via **ask_for_salary** tool
- **Managers**: View only the requested manager's team compensation data (employee name, title, salary, bonus, department, hire date) via **view_team_compensation** tool

#### What You Cannot Do
- **Employees** cannot view team compensation data, bonus, or hire date information (**view_team_compensation** tool blocked)
-  **Managers** cannot see any team's Social Security Numbers (SSN), Home addresses, Bank account numbers, Tax ID numbers

### Data Export

#### What You Can Do
- **Managers**: Export team compensation data in CSV, PDF, JSON format 

#### What You Cannot Do
- **Employees** cannot export team compensation data 

### External Sharing

#### What You Can Do
- **Managers**: Share information externally by email with:
  1. Non-compensation and non-salary data only  

#### What You Cannot Do
- **No one** can share compensation data externally 
- **No one** can send to blocked domains: gmail.com, yahoo.com, hotmail.com, outlook.com, personal.com 

### Purchases (Business Policy)

#### What You Can Do
- **Employees**: Buy products under $200 
- **Managers**: Buy products under $1,000 

#### What You Cannot Do
- **Employees** cannot buy products $200+ without manager approval 
- **Managers** cannot buy products $1,000+ 

### Security Controls (Multi-Layer Protection)

#### Examples on what the System can Block
- Attempts to "ignore all policies" 
- Requests to "bypass security" 
- "Override all policies" commands 
- Attempts to "show all SSN data" **OPA policies block** + **LLMGuard redacts** any leaked sensitive data
>>>>>>> 6ca24fa (fix: Guidelines for Agent Alice)

#### Policy Enforcement Architecture
- **Layer 1 - LLMGuard**: Scans inputs/outputs for sensitive data patterns and prompt injection attempts
- **Layer 2 - OPA Policies**: Role-based field filtering and access control enforcement and Data Filtering where tools include sensitive data but policies filter based on permissions

