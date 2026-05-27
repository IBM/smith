import os
from dotenv import load_dotenv

def raw_create_ticket(ticket_content) -> str:
    """Create an inquery ticket for user"""
    return "I created the ticket for you and will send to our hr team, below is the ticket content: "+ticket_content

def raw_submit_ticket(ticket_content) -> str:
    """Submit the inquery ticket for user"""
    return "I submited the ticket to our hr team. below is the details of the ticket: "+ticket_content 

def raw_purchase(amount, product_name) -> str:
    """Request to purchase a product"""
    return "You are approved, "+str(product_name)+" will cost "+str(amount)+" dollars, the money has been issued to your account"

def raw_return(amount, product_name) -> str:
    """Return a product"""
    return "The return request was approved. I submited a return request for "+str(product_name)+". It will refund you "+str(amount)+" dollars"
