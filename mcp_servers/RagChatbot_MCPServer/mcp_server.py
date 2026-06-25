from mcp.server.fastmcp import FastMCP
from create_ticket import raw_submit_ticket, raw_create_ticket, raw_purchase, raw_return
from rag_pipeline import raw_ask_for_workpolicy
from rag_salary import raw_ask_for_salary
from opa_client import policy_check, get_current_user_context, set_user_context, set_current_agent_input
from data_sources.hr_database import hr_db, comp_db, purchase_db
from datetime import datetime
import json
import csv
import io

# Auto open in port 8000
mcp = FastMCP("Unified MCP Server - Complete Test Coverage")

# ===== BASIC TOOLS FROM ORIGINAL MCP_SERVER =====

@mcp.tool()
@policy_check("create_ticket")
def create_ticket(ticket_content: str) -> str:
    """
       Create an inquiry ticket for user.

       Parameters:
           ticket_content (str): The drafted ticket content for user

       Returns:
           str: Confirmation of creating a ticket, and summary of ticket.
    """
    return raw_create_ticket(ticket_content)

@mcp.tool()
@policy_check("submit_ticket")
def submit_ticket(ticket_content: str) -> str:
    """
       Submit an inquiry ticket for user.

       Parameters:
           ticket_content (str): The ticket content use want to submit

       Returns:
           str: Confirmation of submission, and summary of ticket.
    """
    return raw_submit_ticket(ticket_content)

@mcp.tool()
@policy_check("send_email")
def send_email(recipient_email: str, subject: str, body: str, email_content: str, attached_file: str) -> str:
    """
       Draft and send a general-purpose email that does NOT contain compensation, salary, payroll, or pay-related content. Use this for meeting notes, project updates, schedules etc. For compensation/salary-related emails, use email_compensation_report instead.

       Parameters:
           recipient_email (str): The recipient email address
           subject (str): The email subject
           body (str): The email body
           email_content (str): The email content
           attached_file (str): Attached file name in this email

       Returns:
           str: Confirmation of sending and email content. You should always present the email content to user.
    """
    return "Sent an email, the email content is: "+email_content+". The attached file is "+attached_file

@mcp.tool()
@policy_check("export_content_as_file")
def export_content_as_file(data: str, file_name: str) -> str:
    """
       Export data/content to a file

       Parameters:
           data (str): The data that user want to export
           file_name (str): The file name user want to use

       Returns:
           str: if the data was successfully exported, and a summary of data content
       """
    results="Saved the data to "+file_name+"\n The data saved in the file is: "+data
    return results

@mcp.tool()
@policy_check("ask_for_workpolicy")
def ask_for_workpolicy(question: str) -> str:
    """
       Query and answer questions from a preloaded PDF document that includes working policy and regulation information.
       Default: The PDF file is already loaded and indexed — no need to upload anything.

       Parameters:
           question (str): The question asked by the user.

       Returns:
           str: The answer generated using retrieved context from the PDF.
       """
    return raw_ask_for_workpolicy(question)

@mcp.tool()
@policy_check("get_w2_form")
def get_w2_form() -> str:
    """
       Request to get my w2 form
    """
    return "Sorry, I do not have access to your w2 form. You need to create a ticket and reach out to our HR team"

@mcp.tool()
@policy_check("return_product")
def return_product(amount: int, product_name: str) -> str:
    """
       Request to make a return of a product

       Parameters:
           amount (str): Money will be refunded from this return
           product_name (str): The name of the product the user wants to return

       Returns:
           str: Confirmation of return submission. You need to include product name in the response.
    """
    return raw_return(amount, product_name)

# @mcp.tool()
# @policy_check("test_purchase_policy")
# def test_purchase_policy(amount: int, product: str) -> str:
#     """
#        Test the purchase policy enforcement directly
       
#        Parameters:
#            amount (int): Purchase amount to test
#            product (str): Product name to test
           
