"""
Zoho Books MCP Tools
====================
LangChain tool wrappers for Zoho Books MCP server.
Follows the same pattern as gmail_tools.py
"""

from langchain.tools import tool
from src.Zoho_MCP.zoho_mcp_client import ZohoMCPClient
from typing import Optional, List, Dict
import json

# Initialize MCP client once (lazy connection - connects on first tool use)
client = ZohoMCPClient()

def ensure_connected():
    """Ensure client is connected before tool use"""
    if client.session is None:
        client.connect()


# ==========================================================
# INVOICE MANAGEMENT TOOLS
# ==========================================================

@tool("zoho_create_invoice")
def zoho_create_invoice(customer_id: str, line_items: List[Dict], due_date: Optional[str] = None):
    """
    Create a new invoice in Zoho Books.
    
    Args:
        customer_id: ID of the customer
        line_items: List of line items [{"item_id": "...", "quantity": 1, "rate": 100}]
        due_date: Optional due date (YYYY-MM-DD format)
    """
    ensure_connected()
    # The MCP server uses **kwargs, so pass params directly (not wrapped in 'kwargs')
    args = {
        "customer_id": customer_id,
        "line_items": line_items
    }
    # Only include due_date if it's actually provided (not None)
    if due_date is not None:
        args["due_date"] = due_date
    
    return client.call_tool("create_invoice", args)


@tool("zoho_list_invoices")
def zoho_list_invoices(max_results: int = 10, status: Optional[str] = None):
    """
    List invoices from Zoho Books.
    
    Args:
        max_results: Maximum number of invoices to return (default: 10)
        status: Optional filter by status (sent, draft, overdue, paid, void, unpaid). If not provided, returns all invoices.
    """
    ensure_connected()
    args = {"max_results": max_results}
    if status:
        args["status"] = status
    return client.call_tool("list_invoices", args)


@tool("zoho_get_invoice")
def zoho_get_invoice(invoice_id: str):
    """
    Get details of a specific invoice.
    
    Args:
        invoice_id: ID of the invoice
    """
    ensure_connected()
    return client.call_tool("get_invoice", {"invoice_id": invoice_id})


# @tool("zoho_email_invoice")
# def zoho_email_invoice(invoice_id: str, to_emails: str):
#     """
#     Email an invoice to recipients.
    
#     Args:
#         invoice_id: ID of the invoice
#         to_emails: Comma-separated email addresses
#     """
#     ensure_connected()
#     return client.call_tool("email_invoice", {
#         "invoice_id": invoice_id,
#         "to_emails": to_emails
#     })


@tool("zoho_record_payment")
def zoho_record_payment(invoice_id: str, amount: float, payment_mode: str = "cash"):
    """
    Record a payment for an invoice.
    
    Args:
        invoice_id: ID of the invoice
        amount: Payment amount
        payment_mode: Payment method (cash, check, credit_card, bank_transfer, etc.)
    """
    ensure_connected()
    return client.call_tool("record_payment", {
        "invoice_id": invoice_id,
        "amount": amount,
        "payment_mode": payment_mode
    })


@tool("zoho_send_payment_reminder")
def zoho_send_payment_reminder(invoice_id: str):
    """
    Send a payment reminder for an invoice.
    
    Args:
        invoice_id: ID of the invoice
    """
    ensure_connected()
    return client.call_tool("send_payment_reminder", {"invoice_id": invoice_id})


@tool("zoho_void_invoice")
def zoho_void_invoice(invoice_id: str):
    """
    Void an invoice.
    
    Args:
        invoice_id: ID of the invoice to void
    """
    ensure_connected()
    return client.call_tool("void_invoice", {"invoice_id": invoice_id})


@tool("zoho_mark_invoice_as_sent")
def zoho_mark_invoice_as_sent(invoice_id: str):
    """
    Mark an invoice as sent.
    
    Args:
        invoice_id: ID of the invoice
    """
    ensure_connected()
    return client.call_tool("mark_invoice_as_sent", {"invoice_id": invoice_id})


# ==========================================================
# CONTACT MANAGEMENT TOOLS
# ==========================================================

@tool("zoho_create_customer")
def zoho_create_customer(customer_name: str, email: str, company_name: Optional[str] = None):
    """
    Create a new customer in Zoho Books.
    
    Args:
        customer_name: Name of the customer
        email: Email address
        company_name: Optional company name
    """
    ensure_connected()
    # Map customer_name to contact_name for the MCP server
    args = {"contact_name": customer_name, "email": email}
    if company_name:
        args["company_name"] = company_name
    return client.call_tool("create_customer", args)


