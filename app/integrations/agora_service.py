import time
import random
from agora_token_builder import RtcTokenBuilder

from app.core.config import (
    AGORA_APP_ID,
    AGORA_APP_CERTIFICATE,
)
import random


class AgoraService:
    """
    Handles Agora RTC Video Meetings
    """

    TOKEN_EXPIRATION_SECONDS = 3600

    def __init__(self):
        self.app_id = AGORA_APP_ID
        self.app_certificate = AGORA_APP_CERTIFICATE

    # ------------------------------------------
    # Generate unique meeting channel
    # ------------------------------------------

    @staticmethod
    def generate_channel_name(appointment_id: int) -> str:
        """
        Example:
        appointment_25_1721465200
        """

        timestamp = int(time.time())

        return f"appointment_{appointment_id}_{timestamp}"

    # ------------------------------------------
    # Generate User UID
    # ------------------------------------------

    @staticmethod
    def generate_uid() -> int:
        """
        Agora requires numeric UID.
        """

        return random.randint(100000, 999999)

    # ------------------------------------------
    # Generate Agora Token
    # ------------------------------------------

    @staticmethod
    def generate_token(
     channel_name: str,
     uid: int,
     role: int = 1,
    ):
       """
       Generate an Agora RTC token.

        Roles:
         1 = Publisher
         2 = Subscriber
       """

       current_time = int(time.time())

       privilege_expired_ts = (
         current_time
         + AgoraService.TOKEN_EXPIRATION_SECONDS
        )

       token = RtcTokenBuilder.buildTokenWithUid(
        AGORA_APP_ID,
        AGORA_APP_CERTIFICATE,
        channel_name,
        uid,
        role,
        privilege_expired_ts,
    )

       return token
  
    # ------------------------------------------
    # Create Video Meeting
    # ------------------------------------------

    @staticmethod
    def create_video_meeting(appointment_id: int):

        channel = AgoraService.generate_channel_name(
            appointment_id
        )

        uid = AgoraService.generate_uid()

        token = AgoraService.generate_token(
            channel,
            uid,
        )

        return {
            "app_id": AGORA_APP_ID,
            "channel": channel,
            "uid": uid,
            "token": token,
            "expires_in": AgoraService.TOKEN_EXPIRATION_SECONDS,
        }