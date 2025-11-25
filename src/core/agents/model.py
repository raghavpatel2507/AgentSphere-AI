from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os

load_dotenv() 

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Model Configuration (easily changeable)
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")  # Change in .env
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "100000"))  # Token limit for trimming

# Initialize model based on configuration
# Uncomment the one you want to use:

# model = ChatOpenAI(
#     model_name=MODEL_NAME,
#     openai_api_key=OPENAI_API_KEY,
#     temperature=0.7,
#     max_retries=3,  # Auto-retry on API errors
# )

# model = ChatGroq(
#     api_key=GROQ_API_KEY,
#     # model="llama-3.3-70b-versatile",
#     model="openai/gpt-oss-120b",
#     temperature=0.7,
#     max_retries=3,
# )

model = ChatGoogleGenerativeAI(
    google_api_key=GOOGLE_API_KEY,
    model="gemini-2.5-flash",
    temperature=0.7,
    max_retries=3,
)