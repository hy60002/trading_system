#!/usr/bin/env python3
"""
Simple test to see if FastAPI server can actually start
"""
import uvicorn
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Test server is working"}

@app.get("/test")
def test():
    return {"status": "OK", "server": "running"}

if __name__ == "__main__":
    print("Starting simple test server...")
    uvicorn.run(app, host="127.0.0.1", port=8000)