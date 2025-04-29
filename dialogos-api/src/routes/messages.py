# src/routes/messages.py
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import json
import os

router = APIRouter()

@router.get("/api/messages/branched")
def get_branched_messages():
    try:
        with open("data/messages.json", "r") as f:
            messages = json.load(f)
        return {"data": messages}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
