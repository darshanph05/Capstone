from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.analytics import QuestionAnalyticsResponse
from app.models.user import User
from app.schemas.survey import (
    GenerateTokenResponse,
    SurveyCreateRequest,
    SurveyCreateResponse,
    SurveyShowByTokenResponse,
    SurveyDeleteResponse,
)


from app.services.auth import get_current_user
from app.services.survey import (
    copy_survey,
    create_survey,
    delete_survey,
    export_question_responses_csv,
    export_survey_responses_csv,
    generate_survey_token,
    get_question_analytics_by_id,
    get_survey_by_token_show,
    get_survey_detail_by_id,
    get_surveys_by_current_user,
)

router = APIRouter(
    prefix="/surveys",
    tags=["Surveys"],
)


@router.post("", response_model=SurveyCreateResponse, status_code=status.HTTP_201_CREATED)
def create(payload: SurveyCreateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    survey = create_survey(db=db, payload=payload, current_user=current_user)
    return survey


@router.get("", response_model=List[SurveyCreateResponse])
def get_my_surveys(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    surveys = get_surveys_by_current_user(db=db, current_user=current_user)
    return surveys


@router.get("/{survey_id}", response_model=SurveyCreateResponse)
def get_survey_detail(survey_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    survey = get_survey_detail_by_id(db=db, survey_id=survey_id, current_user=current_user)
    return survey


@router.delete("/{survey_id}", response_model=SurveyDeleteResponse, status_code=status.HTTP_200_OK)
def delete(survey_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = delete_survey(db=db, survey_id=survey_id, current_user=current_user)
    return result


@router.get("/{survey_id}/questions/{question_id}/responses", response_model=QuestionAnalyticsResponse)
def get_question_responses(
    survey_id: UUID,
    question_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = get_question_analytics_by_id(
        db=db,
        survey_id=survey_id,
        question_id=question_id,
        current_user=current_user,
    )
    return result


@router.get("/{survey_id}/questions/{question_id}/responses/export", status_code=status.HTTP_200_OK)
def export_question_responses(
    survey_id: UUID,
    question_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    csv_content, filename = export_question_responses_csv(
        db=db,
        survey_id=survey_id,
        question_id=question_id,
        current_user=current_user,
    )

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/{survey_id}/responses/export", status_code=status.HTTP_200_OK)
def export_survey_responses(
    survey_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    csv_content, filename = export_survey_responses_csv(
        db=db,
        survey_id=survey_id,
        current_user=current_user,
    )

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )

#them cai nay nua a
@router.post("/{survey_id}/token", response_model=GenerateTokenResponse, status_code=status.HTTP_201_CREATED)
def generate_token(
    survey_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    survey = generate_survey_token(db=db, survey_id=survey_id, current_user=current_user)
    return survey


@router.get("/{token}/show", response_model=SurveyShowByTokenResponse)
def show_by_token(token: str, db: Session = Depends(get_db)):
    survey = get_survey_by_token_show(db=db, token=token)
    return survey


@router.post("/{survey_id}/copy", response_model=SurveyCreateResponse, status_code=status.HTTP_201_CREATED)
def copy(
    survey_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    survey = copy_survey(db=db, survey_id=survey_id, current_user=current_user)
    return survey

