from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from controller import auth
from controller.ui import render_phone_ui

router = APIRouter()



@router.get("/", response_class=HTMLResponse)
def phone_ui(request: Request):
    name = "Local session" if auth.LOCAL_AUTH else auth.get_session_name(request)
    return render_phone_ui(name, auth.LOCAL_AUTH)
