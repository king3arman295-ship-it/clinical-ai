from jose import JWTError, jwt
from fastapi import Depends

from app.auth.jwt import SECRET_KEY, ALGORITHM
from app.exceptions.exceptions import UnauthorizedException

from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)

# Public endpoints, such as the website chat, can use this dependency without
# rejecting visitors who have not signed in. A supplied token is still decoded
# and validated before its identity is used.
optional_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    auto_error=False,
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
):
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        username = payload.get("sub")

        role = payload.get("role")
        doctor_id = payload.get("doctor_id")
        patient_id = payload.get("patient_id")

        if username is None:
            raise UnauthorizedException(
                "Invalid token."
            )

        return {
            "id": payload.get("id"),
            "username": username,
            "role": role,
            "doctor_id": doctor_id,
            "patient_id": patient_id,
        }

    except JWTError:
        raise UnauthorizedException(
            "Invalid or expired token."
        )


def get_optional_current_user(
    token: str | None = Depends(optional_oauth2_scheme),
):
    if token is None:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise UnauthorizedException("Invalid token.")

        return {
            "id": payload.get("id"),
            "username": username,
            "role": payload.get("role"),
            "doctor_id": payload.get("doctor_id"),
            "patient_id": payload.get("patient_id"),
        }
    except JWTError:
        raise UnauthorizedException("Invalid or expired token.")