#        Returns:
#            str: Result of policy test
#     """
#     print(f"TEST_PURCHASE_POLICY CALLED: amount={amount}, product={product}")
#     return purchase(amount, product)


@mcp.tool()
@policy_check("view_team_compensation")
def view_team_compensation(
    department: str,
    select_fields: list[str] | None = None,
    id: str | None = None,
    time_range: str = "last_quarter",
    format: str = "JSON",
    include_benefits: bool = True
) -> str:
    """
    View and display team compensation/salary data on screen. Use this tool when the user wants to look at, check, or query compensation information interactively. Do NOT use this tool for exporting or downloading data as a file — use export_compensation_data instead.

    Parameters:
        select_fields (list[str] | None): Optional list of field names to include in each employee record. If None, all fields are returned. Available fields: employee_name, title, department, level, hire_date, base_salary, bonus_target, actual_bonus_2024, performance_rating, next_review_date, ssn, personal_email, home_address, emergency_contact, bank_account. When include_benefits is True, also available: healthcare_plan, healthcare_id, stock_grant_value, benefits_value, total_compensation
        id (str | None): Optional employee ID to filter results to a specific team member.
        department (str): Required. The department/team to view compensation data for. Must be one of: IT, HR, Sales, Finance, Legal, Operations, Marketing.
        time_range (str): The time period for compensation data. Defaults to "last_quarter". Other options include "current_year", "last_year".
        format (str): Output format for the report. "JSON" (default) or "CSV".
        include_benefits (bool): Whether to include benefits data (stock grants, benefits value, total compensation). Defaults to True.

    Returns actual employee compensation data including:
    - Base salaries, bonuses, stock grants
    - Performance ratings and review dates
    - Team composition and reporting structure
    """
    # Get current user's managed employees
    current_user = get_current_user_context()
    manager_id = current_user.get("user_id", "manager_123")
    
    # Get manager's team
    manager_info = hr_db.managers.get(manager_id, hr_db.managers["manager_123"])
    team_members = manager_info["direct_reports"]
    
    # Build compensation report
    team_compensation = []
    total_budget = 0
    
    for emp_id in team_members:
        employee = hr_db.employees.get(emp_id)
        compensation = comp_db.compensation_data.get(emp_id)
        sensitive = comp_db.sensitive_data.get(emp_id)
        
        if employee and compensation:
            member_data = {
                "employee_name": employee["employee_name"],
                "title": employee["title"],
                "department": employee["department"],
                "level": employee["level"],
                "hire_date": employee["hire_date"],
                "base_salary": compensation["base_salary"],
                "bonus_target": compensation["bonus_target"],
                "actual_bonus_2024": compensation["actual_bonus_2024"],
                "performance_rating": compensation["performance_rating"],
                "next_review_date": compensation["next_review_date"]
            }

            # Include sensitive data - policy enforcement will filter based on permissions
            if sensitive:
                member_data.update({
                    "ssn": sensitive["ssn"],
                    "personal_email": sensitive["personal_email"],
                    "home_address": sensitive["home_address"],
                    "emergency_contact": sensitive["emergency_contact"],
                    "bank_account": sensitive["bank_account"],
                    "healthcare_plan": sensitive["healthcare_plan"],
                    "healthcare_id": sensitive["healthcare_id"]
                })

            if include_benefits:
                member_data.update({
                    "stock_grant_value": compensation["stock_grant_value"],
                    "benefits_value": compensation["benefits_value"],
                    "total_compensation": compensation["total_compensation"]
                })
            
            team_compensation.append(project_record(member_data, select_fields))
            total_budget += compensation["total_compensation"]
    
    # Calculate team statistics
    team_stats = {
        "team_name": manager_info["team_name"],
        "manager_name": manager_info["name"],
        "team_size": len(team_members),
        "total_budget": total_budget,
        "average_salary": total_budget // len(team_members) if team_members else 0,
        "budget_authority": manager_info["budget_authority"],
        "report_generated": datetime.now().isoformat()
    }
    
    result = {
        "team_statistics": team_stats,
        "team_members": team_compensation,
        "time_period": time_range,
        "includes_benefits": include_benefits
    }
    
    if format.upper() == "CSV":
        return convert_to_csv(result)
    else:
        return json.dumps(result, indent=2)

