import uvicorn
from config.settings import env
from app.kernel import app
from config.middleware import setup_middleware
from config.routes import setup_routes


setup_middleware(app)
setup_routes(app, env)

if __name__ == "__main__":
    uvicorn.run("main:app", host="localhost", port=8001)
