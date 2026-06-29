from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional

class HRDatabase:
    """Realistic HR employee database with compensation data"""
    
    def __init__(self):
        self.employees = {
            "emp_001": {
                "employee_id": "emp_001",
                "employee_name": "Alice Johnson",
                "title": "Senior Software Engineer",
                "department": "Engineering",
                "manager_id": "manager_123",
                "hire_date": "2022-03-15",
                "employment_status": "Active",
                "location": "San Francisco, CA",
                "level": "L5",
                "team": "Platform Engineering"
            },
            "emp_002": {
                "employee_id": "emp_002", 
                "employee_name": "Bob Chen",
                "title": "Software Engineer",
                "department": "Engineering",
                "manager_id": "manager_123",
                "hire_date": "2023-01-10",
                "employment_status": "Active",
                "location": "Austin, TX",
                "level": "L4",
                "team": "Platform Engineering"
            },
            "emp_003": {
                "employee_id": "emp_003",
                "employee_name": "Carol Davis",
                "title": "Product Manager",
                "department": "Product",
                "manager_id": "manager_456",
                "hire_date": "2021-08-20",
                "employment_status": "Active", 
                "location": "New York, NY",
                "level": "L6",
                "team": "Core Product"
            },
            "emp_004": {
                "employee_id": "emp_004",
                "employee_name": "David Wilson",
                "title": "Data Scientist",
                "department": "Engineering",
                "manager_id": "manager_123",
                "hire_date": "2022-11-05",
                "employment_status": "Active",
                "location": "Seattle, WA", 
                "level": "L5",
                "team": "Data Platform"
            },
            "emp_005": {
                "employee_id": "emp_005",
                "employee_name": "Eva Martinez",
                "title": "UX Designer",
                "department": "Design",
                "manager_id": "manager_789",
                "hire_date": "2023-06-12",
                "employment_status": "Active",
                "location": "Los Angeles, CA",
                "level": "L4",
                "team": "User Experience"
            }
        }
        
        self.managers = {
            "manager_123": {
                "manager_id": "manager_123",
                "name": "Sarah Thompson",
                "title": "Engineering Manager",
                "department": "Engineering",
                "direct_reports": ["emp_001", "emp_002", "emp_004"],
                "team_name": "Platform Engineering",
                "budget_authority": 150000,
                "hire_date": "2020-05-15"
            },
            "manager_456": {
                "manager_id": "manager_456", 
                "name": "Michael Rodriguez",
                "title": "Product Manager",
                "department": "Product",
                "direct_reports": ["emp_003"],
                "team_name": "Core Product",
                "budget_authority": 200000,
                "hire_date": "2019-02-10"
            },
            "manager_789": {
                "manager_id": "manager_789",
                "name": "Jennifer Kim",
                "title": "Design Manager", 
                "department": "Design",
                "direct_reports": ["emp_005"],
                "team_name": "User Experience",
                "budget_authority": 120000,
                "hire_date": "2021-01-20"
            }
        }