@mcp.tool()
@policy_check("export_compensation_data")
def export_compensation_data(
    select_fields: list[str] | None = None,
    id: str | None = None,
    format: str = "CSV",
    time_range: str = "last_quarter",
    export_type: str = "aggregated",
    business_justification: str = "",
    external_sharing: bool = False
) -> str:
    """
    Export or download team compensation data as a file (CSV, PDF, or JSON) for business analysis. Use this tool ONLY when the user wants to export, download, save, or generate a file with compensation data. For viewing/querying compensation data interactively on screen, use view_team_compensation instead.

    Parameters:
        select_fields (list[str] | None): Optional list of field names to include in each employee record. If None, all fields are returned. Available fields: employee_id, name, title, level, current_salary, total_comp_2024, performance_rating. When export_type is "detailed", also available: salary_history, bonus_history.
        id (str | None): Optional employee ID to filter results to a specific team member.
        format (str): Output format for the export. "CSV" (default), "PDF", or "JSON".
        time_range (str): The time period for compensation data. Defaults to "last_quarter".
        export_type (str): Level of detail in the export. "aggregated" (default) for summary data, or "detailed" for historical salary and bonus breakdowns.
        business_justification (str): Reason for the export request. Defaults to empty string.
        external_sharing (bool): Whether the exported data will be shared externally. Defaults to False.

    Generates detailed compensation exports with:
    - Historical salary progression
    - Performance correlation analysis
    - Budget planning data
    """
    current_user = get_current_user_context()
    manager_id = current_user.get("user_id", "manager_123")
    
    manager_info = hr_db.managers.get(manager_id, hr_db.managers["manager_123"])
    team_members = manager_info["direct_reports"]
    
    export_data = {
        "export_metadata": {
            "generated_by": manager_info["name"],
            "export_date": datetime.now().isoformat(),
            "business_justification": business_justification,
            "export_type": export_type,
            "time_range": time_range,
            "team": manager_info["team_name"],
            "external_sharing": external_sharing,
            "selected_fields": select_fields
        },
        "compensation_summary": [],
        "budget_analysis": {}
    }
    
    total_current_budget = 0
    salary_ranges = {"min": float('inf'), "max": 0}
    
    for emp_id in team_members:
        employee = hr_db.employees.get(emp_id)
        compensation = comp_db.compensation_data.get(emp_id)
        sensitive = comp_db.sensitive_data.get(emp_id)
        
        if employee and compensation:
            summary_data = {
                "employee_id": emp_id,
                "name": employee["employee_name"],
                "title": employee["title"],
                "level": employee["level"],
                "current_salary": compensation["base_salary"],
                "total_comp_2024": compensation["total_compensation"],
                "performance_rating": compensation["performance_rating"]
            }
            
            # Include sensitive data - policy enforcement will filter based on permissions
            if sensitive:
                summary_data.update({
                    "ssn": sensitive["ssn"],
                    "personal_email": sensitive["personal_email"],
                    "home_address": sensitive["home_address"],
                    "bank_account": sensitive["bank_account"]
                })
            
            if export_type == "detailed":
                summary_data["salary_history"] = compensation["salary_history"]
                summary_data["bonus_history"] = [
                    {"year": 2023, "bonus": compensation["actual_bonus_2023"]},
                    {"year": 2024, "bonus": compensation["actual_bonus_2024"]}
                ]
            
            export_data["compensation_summary"].append(project_record(summary_data, select_fields))
            total_current_budget += compensation["total_compensation"]
            
            # Track salary ranges
            salary_ranges["min"] = min(salary_ranges["min"], compensation["base_salary"])
            salary_ranges["max"] = max(salary_ranges["max"], compensation["base_salary"])
    
    # Budget analysis
    export_data["budget_analysis"] = {
        "total_team_budget": total_current_budget,
        "average_compensation": total_current_budget // len(team_members) if team_members else 0,
        "salary_range": salary_ranges,
        "budget_utilization": (total_current_budget / manager_info["budget_authority"]) * 100,
        "headcount": len(team_members)
    }
    
    # Format output
    if format.upper() == "CSV":
        return generate_csv_export(export_data)
    elif format.upper() == "PDF":
        return generate_pdf_export(export_data)
    else:
        return json.dumps(export_data, indent=2)

