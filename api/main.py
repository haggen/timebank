from os import environ
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello, world"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(environ.get("PORT", 5000)),
        reload=environ.get("PYTHON_ENV") == "development",
    )
