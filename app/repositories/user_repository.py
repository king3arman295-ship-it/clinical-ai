from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):

    def __init__(self):
        super().__init__(User)

    # -----------------------------------
    # Get User By ID
    # -----------------------------------
    def get_by_id(
        self,
        db: Session,
        user_id: int,
    ):
        return (
            db.query(User)
            .filter(User.id == user_id)
            .first()
        )

    # -----------------------------------
    # Get User By Username
    # -----------------------------------
    def get_by_username(
        self,
        db: Session,
        username: str,
    ):
        return (
            db.query(User)
            .filter(User.username == username)
            .first()
        )

    # -----------------------------------
    # Get User By Email
    # -----------------------------------
    def get_by_email(
        self,
        db: Session,
        email: str,
    ):
        return (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

    # -----------------------------------
    # Check Username Exists
    # -----------------------------------
    def username_exists(
        self,
        db: Session,
        username: str,
    ) -> bool:
        return (
            db.query(User)
            .filter(User.username == username)
            .first()
            is not None
        )

    # -----------------------------------
    # Check Email Exists
    # -----------------------------------
    def email_exists(
        self,
        db: Session,
        email: str,
    ) -> bool:
        return (
            db.query(User)
            .filter(User.email == email)
            .first()
            is not None
        )
    # -----------------------------------
    # Get Users By Role (e.g. broadcasting to all admission_head /
    # pharmacist accounts for queue notifications)
    # -----------------------------------
    def get_by_role(
        self,
        db: Session,
        role: str,
    ):
        return (
            db.query(User)
            .filter(User.role == role)
            .all()
        )

    # -----------------------------------
# Update FCM Token
# -----------------------------------
    def update_fcm_token(
    self,
    db: Session,
    user: User,
    token: str,
   ):
       user.fcm_token = token
       db.add(user)
       return user