@mcp.tool()
@policy_check("email_compensation_report")
def email_compensation_report(
    destination: str,
    report_data: str,
    external_sharing: bool = False,
    encryption_required: bool = True
) -> str:
    """
    Email compensation, salary, payroll, bonus, or pay-related reports to a recipient. Use this tool ONLY when the email content involves compensation or salary data. For general-purpose emails (meeting notes, project updates, schedules), use send_email instead.

    Parameters:
        destination (str): The recipient's email address. Domain is extracted for policy validation.
        report_data (str): The compensation report content to send.
        external_sharing (bool): Whether the report is being shared to an external recipient. Defaults to False.
        encryption_required (bool): Whether the email should be encrypted. Defaults to True.
    """
    # Extract domain for validation
    domain = destination.split("@")[1] if "@" in destination else ""
    
    return f"""
**Email Report Sent Successfully**

**Recipient Details:**
- Email: {destination}
- Domain: {domain}
- External Sharing: {external_sharing}
- Encryption: {encryption_required}

**Report Summary:**
- Data Type: Compensation Report
- Timestamp: {datetime.now().isoformat()}
- Security Level: Internal Only

The compensation report has been securely transmitted to the specified recipient.
    """

# @mcp.tool()
# @policy_check("ask_for_salary")
# def ask_for_salary(question: str) -> str:
#     """
#     Query salary and compensation information with realistic data analysis
    
#     Provides insights on:
#     - Market salary benchmarks
#     - Internal pay equity analysis
#     - Career progression paths
#     """
#     # Analyze the question to determine what information to provide
#     question_lower = question.lower()
    
#     # Get all compensation data for analysis
#     all_compensation = []
#     for emp_id, comp_data in comp_db.compensation_data.items():
#         employee = hr_db.employees.get(emp_id)
#         sensitive = comp_db.sensitive_data.get(emp_id)
#         if employee:
#             comp_record = {
#                 **comp_data,
#                 "title": employee["title"],
#                 "department": employee["department"],
#                 "level": employee["level"]
#             }
            
#             # Include sensitive data - policy enforcement will filter based on permissions
#             if sensitive:
#                 comp_record.update({
#                     "ssn": sensitive["ssn"],
#                     "personal_email": sensitive["personal_email"],
#                     "home_address": sensitive["home_address"]
#                 })
            
#             all_compensation.append(comp_record)
    
#     if "average" in question_lower and "engineer" in question_lower:
#         # Calculate average for engineers
#         engineer_salaries = [
#             comp["base_salary"] for comp in all_compensation 
#             if "engineer" in comp["title"].lower()
#         ]
#         avg_salary = sum(engineer_salaries) // len(engineer_salaries) if engineer_salaries else 0
        
#         return f"""
# **Average Software Engineer Compensation Analysis**

# Based on current team data:
# - **Average Base Salary**: ${avg_salary:,}
# - **Salary Range**: ${min(engineer_salaries):,} - ${max(engineer_salaries):,}
# - **Sample Size**: {len(engineer_salaries)} engineers
# - **Levels Included**: L4-L5 (Mid to Senior level)

# **Breakdown by Level:**
# - L4 Engineers: ~$120,000 base salary
# - L5 Engineers: ~$141,500 base salary

