"""
Gmail MCP Tools
===============
LangChain tool wrappers for Gmail MCP server.
Follows the same pattern as github_tools.py
"""

from langchain.tools import tool
from src.Gmail_MCP.gmail_mcp_client import GmailMCPClient
import json

# Initialize MCP client once (lazy connection - connects on first tool use)
client = GmailMCPClient()

def ensure_connected():
    """Ensure client is connected before tool use"""
    if client.session is None:
        client.connect()


# ==========================================================
# EMAIL MANAGEMENT TOOLS
# ==========================================================

@tool("gmail_send_email")
def gmail_send_email(to: str, subject: str, body: str, cc: str = None, bcc: str = None):
    """
    Send an email via Gmail.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body content
        cc: Optional CC recipients (comma-separated)
        bcc: Optional BCC recipients (comma-separated)
    """
    ensure_connected()
    # Gmail MCP server expects: recipient_id, subject, message
    args = {"recipient_id": to, "subject": subject, "message": body}
    if cc:
        args["cc"] = cc
    if bcc:
        args["bcc"] = bcc
    
    return client.call_tool("send-email", args)


@tool("gmail_search_emails")
def gmail_search_emails(query: str, max_results: int = 10):
    """
    Search emails using Gmail query syntax.
    
    Args:
        query: Gmail search query (e.g., "is:unread", "from:user@example.com")
        max_results: Maximum number of results to return (default: 10)
    
    Examples:
        - "is:unread" - Find unread emails
        - "from:boss@company.com" - Emails from specific sender
        - "subject:meeting" - Emails with "meeting" in subject
        - "has:attachment" - Emails with attachments
    """
    ensure_connected()
    return client.call_tool("search-emails", {
        "query": query,
        "max_results": max_results
    })


@tool("gmail_read_email")
def gmail_read_email(email_id: str):
    """
    Read the content of a specific email.
    
    Args:
        email_id: The ID of the email to read
    """
    ensure_connected()
    return client.call_tool("read-email", {"email_id": email_id})


@tool("gmail_mark_as_read")
def gmail_mark_as_read(email_id: str):
    """
    Mark an email as read.
    
    Args:
        email_id: The ID of the email to mark as read
    """
    ensure_connected()
    return client.call_tool("mark-email-as-read", {"email_id": email_id})


@tool("gmail_mark_as_unread")
def gmail_mark_as_unread(email_id: str):
    """
    Mark an email as unread.
    
    Args:
        email_id: The ID of the email to mark as unread
    """
    ensure_connected()
    return client.call_tool("mark-email-as-unread", {"email_id": email_id})


@tool("gmail_trash_email")
def gmail_trash_email(email_id: str):
    """
    Move an email to trash.
    
    Args:
        email_id: The ID of the email to trash
    """
    ensure_connected()
    return client.call_tool("trash-email", {"email_id": email_id})


# ==========================================================
# DRAFT MANAGEMENT TOOLS
# ==========================================================

@tool("gmail_create_draft")
def gmail_create_draft(to: str, subject: str, body: str):
    """
    Create a draft email.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body content
    """
    ensure_connected()
    return client.call_tool("create-draft", {
        "to": to,
        "subject": subject,
        "body": body
    })


@tool("gmail_list_drafts")
def gmail_list_drafts(max_results: int = 10):
    """
    List all draft emails.
    
    Args:
        max_results: Maximum number of drafts to return (default: 10)
    """
    ensure_connected()
    return client.call_tool("list-drafts", {"max_results": max_results})


# ==========================================================
# LABEL MANAGEMENT TOOLS
# ==========================================================

@tool("gmail_list_labels")
def gmail_list_labels():
    """List all Gmail labels."""
    ensure_connected()
    return client.call_tool("list-labels", {})


@tool("gmail_create_label")
def gmail_create_label(name: str):
    """
    Create a new Gmail label.
    
    Args:
        name: Name of the label to create
    """
    ensure_connected()
    return client.call_tool("create-label", {"name": name})


@tool("gmail_apply_label")
def gmail_apply_label(email_id: str, label_name: str):
    """
    Apply a label to an email.
    
    Args:
        email_id: The ID of the email
        label_name: Name of the label to apply
    """
    ensure_connected()
    return client.call_tool("apply-label", {
        "email_id": email_id,
        "label_name": label_name
    })


@tool("gmail_remove_label")
def gmail_remove_label(email_id: str, label_name: str):
    """
    Remove a label from an email.
    
    Args:
        email_id: The ID of the email
        label_name: Name of the label to remove
    """
    ensure_connected()
    return client.call_tool("remove-label", {
        "email_id": email_id,
        "label_name": label_name
    })


# ==========================================================
# ARCHIVE MANAGEMENT TOOLS
# ==========================================================

@tool("gmail_archive_email")
def gmail_archive_email(email_id: str):
    """
    Archive an email (remove from inbox without deleting).
    
    Args:
        email_id: The ID of the email to archive
    """
    ensure_connected()
    return client.call_tool("archive-email", {"email_id": email_id})


@tool("gmail_list_archived_emails")
def gmail_list_archived_emails(max_results: int = 10):
    """
    List archived emails.
    
    Args:
        max_results: Maximum number of emails to return (default: 10)
    """
    ensure_connected()
    return client.call_tool("list-archived", {"max_results": max_results})


# ==========================================================
# ALL TOOLS LIST (for easy import)
# ==========================================================

ALL_GMAIL_TOOLS = [
    # Email management
    gmail_send_email,
    gmail_search_emails,
    gmail_read_email,
    gmail_mark_as_read,
    gmail_mark_as_unread,
    gmail_trash_email,
    
    # Draft management
    gmail_create_draft,
    gmail_list_drafts,
    
    # Label management
    gmail_list_labels,
    gmail_create_label,
    gmail_apply_label,
    gmail_remove_label,
    
    # Archive management
    gmail_archive_email,
    gmail_list_archived_emails,
]