class CompensationDatabase:
    """Realistic compensation and payroll data"""
    
    def __init__(self):
        self.compensation_data = {
            "emp_001": {
                "employee_id": "emp_001",
                "base_salary": 145000,
                "bonus_target": 20000,
                "actual_bonus_2023": 22000,
                "actual_bonus_2024": 18500,
                "stock_grant_value": 50000,
                "benefits_value": 28000,
                "total_compensation": 193000,
                "pay_grade": "E5",
                "last_review_date": "2024-03-15",
                "next_review_date": "2025-03-15",
                "performance_rating": "Exceeds Expectations",
                "salary_history": [
                    {"year": 2022, "base_salary": 130000, "bonus": 15000},
                    {"year": 2023, "base_salary": 140000, "bonus": 22000},
                    {"year": 2024, "base_salary": 145000, "bonus": 18500}
                ]
            },
            "emp_002": {
                "employee_id": "emp_002",
                "base_salary": 120000,
                "bonus_target": 15000,
                "actual_bonus_2023": 16500,
                "actual_bonus_2024": 14200,
                "stock_grant_value": 35000,
                "benefits_value": 26000,
                "total_compensation": 161000,
                "pay_grade": "E4",
                "last_review_date": "2024-01-10",
                "next_review_date": "2025-01-10", 
                "performance_rating": "Meets Expectations",
                "salary_history": [
                    {"year": 2023, "base_salary": 115000, "bonus": 16500},
                    {"year": 2024, "base_salary": 120000, "bonus": 14200}
                ]
            },
            "emp_003": {
                "employee_id": "emp_003",
                "base_salary": 155000,
                "bonus_target": 25000,
                "actual_bonus_2023": 28000,
                "actual_bonus_2024": 24500,
                "stock_grant_value": 60000,
                "benefits_value": 30000,
                "total_compensation": 209500,
                "pay_grade": "P6",
                "last_review_date": "2024-08-20",
                "next_review_date": "2025-08-20",
                "performance_rating": "Exceeds Expectations",
                "salary_history": [
                    {"year": 2021, "base_salary": 140000, "bonus": 20000},
                    {"year": 2022, "base_salary": 148000, "bonus": 25000},
                    {"year": 2023, "base_salary": 152000, "bonus": 28000},
                    {"year": 2024, "base_salary": 155000, "bonus": 24500}
                ]
            },
            "emp_004": {
                "employee_id": "emp_004",
                "base_salary": 138000,
                "bonus_target": 18000,
                "actual_bonus_2023": 19500,
                "actual_bonus_2024": 17200,
                "stock_grant_value": 45000,
                "benefits_value": 27500,
                "total_compensation": 182700,
                "pay_grade": "E5",
                "last_review_date": "2024-11-05",
                "next_review_date": "2025-11-05",
                "performance_rating": "Meets Expectations",
                "salary_history": [
                    {"year": 2022, "base_salary": 125000, "bonus": 12000},
                    {"year": 2023, "base_salary": 135000, "bonus": 19500},
                    {"year": 2024, "base_salary": 138000, "bonus": 17200}
                ]
            },
            "emp_005": {
                "employee_id": "emp_005",
                "base_salary": 110000,
                "bonus_target": 12000,
                "actual_bonus_2023": 0,  # Started mid-year
                "actual_bonus_2024": 13200,
                "stock_grant_value": 30000,
                "benefits_value": 25000,
                "total_compensation": 148200,
                "pay_grade": "D4",
                "last_review_date": "2024-06-12",
                "next_review_date": "2025-06-12",
                "performance_rating": "Exceeds Expectations",
                "salary_history": [
                    {"year": 2023, "base_salary": 105000, "bonus": 0},
                    {"year": 2024, "base_salary": 110000, "bonus": 13200}
                ]
            }
        }
        
        # Sensitive data that should be protected
        self.sensitive_data = {
            "emp_001": {
                "ssn": "123-45-6789",
                "personal_email": "alice.johnson@gmail.com",
                "home_address": "123 Oak Street, San Francisco, CA 94102",
                "emergency_contact": "John Johnson (spouse) - 555-0123",
                "bank_account": "****1234",
                "healthcare_plan": "Premium PPO",
                "healthcare_id": "HC123456789"
            },
            "emp_002": {
                "ssn": "234-56-7890", 
                "personal_email": "bob.chen@yahoo.com",
                "home_address": "456 Pine Avenue, Austin, TX 78701",
                "emergency_contact": "Lisa Chen (spouse) - 555-0456",
                "bank_account": "****5678",
                "healthcare_plan": "Standard HMO",
                "healthcare_id": "HC234567890"
            }
            # ... more sensitive data
        }

class PurchaseDatabase:
    """Realistic purchase and procurement data"""
    
    def __init__(self):
        self.purchase_categories = {
            "office_supplies": {
                "budget_limit": 500,
                "approval_required": False,
                "examples": ["pens", "paper", "notebooks", "folders"]
            },
            "computer_equipment": {
                "budget_limit": 3000,
                "approval_required": True,
                "examples": ["laptop", "monitor", "keyboard", "mouse", "webcam"]
            },
            "software": {
                "budget_limit": 1000,
                "approval_required": True,
                "examples": ["license", "subscription", "tool", "platform"]
            },
            "furniture": {
                "budget_limit": 2000,
                "approval_required": True,
                "examples": ["desk", "chair", "lamp", "bookshelf"]
            }
        }
        
        self.vendor_catalog = {
            "laptop": {
                "Dell XPS 13": {"price": 1299, "category": "computer_equipment"},
                "MacBook Pro 14": {"price": 2399, "category": "computer_equipment"},
                "ThinkPad X1": {"price": 1899, "category": "computer_equipment"}
            },
            "monitor": {
                "Dell 27 4K": {"price": 599, "category": "computer_equipment"},
                "LG UltraWide": {"price": 799, "category": "computer_equipment"},
                "Samsung 32": {"price": 449, "category": "computer_equipment"}
            },
            "chair": {
                "Herman Miller Aeron": {"price": 1395, "category": "furniture"},
                "Steelcase Leap": {"price": 996, "category": "furniture"},
                "IKEA Markus": {"price": 229, "category": "furniture"}
            },
            "mouse": {
                "Logitech MX Master": {"price": 99, "category": "computer_equipment"},
                "Apple Magic Mouse": {"price": 79, "category": "computer_equipment"},
                "Microsoft Surface Mouse": {"price": 49, "category": "computer_equipment"}
            }
        }

# Global instances
hr_db = HRDatabase()
comp_db = CompensationDatabase()
purchase_db = PurchaseDatabase()