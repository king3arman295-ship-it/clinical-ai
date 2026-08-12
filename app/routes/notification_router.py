from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.auth.dependencies import get_current_user

from app.repositories.user_repository import UserRepository
from app.services.firebase_service import send_notification

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)

user_repository = UserRepository()


@router.post("/test")
def test_notification(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    user = user_repository.get_by_username(
        db,
        current_user["username"],
    )

    if not user.fcm_token:
        return {
            "message": "User has no FCM token."
        }

    message_id = send_notification(
        token=user.fcm_token,
        title="Clinic AI",
        body="🎉 Firebase notifications are working!",
    )

    return {
        "message": "Notification sent successfully.",
        "firebase_message_id": message_id,
    }