@tool("zoho_create_vendor")
def zoho_create_vendor(vendor_name: str, email: str, company_name: Optional[str] = None):
    """
    Create a new vendor in Zoho Books.
    
    Args:
        vendor_name: Name of the vendor
        email: Email address
        company_name: Optional company name
    """
    ensure_connected()
    # Map vendor_name to contact_name for the MCP server
    args = {"contact_name": vendor_name, "email": email}
    if company_name:
        args["company_name"] = company_name
    return client.call_tool("create_vendor", args)


@tool("zoho_list_contacts")
def zoho_list_contacts(max_results: int = 10, contact_type: Optional[str] = None):
    """
    List contacts from Zoho Books.
    
    Args:
        max_results: Maximum number of contacts to return (default: 10)
        contact_type: Optional filter by type (customer, vendor). If not provided, returns all contacts.
    """
    ensure_connected()
    args = {"max_results": max_results}
    if contact_type:
        args["contact_type"] = contact_type
    return client.call_tool("list_contacts", args)


@tool("zoho_get_contact")
def zoho_get_contact(contact_id: str):
    """
    Get details of a specific contact.
    
    Args:
        contact_id: ID of the contact
    """
    ensure_connected()
    return client.call_tool("get_contact", {"contact_id": contact_id})


@tool("zoho_update_contact")
def zoho_update_contact(contact_id: str, updates: str):
    """
    Update a contact's information.
    
    Args:
        contact_id: ID of the contact
        updates: JSON string of fields to update
    """
    ensure_connected()
    return client.call_tool("update_contact", {
        "contact_id": contact_id,
        "updates": json.loads(updates)
    })


@tool("zoho_delete_contact")
def zoho_delete_contact(contact_id: str):
    """
    Delete a contact from Zoho Books.
    
    Args:
        contact_id: ID of the contact to delete
    """
    ensure_connected()
    return client.call_tool("delete_contact", {"contact_id": contact_id})


@tool("zoho_email_statement")
def zoho_email_statement(contact_id: str, to_email: str):
    """
    Email a statement to a contact.
    
    Args:
        contact_id: ID of the contact
        to_email: Email address to send to
    """
    ensure_connected()
    return client.call_tool("email_statement", {
        "contact_id": contact_id,
        "to_email": to_email
    })


# ==========================================================
# EXPENSE MANAGEMENT TOOLS
# ==========================================================

@tool("zoho_create_expense")
def zoho_create_expense(account_id: str, amount: float, date: str, description: Optional[str] = None):
    """
    Create a new expense in Zoho Books.
    
    Args:
        account_id: ID of the expense account
        amount: Expense amount
        date: Expense date (YYYY-MM-DD format)
        description: Optional description
    """
    ensure_connected()
    args = {"account_id": account_id, "amount": amount, "date": date}
    if description:
        args["description"] = description
    return client.call_tool("create_expense", args)


@tool("zoho_update_expense")
def zoho_update_expense(expense_id: str, updates: str):
    """
    Update an expense.
    
    Args:
        expense_id: ID of the expense
        updates: JSON string of fields to update
    """
    ensure_connected()
    return client.call_tool("update_expense", {
        "expense_id": expense_id,
        "updates": json.loads(updates)
    })


@tool("zoho_list_expenses")
def zoho_list_expenses(max_results: int = 10):
    """
    List expenses from Zoho Books.
    
    Args:
        max_results: Maximum number of expenses to return
    """
    ensure_connected()
    return client.call_tool("list_expenses", {"max_results": max_results})


@tool("zoho_get_expense")
def zoho_get_expense(expense_id: str):
    """
    Get details of a specific expense.
    
    Args:
        expense_id: ID of the expense
    """
    ensure_connected()
    return client.call_tool("get_expense", {"expense_id": expense_id})


@tool("zoho_categorize_expense")
def zoho_categorize_expense(expense_id: str, category_id: str):
    """
    Categorize an expense.
    
    Args:
        expense_id: ID of the expense
        category_id: ID of the category
    """
    ensure_connected()
    return client.call_tool("categorize_expense", {
        "expense_id": expense_id,
        "category_id": category_id
    })


# ==========================================================
# ITEM MANAGEMENT TOOLS
# ==========================================================

