from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os
load_dotenv() 
GROQ_API_KEY=os.getenv("GROQ_API_KEY")
openai_api_key=os.getenv("OPENAI_API_KEY")

model = ChatGroq(api_key=GROQ_API_KEY, model="openai/gpt-oss-120b")

#model=  ChatOpenAI(model_name="gpt-4.1-mini", openai_api_key=openai_api_key)