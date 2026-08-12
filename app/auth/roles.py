from fastapi import Depends

from app.auth.dependencies import get_current_user
from app.exceptions.exceptions import UnauthorizedException


def require_roles(*allowed_roles):
    def role_checker(current_user=Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise UnauthorizedException(
                "You are not authorized to perform this action."
            )

        return current_user

    return role_checker