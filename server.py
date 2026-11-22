"""Start the LumenCut API and static dashboard."""

import os

from dotenv import load_dotenv

load_dotenv()

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "3000")),
        reload=False,
    )
