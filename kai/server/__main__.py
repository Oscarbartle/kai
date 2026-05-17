"""Entry point: python -m kai.server"""
import uvicorn
from kai.server import config

if __name__ == "__main__":
    uvicorn.run(
        "kai.server.app:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
    )
