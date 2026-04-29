from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.schemas.participant import (
    AttemptDoneResponse,
    ParticipantAnswerSubmitRequest,
    ParticipantAnswerSubmitResponse,
    ParticipantSubmitRequest,
    ParticipantSubmitStartResponse,
)
from app.services.participant import done_attempt, submit_answer_one, submit_participant

router = APIRouter(
    prefix="/participants",
    tags=["Participants"]
)

@router.post("/submit", response_model=ParticipantSubmitStartResponse, status_code=status.HTTP_200_OK)
def submit(payload: ParticipantSubmitRequest, db: Session = Depends(get_db)):
    participant = submit_participant(db, payload)
    return participant


@router.post("/attempts/{attempt_id}/answers/one", response_model=ParticipantAnswerSubmitResponse, status_code=status.HTTP_200_OK)
def submit_one_answer(attempt_id: UUID, payload: ParticipantAnswerSubmitRequest, db: Session = Depends(get_db)):
    result = submit_answer_one(db=db, attempt_id=attempt_id, payload=payload)
    return result


@router.post("/attempts/{attempt_id}/done", response_model=AttemptDoneResponse, status_code=status.HTTP_200_OK)
def done(attempt_id: UUID, db: Session = Depends(get_db)):
    result = done_attempt(db=db, attempt_id=attempt_id)
    return result