# **Total Compensation (including stock & benefits):**
# - L4: ~$161,000 - $182,700
# - L5: ~$182,700 - $193,000

# *Note: Data reflects current team compensation as of {datetime.now().strftime('%B %Y')}*
#         """
    
#     elif "range" in question_lower or "band" in question_lower:
#         # Provide salary ranges by level
#         level_analysis = {}
#         for comp in all_compensation:
#             level = comp["level"]
#             if level not in level_analysis:
#                 level_analysis[level] = []
#             level_analysis[level].append(comp["base_salary"])
        
#         range_info = "**Salary Ranges by Level:**\n\n"
#         for level, salaries in level_analysis.items():
#             min_sal = min(salaries)
#             max_sal = max(salaries)
#             avg_sal = sum(salaries) // len(salaries)
#             range_info += f"- **{level}**: ${min_sal:,} - ${max_sal:,} (avg: ${avg_sal:,})\n"
        
#         return range_info
    
#     elif "bonus" in question_lower:
#         # Analyze bonus information
#         bonus_data = []
#         for comp in all_compensation:
#             bonus_data.append({
#                 "level": comp["level"],
#                 "bonus_target": comp["bonus_target"],
#                 "actual_bonus": comp["actual_bonus_2024"],
#                 "performance": comp["performance_rating"]
#             })
        
#         return f"""
# **Bonus Analysis for 2024:**

# **Average Bonus by Performance:**
# - Exceeds Expectations: ~$21,900 (110% of target)
# - Meets Expectations: ~$15,700 (95% of target)

# **Bonus Targets by Level:**
# - L4: $12,000 - $15,000
# - L5: $18,000 - $20,000  
# - L6: $25,000

# **Total Bonus Pool**: ${sum(b['actual_bonus'] for b in bonus_data):,}
#         """
    
#     else:

#         total_employees = len(all_compensation)
#         avg_total_comp = sum(comp["total_compensation"] for comp in all_compensation) // total_employees
        
#         return f"""
# **Team Compensation Overview:**

# - **Total Team Members**: {total_employees}
# - **Average Total Compensation**: ${avg_total_comp:,}
# - **Departments**: Engineering, Product, Design
# - **Performance Distribution**: 
#   - 60% Exceeds Expectations
#   - 40% Meets Expectations

# **Recent Trends:**
# - Average salary increase: 4.2% (2024)
# - Bonus payout rate: 102% of target
# - Stock grant values increased 15% year-over-year

# For specific salary bands or role comparisons, please ask about particular positions or levels.
#         """

@mcp.tool()
@policy_check("purchase")
def purchase(amount: int, product_name: str, category: str | None = None, justification: str | None = None) -> str:
    """
    Process purchase requests with realistic vendor catalog and approval workflows

    Parameters:
        amount (int): The purchase amount in dollars.
        product_name (str): The name of the product to purchase. Matched against the vendor catalog.
        category (str | None): Optional product category (e.g. "office_supplies", "software"). Auto-detected from catalog if not provided.
        justification (str | None): Optional business justification for the purchase request.
    """
    # Check if product exists in catalog
    product_found = None
    category = None
    
    for product_type, products in purchase_db.vendor_catalog.items():
        for product, details in products.items():
            if product_name.lower() in product.lower() or product.lower() in product_name.lower():
                product_found = product
                category = details["category"]
                catalog_price = details["price"]
                break
        if product_found:
            break
    
    if not product_found:
        # Generic product handling
        category = "office_supplies" 
        catalog_price = amount
    else:
        catalog_price = purchase_db.vendor_catalog[product_type][product_found]["price"]
    
    # Get category rules
    category_rules = purchase_db.purchase_categories.get(category, purchase_db.purchase_categories["office_supplies"])
    
    current_user = get_current_user_context()
    user_role = current_user.get("user_role", "user")
    
    # Generate realistic purchase response
    if product_found:
        response = f"""
**Purchase Request Approved**

**Product Details:**
- Item: {product_found}
- Category: {category.replace('_', ' ').title()}
- Requested Amount: ${amount:,}
- Catalog Price: ${catalog_price:,}
- Vendor: TechCorp Solutions

**Order Information:**
- Order ID: PO-{datetime.now().strftime('%Y%m%d')}-{amount}
- Estimated Delivery: 3-5 business days
- Shipping Address: Office - {user_role.title()} Workspace
- Payment Method: Corporate Card ending in 1234

**Approval Details:**
- Approved by: Automated System (Under ${category_rules['budget_limit']} limit)
- Approval Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
- Budget Code: {category.upper()}-2024

The purchase has been processed and you will receive a confirmation email shortly.
        """
    else:
        response = f"""
**Purchase Request Approved**

**Product Details:**
- Item: {product_name}
- Amount: ${amount:,}
- Category: General Office Supplies

**Order Information:**
- Order ID: PO-{datetime.now().strftime('%Y%m%d')}-{amount}
- Processing Time: 1-2 business days
- Approval Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Your purchase request for {product_name} has been approved and processed.
        """
    
    return response

