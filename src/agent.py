from langgraph_supervisor import create_supervisor
from langchain.agents import create_agent
from src.model import model
from src.tool import *
from src.system_prompt import *
from src.Github_MCP.github_tools import *
from src.Figma_MCP.figma_tools import *
from src.Gmail_MCP.gmail_tools import *
from src.Zoho_MCP.zoho_tools import *

#------------------------------This agent used for The mathmatical calculation------------------------------#
math_agent = create_agent(
    model=model,
    tools=[calculate_expression],
    name="math_expert",
    system_prompt=system_prompt_mathagent
)

#------------------------------This agent used for The web search------------------------------#
websearch_agent = create_agent(
    model=model,
    tools=[search_duckduckgo],
    name="websearch_expert",
    system_prompt=system_prompt_websearch
)

#------------------------------This agent used for The python code execution------------------------------#
python_agent = create_agent(
    model=model,
    tools=[python_executor],
    name="python_expert",
    system_prompt=system_prompt_python
)

#------------------------------This agent used for The GitHub MCP operations------------------------------#
github_agent = create_agent(
    model=model,
    tools=[
        github_list_repos,
        github_read_file,
        github_write_file,
        github_delete_file,
        github_create_repo,
        github_create_branch,
        github_list_branches,
        github_list_tags,
        github_list_commits,
        github_push_files,
        github_fork_repo,
        github_search_code,
        github_get_commit,
        github_list_releases,
        github_get_latest_release,
        github_get_release_by_tag,
        github_get_tag,
    ],
    name="github_expert",
    system_prompt=system_prompt_github_mcp
)

#------------------------------This agent used for Gmail MCP operations------------------------------#
gmail_agent = create_agent(
    model=model,
    tools=[
        gmail_send_email,
        gmail_search_emails,
        gmail_read_email,
        gmail_mark_as_read,
        gmail_mark_as_unread,
        gmail_trash_email,
        gmail_create_draft,
        gmail_list_drafts,
        gmail_list_labels,
        gmail_create_label,
        gmail_apply_label,
        gmail_remove_label,
        gmail_archive_email,
        gmail_list_archived_emails,
    ],
    name="gmail_expert",
    system_prompt=system_prompt_gmail_mcp
)


# figma_agent = create_agent(
#     model=model,
#     tools=[
#         figma_get_design_context,
#         figma_get_variable_defs,
#         figma_get_code_connect_map
#     ],
#     name="figma_expert",
#     system_prompt=system_prompt_figma_mcp
# )#------------------------------This agent used for Zoho Books MCP operations------------------------------#
zoho_agent = create_agent(
    model=model,
    tools=[
        # Invoice management
        zoho_create_invoice,
        zoho_list_invoices,
        zoho_get_invoice,
        # zoho_email_invoice,
        zoho_record_payment,
        zoho_send_payment_reminder,
        zoho_void_invoice,
        zoho_mark_invoice_as_sent,
        
        # Contact management
        zoho_create_customer,
        zoho_create_vendor,
        zoho_list_contacts,
        zoho_get_contact,
        zoho_update_contact,
        zoho_delete_contact,
        zoho_email_statement,
        
        # Expense management
        zoho_create_expense,
        zoho_update_expense,
        zoho_list_expenses,
        zoho_get_expense,
        zoho_categorize_expense,
        
        # Item management
        zoho_create_item,
        zoho_update_item,
        zoho_list_items,
        zoho_get_item,
        
        # Sales order management
        zoho_create_sales_order,
        zoho_update_sales_order,
        zoho_convert_to_invoice,
        zoho_list_sales_orders,
        zoho_get_sales_order,
    ],
    name="zoho_expert",
    system_prompt=system_prompt_zoho_mcp
)
