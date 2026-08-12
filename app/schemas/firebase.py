from pydantic import BaseModel


class FCMTokenRequest(BaseModel):
    fcm_token: str
    # True only right after a fresh sign-in. The frontend also re-sends the
    # token on every normal page load/refresh (so the scheduler always has a
    # current token to notify), and those calls must NOT re-trigger the
    # "you've logged in" push — only an actual login should.
    notify_login: bool = False