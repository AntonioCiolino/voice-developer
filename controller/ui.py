import pathlib

_TEMPLATE = pathlib.Path(__file__).with_name("templates") / "phone.html"

# The phone UI is an HTML template with {{USER_NAME}} and {{LOGOUT_VISIBILITY}} placeholders.
PHONE_UI = _TEMPLATE.read_bytes().decode("utf-8")


def render_phone_ui(name: str, local_auth: bool) -> str:
    return PHONE_UI.replace("{{USER_NAME}}", name).replace(
        "{{LOGOUT_VISIBILITY}}", "hidden" if local_auth else ""
    )
