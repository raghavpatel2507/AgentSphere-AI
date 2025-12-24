import uvicorn
import os
import dotenv

dotenv.load_dotenv(override=True)

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    print(f"🚀 Starting AgentSphere-AI Server on http://{host}:{port}")
    uvicorn.run("src.api.main:app", host=host, port=port, reload=True)
