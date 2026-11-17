import os

from fastapi import APIRouter

router = APIRouter()



@router.get("/status")
def status():
    return {"status": "running"}


@router.get("/check-api")
def check_api():
    api_key = os.getenv("OPENAI_API_KEY")
    return {"has_api_key": bool(api_key)}