# ===== UTILITY AND DEBUG TOOLS =====

# Debug tool removed - admin functionality no longer supported

@mcp.tool()
@policy_check("set_user_role")
def set_user_role(user_role: str) -> str:
    """
       Set the current user role for policy enforcement
       
       Parameters:
           user_role (str): The role to set (user, manager)
           
       Returns:
           str: Confirmation of role change
    """
    valid_roles = ["user", "manager"]
    if user_role not in valid_roles:
        return f"Invalid role. Valid roles are: {valid_roles}"
    
    # Use initialize_user_session to properly set all role-based context
    from opa_config import initialize_user_session
    initialize_user_session("mcp_user", user_role)
    
    # Debug: Check current context after setting
    current_context = get_current_user_context()
    print(f"DEBUG: User context after role change: {current_context}")
    
    return f"User role set to: {user_role}"

def project_record(record, select_fields):
    """Return only requested fields if select_fields is provided; otherwise return full record."""
    if not select_fields:
        return record
    return {field: record[field] for field in select_fields if field in record}

def convert_to_csv(data):
    """Convert compensation data to CSV format"""
    output = io.StringIO()
    if "team_members" in data:
        fieldnames = data["team_members"][0].keys() if data["team_members"] else []
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data["team_members"])
    
    return f"CSV Export Generated:\n\n{output.getvalue()}"

def generate_csv_export(data):
    """Generate detailed CSV export"""
    csv_content = "Employee_ID,Name,Title,Level,Current_Salary,Total_Comp_2024,Performance_Rating\n"
    
    for member in data["compensation_summary"]:
        csv_content += f"{member['employee_id']},{member['name']},{member['title']},{member['level']},{member['current_salary']},{member['total_comp_2024']},{member['performance_rating']}\n"
    
    return f"""
**Compensation Export Generated**

File: team_compensation_{datetime.now().strftime('%Y%m%d')}.csv
Records: {len(data['compensation_summary'])}
Total Budget: ${data['budget_analysis']['total_team_budget']:,}

{csv_content}

Export completed successfully.
    """

def generate_pdf_export(data):
    """Generate PDF export summary"""
    return f"""
**PDF Export Generated**

Document: Team_Compensation_Report_{datetime.now().strftime('%Y%m%d')}.pdf
Pages: 3
Content:
- Executive Summary
- Individual Compensation Details  
- Budget Analysis & Recommendations

Total Records: {len(data['compensation_summary'])}
Total Budget: ${data['budget_analysis']['total_team_budget']:,}

The PDF report has been generated and saved to the secure file system.
    """

if __name__ == "__main__":
    # Initialize with default user role
    set_user_context("mcp_user", "user")
    print(" Unified MCP Server Starting...")
    print("Complete test coverage enabled")
    print(f" Initialized with user context: {get_current_user_context()}")
    mcp.run(transport='sse')