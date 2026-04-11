import uuid
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.models.survey import Question, QuestionConfig, QuestionOption, Survey
from app.models.user import User
from app.schemas.survey import (
    PublicQuestionConfigResponse,
    PublicQuestionOptionResponse,
    PublicQuestionResponse,
    QuestionTypeEnum,
    SurveyCreateRequest,
    SurveyShowByTokenResponse,
)


def _validate_question_payload(question_index: int, question_payload):
    if question_payload.type == QuestionTypeEnum.MCQ:
        if not question_payload.options:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Question at index {question_index} with type 'mcq' must include options",
            )
        if question_payload.config is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Question at index {question_index} with type 'mcq' must not include config",
            )

    if question_payload.type == QuestionTypeEnum.ARROW:
        if question_payload.config is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Question at index {question_index} with type 'arrow' must include config",
            )
        if question_payload.options:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Question at index {question_index} with type 'arrow' must not include options",
            )


def _validate_survey_time_range(start_time, end_time):
    if start_time and end_time and end_time <= start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_time must be greater than start_time",
        )


def _generate_unique_survey_token(db: Session, max_attempts: int = 5):
    for _ in range(max_attempts):
        token = uuid.uuid4().hex
        token_exists = db.query(Survey.id).filter(Survey.token == token).first()
        if token_exists is None:
            return token

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Could not generate a unique survey token",
    )


def _upsert_survey(db: Session, payload: SurveyCreateRequest, current_user: User):
    if payload.id is None:
        _validate_survey_time_range(payload.start_time, payload.end_time)
        survey = Survey(
            name=payload.name,
            token=_generate_unique_survey_token(db=db),
            created_by=current_user.id,
            start_time=payload.start_time,
            end_time=payload.end_time,
            status=(payload.status.value if payload.status is not None else "pending"),
        )
        db.add(survey)
        db.flush()
        return survey

    survey = db.query(Survey).filter(Survey.id == payload.id).first()
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found",
        )

    if survey.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this survey",
        )

    start_time = payload.start_time if payload.start_time is not None else survey.start_time
    end_time = payload.end_time if payload.end_time is not None else survey.end_time
    _validate_survey_time_range(start_time, end_time)

    survey.name = payload.name
    survey.start_time = start_time
    survey.end_time = end_time
    if payload.status is not None:
        survey.status = payload.status.value
    return survey


def _upsert_question(db: Session, survey: Survey, question_payload):
    if question_payload.id is None:
        question = Question(
            survey_id=survey.id,
            type=question_payload.type.value,
            title=question_payload.title,
            question_image=question_payload.question_image,
            is_visible=question_payload.is_visible,
            is_required=question_payload.is_required,
            allow_multiple_selection=question_payload.allow_multiple_selection,
            order_index=question_payload.order_index,
        )
        db.add(question)
        db.flush()
        return question

    question = (
        db.query(Question)
        .filter(Question.id == question_payload.id, Question.survey_id == survey.id)
        .first()
    )
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question with id {question_payload.id} not found in this survey",
        )

    question.type = question_payload.type.value
    question.title = question_payload.title
    question.question_image = question_payload.question_image
    question.is_visible = question_payload.is_visible
    question.is_required = question_payload.is_required
    question.allow_multiple_selection = question_payload.allow_multiple_selection
    question.order_index = question_payload.order_index
    return question


def _upsert_question_options(db: Session, question: Question, question_payload, sync_missing: bool = False):
    kept_option_ids = set()

    for option_payload in question_payload.options or []:
        if option_payload.id is None:
            option = QuestionOption(
                question_id=question.id,
                image_url=option_payload.image_url,
                order_index=option_payload.order_index,
            )
            db.add(option)
            db.flush()
            kept_option_ids.add(option.id)
            continue

        option = (
            db.query(QuestionOption)
            .filter(
                QuestionOption.id == option_payload.id,
                QuestionOption.question_id == question.id,
            )
            .first()
        )
        if not option:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Option with id {option_payload.id} not found in this question",
            )

        option.image_url = option_payload.image_url
        option.order_index = option_payload.order_index
        kept_option_ids.add(option.id)

    if sync_missing:
        existing_options = db.query(QuestionOption).filter(QuestionOption.question_id == question.id).all()
        for existing_option in existing_options:
            if existing_option.id not in kept_option_ids:
                db.delete(existing_option)


def _delete_question_options(db: Session, question_id):
    options = db.query(QuestionOption).filter(QuestionOption.question_id == question_id).all()
    for option in options:
        db.delete(option)


def _delete_question_config(db: Session, question_id):
    config = db.query(QuestionConfig).filter(QuestionConfig.question_id == question_id).first()
    if config is not None:
        db.delete(config)


def _upsert_question_config(db: Session, question: Question, question_payload):
    config_payload = question_payload.config
    if config_payload is None:
        return

    if config_payload.id is not None:
        config = db.query(QuestionConfig).filter(QuestionConfig.question_id == config_payload.id).first()
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Config with id {config_payload.id} not found",
            )
        if config.question_id != question.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Config with id {config_payload.id} does not belong to question {question.id}",
            )
    else:
        config = db.query(QuestionConfig).filter(QuestionConfig.question_id == question.id).first()

    if config is None:
        db.add(
            QuestionConfig(
                question_id=question.id,
                correct_angle=config_payload.correct_angle,
                tolerance=config_payload.tolerance,
                standing_position=config_payload.standing_position,
                looking_direction=config_payload.looking_direction,
            )
        )
        return

    config.correct_angle = config_payload.correct_angle
    config.tolerance = config_payload.tolerance
    config.standing_position = config_payload.standing_position
    config.looking_direction = config_payload.looking_direction