@tool("zoho_create_item")
def zoho_create_item(item_name: str, rate: float, description: Optional[str] = None):
    """
    Create a new item/product in Zoho Books.
    
    Args:
        item_name: Name of the item
        rate: Item price/rate
        description: Optional description
    """
    ensure_connected()
    # Map item_name to name for the MCP server
    args = {"name": item_name, "rate": rate}
    if description:
        args["description"] = description
    return client.call_tool("create_item", args)


@tool("zoho_update_item")
def zoho_update_item(item_id: str, updates: str):
    """
    Update an item.
    
    Args:
        item_id: ID of the item
        updates: JSON string of fields to update
    """
    ensure_connected()
    return client.call_tool("update_item", {
        "item_id": item_id,
        "updates": json.loads(updates)
    })


@tool("zoho_list_items")
def zoho_list_items(max_results: int = 10):
    """
    List items from Zoho Books.
    
    Args:
        max_results: Maximum number of items to return
    """
    ensure_connected()
    return client.call_tool("list_items", {"max_results": max_results})


@tool("zoho_get_item")
def zoho_get_item(item_id: str):
    """
    Get details of a specific item.
    
    Args:
        item_id: ID of the item
    """
    ensure_connected()
    return client.call_tool("get_item", {"item_id": item_id})


# ==========================================================
# SALES ORDER MANAGEMENT TOOLS
# ==========================================================

@tool("zoho_create_sales_order")
def zoho_create_sales_order(customer_id: str, line_items: str):
    """
    Create a new sales order in Zoho Books.
    
    Args:
        customer_id: ID of the customer
        line_items: JSON string of line items
    """
    ensure_connected()
    return client.call_tool("create_sales_order", {
        "customer_id": customer_id,
        "line_items": json.loads(line_items)
    })


@tool("zoho_update_sales_order")
def zoho_update_sales_order(salesorder_id: str, updates: str):
    """
    Update a sales order.
    
    Args:
        salesorder_id: ID of the sales order
        updates: JSON string of fields to update
    """
    ensure_connected()
    return client.call_tool("update_sales_order", {
        "salesorder_id": salesorder_id,
        "updates": json.loads(updates)
    })


@tool("zoho_convert_to_invoice")
def zoho_convert_to_invoice(salesorder_id: str):
    """
    Convert a sales order to an invoice.
    
    Args:
        salesorder_id: ID of the sales order
    """
    ensure_connected()
    return client.call_tool("convert_to_invoice", {"salesorder_id": salesorder_id})


@tool("zoho_list_sales_orders")
def zoho_list_sales_orders(max_results: int = 10, status: Optional[str] = None):
    """
    List sales orders from Zoho Books.
    
    Args:
        max_results: Maximum number of sales orders to return (default: 10)
        status: Optional filter by status (draft, open, closed, void). If not provided, returns all sales orders.
    """
    ensure_connected()
    args = {"max_results": max_results}
    if status:
        args["status"] = status
    return client.call_tool("list_sales_orders", args)


@tool("zoho_get_sales_order")
def zoho_get_sales_order(salesorder_id: str):
    """
    Get details of a specific sales order.
    
    Args:
        salesorder_id: ID of the sales order
    """
    ensure_connected()
    return client.call_tool("get_sales_order", {"salesorder_id": salesorder_id})


# ==========================================================
# ALL TOOLS LIST (for easy import)
# ==========================================================

ALL_ZOHO_TOOLS = [
    # Invoice management (8 tools)
    zoho_create_invoice,
    zoho_list_invoices,
    zoho_get_invoice,
    # zoho_email_invoice,
    zoho_record_payment,
    zoho_send_payment_reminder,
    zoho_void_invoice,
    zoho_mark_invoice_as_sent,
    
    # Contact management (7 tools)
    zoho_create_customer,
    zoho_create_vendor,
    zoho_list_contacts,
    zoho_get_contact,
    zoho_update_contact,
    zoho_delete_contact,
    zoho_email_statement,
    
    # Expense management (5 tools)
    zoho_create_expense,
    zoho_update_expense,
    zoho_list_expenses,
    zoho_get_expense,
    zoho_categorize_expense,
    
    # Item management (4 tools)
    zoho_create_item,
    zoho_update_item,
    zoho_list_items,
    zoho_get_item,
    
    # Sales order management (5 tools)
    zoho_create_sales_order,
    zoho_update_sales_order,
    zoho_convert_to_invoice,
    zoho_list_sales_orders,
    zoho_get_sales_order,
]
