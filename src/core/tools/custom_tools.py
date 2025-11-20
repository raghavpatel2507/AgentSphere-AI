from langchain_community.tools import DuckDuckGoSearchRun
from langchain_experimental.utilities import PythonREPL
from langchain_community.tools import tool


#------------------------------This tool used for the web search using DuckDuckGo------------------------------#
def search_duckduckgo(query: str):
    """Searches DuckDuckGo using LangChain's DuckDuckGoSearchRun tool.it is search the any information on the internet."""
    search = DuckDuckGoSearchRun()
    return search.invoke(query)


#------------------------------This tool used for the mathematical calculations------------------------------#
def calculate_expression(expression: str) -> str:
    """Calculate a mathematical expression.and perform the arithmetical operations."""
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {str(e)}"


#------------------------------------Used for the python code ------------------------------------------------#

python_repl = PythonREPL()

@tool("python_executor")
def python_executor(code: str) -> str:
    """Execute Python code safely in REPL."""
    try:
        return python_repl.run(code)
    except Exception as e:
        return f"Error: {str(e)}"