from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.ai.ai_service import AIService
from app.auth.dependencies import get_current_user, get_optional_current_user


router = APIRouter(
    prefix="/ai",
    tags=["AI Receptionist"],
)


def get_ai_service():
    return AIService()


from fastapi import APIRouter, Depends, File, UploadFile, Form


@router.post("/upload")
def upload_patient_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    service: AIService = Depends(get_ai_service),
    current_user=Depends(get_current_user),
):
    """Upload a document from the patient portal without starting an AI chat flow."""
    if current_user.get("role") != "patient" or not current_user.get("patient_id"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Patient access required.")

    result = service.upload_patient_document(
        db, current_user["patient_id"], file,
    )
    return result.data

# -----------------------------------
# Public AI Chat
# -----------------------------------
@router.post("/chat")
def chat(
    session_id: str,
    message: str = "",
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    service: AIService = Depends(get_ai_service),
    current_user=Depends(get_optional_current_user),
):
    """
    Chat with the AI Receptionist.
    Supports optional file attachments (medical reports, PDFs, images).
    """

    result = service.chat(
        db=db,
        session_id=session_id,
        message=message,
        file=file,
        patient_id=(
            current_user.get("patient_id")
            if current_user and current_user.get("role") == "patient"
            else None
        ),
    )

    return result.data


# -----------------------------------
# Clear Conversation
# -----------------------------------
@router.delete("/conversation/{session_id}")
def clear_conversation(
    session_id: str,
    service: AIService = Depends(get_ai_service),
):
    """
    Clear conversation history.
    """

    result = service.clear_conversation(
        session_id=session_id,
    )

    return {
        "message": result.message,
    }