def _sync_deleted_questions(db: Session, survey_id, kept_question_ids):
    existing_questions = db.query(Question).filter(Question.survey_id == survey_id).all()
    for existing_question in existing_questions:
        if existing_question.id not in kept_question_ids:
            db.delete(existing_question)


def create_survey(db: Session, payload: SurveyCreateRequest, current_user: User):
    try:
        survey = _upsert_survey(db=db, payload=payload, current_user=current_user)
        is_update_request = payload.id is not None
        kept_question_ids = set()

        for idx, question_payload in enumerate(payload.questions):
            _validate_question_payload(question_index=idx, question_payload=question_payload)
            question = _upsert_question(db=db, survey=survey, question_payload=question_payload)
            kept_question_ids.add(question.id)

            if question_payload.type == QuestionTypeEnum.MCQ:
                _upsert_question_options(
                    db=db,
                    question=question,
                    question_payload=question_payload,
                    sync_missing=is_update_request,
                )
                _delete_question_config(db=db, question_id=question.id)

            if question_payload.type == QuestionTypeEnum.ARROW:
                _upsert_question_config(db=db, question=question, question_payload=question_payload)
                _delete_question_options(db=db, question_id=question.id)

        if is_update_request:
            _sync_deleted_questions(db=db, survey_id=survey.id, kept_question_ids=kept_question_ids)

        db.commit()
        upserted_survey = (
            db.query(Survey)
            .options(
                selectinload(Survey.questions).selectinload(Question.options),
                selectinload(Survey.questions).selectinload(Question.config),
            )
            .filter(Survey.id == survey.id)
            .first()
        )
        return upserted_survey
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def get_surveys_by_current_user(db: Session, current_user: User):
    return (
        db.query(Survey)
        .options(
            selectinload(Survey.questions).selectinload(Question.options),
            selectinload(Survey.questions).selectinload(Question.config),
        )
        .filter(Survey.created_by == current_user.id)
        .order_by(Survey.created_at.desc())
        .all()
    )


def get_survey_detail_by_id(db: Session, survey_id: UUID, current_user: User):
    survey = (
        db.query(Survey)
        .options(
            selectinload(Survey.questions).selectinload(Question.options),
            selectinload(Survey.questions).selectinload(Question.config),
        )
        .filter(Survey.id == survey_id, Survey.created_by == current_user.id)
        .first()
    )

    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found",
        )

    return survey


def get_survey_by_token_show(db: Session, token: str):
    survey = (
        db.query(Survey)
        .options(
            selectinload(Survey.questions).selectinload(Question.options),
            selectinload(Survey.questions).selectinload(Question.config),
        )
        .filter(Survey.token == token, Survey.status == "active")
        .first()
    )

    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active survey not found",
        )

    visible_questions = sorted(
        [question for question in survey.questions if question.is_visible],
        key=lambda question: question.order_index,
    )

    public_questions = []
    for question in visible_questions:
        public_options = [
            PublicQuestionOptionResponse(
                id=option.id,
                question_id=option.question_id,
                image_url=option.image_url,
                order_index=option.order_index,
            )
            for option in sorted(question.options, key=lambda item: item.order_index)
        ]

        public_config = None
        if question.config is not None:
            # Intentionally hide correct_angle in public endpoint.
            public_config = PublicQuestionConfigResponse(
                question_id=question.config.question_id,
                tolerance=question.config.tolerance,
                standing_position=question.config.standing_position,
                looking_direction=question.config.looking_direction,
            )

        public_questions.append(
            PublicQuestionResponse(
                id=question.id,
                survey_id=question.survey_id,
                type=question.type,
                title=question.title,
                question_image=question.question_image,
                is_visible=question.is_visible,
                is_required=question.is_required,
                allow_multiple_selection=question.allow_multiple_selection,
                order_index=question.order_index,
                options=public_options,
                config=public_config,
            )
        )

    return SurveyShowByTokenResponse(
        id=survey.id,
        name=survey.name,
        token=survey.token,
        start_time=survey.start_time,
        end_time=survey.end_time,
        status=survey.status,
        questions=public_questions,
    )


def generate_survey_token(db: Session, survey_id: UUID, current_user: User):
    survey = (
        db.query(Survey)
        .filter(Survey.id == survey_id, Survey.created_by == current_user.id)
        .first()
    )

    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found",
        )

    survey.token = _generate_unique_survey_token(db=db)

    db.commit()
    db.refresh(survey)

    return survey


def delete_survey(db: Session, survey_id: UUID, current_user: User):
    survey = (
        db.query(Survey)
        .filter(Survey.id == survey_id, Survey.created_by == current_user.id)
        .first()
    )

    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found",
        )

    if survey.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending surveys can be deleted",
        )

    try:
        db.delete(survey)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    return {
        "id": survey_id,
        "detail": "Survey deleted successfully",
    }