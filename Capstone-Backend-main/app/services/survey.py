import uuid
import csv
import io
import copy
from collections import defaultdict
from datetime import date, datetime
from typing import Dict, List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, selectinload

from app.models.survey import Answer, Attempt, Question, QuestionConfig, QuestionOption, Survey
from app.models.user import User
from app.schemas.analytics import (
    QuestionAnalyticsMetaResponse,
    QuestionAnalyticsResponse,
    QuestionAnalyticsRowResponse,
)
from app.schemas.survey import (
    PublicQuestionConfigResponse,
    PublicQuestionOptionResponse,
    PublicQuestionResponse,
    QuestionTypeEnum,
    SurveyCreateRequest,
    SurveyShowByTokenResponse,
)
from app.utils.timezone import to_canberra_naive


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

    if question_payload.type == QuestionTypeEnum.TEXT_ENTRY:
        if question_payload.options:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Question at index {question_index} with type 'text_entry' must not include options",
            )
        if question_payload.config is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Question at index {question_index} with type 'text_entry' must not include config",
            )


def _validate_survey_time_range(start_time, end_time):
    if start_time and end_time and end_time <= start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_time must be greater than start_time",
        )


def _normalize_survey_datetime(value):
    return to_canberra_naive(value)


def _normalize_time_limit_seconds(value, field_name: str):
    if value is None:
        return None
    if value < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be greater than or equal to 0",
        )
    return int(value)


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
    arrow_limit = _normalize_time_limit_seconds(payload.arrow_time_limit_sec, "arrow_time_limit_sec")
    mcq_limit = _normalize_time_limit_seconds(payload.mcq_time_limit_sec, "mcq_time_limit_sec")
    text_entry_limit = _normalize_time_limit_seconds(payload.text_entry_time_limit_sec, "text_entry_time_limit_sec")
    normalized_start_time = _normalize_survey_datetime(payload.start_time)
    normalized_end_time = _normalize_survey_datetime(payload.end_time)

    if payload.id is None:
        _validate_survey_time_range(normalized_start_time, normalized_end_time)
        survey = Survey(
            name=payload.name,
            token=_generate_unique_survey_token(db=db),
            created_by=current_user.id,
            start_time=normalized_start_time,
            end_time=normalized_end_time,
            status=(payload.status.value if payload.status is not None else "pending"),
            arrow_time_limit_sec=arrow_limit,
            mcq_time_limit_sec=mcq_limit,
            text_entry_time_limit_sec=text_entry_limit,
            participant_form_config=payload.participant_form_config,
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

    start_time = normalized_start_time if payload.start_time is not None else survey.start_time
    end_time = normalized_end_time if payload.end_time is not None else survey.end_time
    _validate_survey_time_range(start_time, end_time)

    survey.name = payload.name
    survey.start_time = start_time
    survey.end_time = end_time
    survey.arrow_time_limit_sec = arrow_limit
    survey.mcq_time_limit_sec = mcq_limit
    survey.text_entry_time_limit_sec = text_entry_limit
    survey.participant_form_config = payload.participant_form_config
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

            if question_payload.type == QuestionTypeEnum.TEXT_ENTRY:
                _delete_question_config(db=db, question_id=question.id)
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


def _is_non_empty_answer(answer: Answer) -> bool:
    if answer.selected_option_id is not None:
        return True
    if answer.user_angle is not None:
        return True
    return isinstance(answer.text_answer, str) and answer.text_answer.strip() != ""


def _unique_preserve_order(values: List):
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _format_decimal(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _format_mcq_option_label(answer: Answer) -> str:
    if answer.selected_option is not None and answer.selected_option.order_index is not None:
        return f"Option {int(answer.selected_option.order_index)}"
    if answer.selected_option_id is not None:
        return "Option (deleted)"
    return ""


def _format_answer_summary(question_type: str, answers: List[Answer]) -> str:
    if not answers:
        return "(no answer)"

    if question_type == "mcq":
        option_labels = []
        for answer in answers:
            if answer.selected_option_id is None:
                continue
            label = _format_mcq_option_label(answer)
            if label:
                option_labels.append(label)

        option_labels = _unique_preserve_order(option_labels)
        return ", ".join(option_labels) if option_labels else "(no answer)"

    if question_type == "arrow":
        parts = []
        for answer in answers:
            if answer.user_angle is None:
                continue
            angle_text = f"{_format_decimal(float(answer.user_angle))}deg"
            if answer.angle_deviation is not None:
                angle_text = f"{angle_text} (dev {_format_decimal(float(answer.angle_deviation))}deg)"
            parts.append(angle_text)
        if not parts:
            return "(no answer)"
        return ", ".join(parts)

    if question_type == "text_entry":
        texts = []
        for answer in answers:
            if isinstance(answer.text_answer, str):
                cleaned = answer.text_answer.strip()
                if cleaned:
                    texts.append(cleaned)
        return "; ".join(texts) if texts else "(no answer)"

    return "(no answer)"


def _question_block_name(question_type: str) -> str:
    if question_type == "mcq":
        return "MCQ"
    if question_type == "arrow":
        return "Arrow"
    if question_type == "text_entry":
        return "Text Entry"
    return question_type or ""


def _question_block_duration_seconds(survey: Survey, question_type: str):
    if question_type == "mcq":
        return survey.mcq_time_limit_sec
    if question_type == "arrow":
        return survey.arrow_time_limit_sec
    if question_type == "text_entry":
        return survey.text_entry_time_limit_sec
    return None


def _to_csv_value(value):
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def export_question_responses_csv(db: Session, survey_id: UUID, question_id: UUID, current_user: User):
    analytics = get_question_analytics_by_id(
        db=db,
        survey_id=survey_id,
        question_id=question_id,
        current_user=current_user,
    )

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

    question = (
        db.query(Question)
        .options(selectinload(Question.config))
        .filter(Question.id == question_id, Question.survey_id == survey_id)
        .first()
    )
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found in this survey",
        )

    attempt_ids = [row.attempt_id for row in analytics.rows]

    completion_percentage_by_attempt = {}
    if attempt_ids:
        attempt_rows = (
            db.query(Attempt.id, Attempt.completion_percentage)
            .filter(Attempt.id.in_(attempt_ids))
            .all()
        )
        completion_percentage_by_attempt = {
            attempt_id: completion_percentage
            for attempt_id, completion_percentage in attempt_rows
        }

    answers_by_attempt: Dict[UUID, List[Answer]] = defaultdict(list)
    if attempt_ids:
        answers = (
            db.query(Answer)
            .options(selectinload(Answer.selected_option))
            .filter(
                Answer.question_id == question_id,
                Answer.attempt_id.in_(attempt_ids),
            )
            .order_by(Answer.attempt_id.asc(), Answer.created_at.asc())
            .all()
        )
        for answer in answers:
            answers_by_attempt[answer.attempt_id].append(answer)

    headers = [
        "survey_id",
        "survey_name",
        "participant_id",
        "participant_code",
        "consent_answer",
        "participant_name",
        "school",
        "grade",
        "dob",
        "attempt_id",
        "attempt_start_time",
        "attempt_end_time",
        "attempt_status",
        "completion_percentage",
        "block_id",
        "block_name",
        "block_duration_seconds",
        "question_id",
        "question_order",
        "question_title",
        "question_type",
        "answer_summary",
        "answered_at",
        "response_time_sec",
        "answer_id",
        "selected_option",
        "text_answer",
        "user_angle",
        "correct_angle",
        "tolerance",
        "angle_variance",
    ]

    block_id = question.type or ""
    block_name = _question_block_name(question.type)
    block_duration_seconds = _question_block_duration_seconds(survey=survey, question_type=question.type)
    correct_angle = question.config.correct_angle if question.config else None
    tolerance = question.config.tolerance if question.config else None

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()

    for row in analytics.rows:
        answer_rows = answers_by_attempt.get(row.attempt_id, [])
        non_empty_answers = [answer for answer in answer_rows if _is_non_empty_answer(answer)]

        if not non_empty_answers:
            non_empty_answers = [None]

        for answer in non_empty_answers:
            selected_option = ""
            text_answer = ""
            user_angle = ""
            answer_id = ""
            angle_variance = ""

            if answer is not None:
                answer_id = _to_csv_value(answer.id)
                if answer.selected_option_id is not None:
                    selected_option = _format_mcq_option_label(answer)
                text_answer = _to_csv_value(answer.text_answer)
                user_angle = _to_csv_value(answer.user_angle)
                if answer.angle_deviation is not None:
                    angle_variance = _to_csv_value(answer.angle_deviation)
                elif answer.user_angle is not None and correct_angle is not None:
                    angle_variance = _to_csv_value(round(abs(float(answer.user_angle) - float(correct_angle)), 2))

            correct_angle_value = _to_csv_value(correct_angle)
            tolerance_value = _to_csv_value(tolerance)

            if question.type == "mcq":
                if not selected_option:
                    selected_option = "(no answer)"
                text_answer = "N/A"
                user_angle = "N/A"
                correct_angle_value = "N/A"
                tolerance_value = "N/A"
                angle_variance = "N/A"
            elif question.type == "text_entry":
                selected_option = "N/A"
                if not text_answer:
                    text_answer = "(no answer)"
                user_angle = "N/A"
                correct_angle_value = "N/A"
                tolerance_value = "N/A"
                angle_variance = "N/A"
            elif question.type == "arrow":
                selected_option = "N/A"
                text_answer = "N/A"
                if not user_angle:
                    user_angle = "(no answer)"
                if not angle_variance:
                    angle_variance = "(no answer)"

            writer.writerow(
                {
                    "survey_id": _to_csv_value(analytics.survey_id),
                    "survey_name": _to_csv_value(analytics.survey_name),
                    "participant_id": _to_csv_value(row.participant_id),
                    "participant_code": _to_csv_value(row.participant_code),
                    "consent_answer": _to_csv_value(row.participant_consent),
                    "participant_name": _to_csv_value(row.participant_name),
                    "school": _to_csv_value(row.participant_school),
                    "grade": _to_csv_value(row.participant_grade),
                    "dob": _to_csv_value(row.participant_dob),
                    "attempt_id": _to_csv_value(row.attempt_id),
                    "attempt_start_time": _to_csv_value(row.attempt_start_time),
                    "attempt_end_time": _to_csv_value(row.attempt_end_time),
                    "attempt_status": _to_csv_value(row.attempt_status),
                    "completion_percentage": _to_csv_value(
                        completion_percentage_by_attempt.get(row.attempt_id)
                    ),
                    "block_id": _to_csv_value(block_id),
                    "block_name": _to_csv_value(block_name),
                    "block_duration_seconds": _to_csv_value(block_duration_seconds),
                    "question_id": _to_csv_value(question.id),
                    "question_order": _to_csv_value(analytics.question.order_index),
                    "question_title": _to_csv_value(analytics.question.title),
                    "question_type": _to_csv_value(question.type),
                    "answer_summary": _to_csv_value(row.answer_summary),
                    "answered_at": _to_csv_value(row.answered_at),
                    "response_time_sec": _to_csv_value(row.response_time_sec),
                    "answer_id": answer_id,
                    "selected_option": selected_option,
                    "text_answer": text_answer,
                    "user_angle": user_angle,
                    "correct_angle": correct_angle_value,
                    "tolerance": tolerance_value,
                    "angle_variance": angle_variance,
                }
            )

    filename = f"survey_{survey.id}_question_{question.order_index}_responses.csv"
    return output.getvalue().encode("utf-8-sig"), filename


def export_survey_responses_csv(db: Session, survey_id: UUID, current_user: User):
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

    questions = (
        db.query(Question)
        .options(selectinload(Question.config))
        .filter(Question.survey_id == survey_id)
        .order_by(Question.order_index.asc(), Question.created_at.asc())
        .all()
    )

    attempts = (
        db.query(Attempt)
        .options(selectinload(Attempt.participant))
        .filter(Attempt.survey_id == survey_id)
        .order_by(Attempt.start_time.desc(), Attempt.id.desc())
        .all()
    )

    attempt_ids = [attempt.id for attempt in attempts]
    question_ids = [question.id for question in questions]

    answers_by_attempt_question: Dict[tuple, List[Answer]] = defaultdict(list)
    if attempt_ids and question_ids:
        answers = (
            db.query(Answer)
            .options(selectinload(Answer.selected_option))
            .filter(
                Answer.attempt_id.in_(attempt_ids),
                Answer.question_id.in_(question_ids),
            )
            .order_by(Answer.attempt_id.asc(), Answer.question_id.asc(), Answer.created_at.asc())
            .all()
        )
        for answer in answers:
            answers_by_attempt_question[(answer.attempt_id, answer.question_id)].append(answer)

    base_headers = [
        "survey_id",
        "survey_name",
        "participant_id",
        "participant_code",
        "consent_answer",
        "participant_name",
        "school",
        "grade",
        "dob",
        "attempt_id",
        "attempt_start_time",
        "attempt_end_time",
        "attempt_status",
        "completion_percentage",
    ]

    question_headers = []
    for index, _ in enumerate(questions, start=1):
        prefix = f"Q{index}"
        question_headers.extend(
            [
                f"{prefix}_Order",
                f"{prefix}_Type",
                f"{prefix}_Title",
                f"{prefix}_Answer",
                f"{prefix}_Angle_Answer",
                f"{prefix}_Deviation_Answer",
                f"{prefix}_Answered_At",
                f"{prefix}_Response_Time_Sec",
            ]
        )

    headers = base_headers + question_headers

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()

    for attempt in attempts:
        participant = attempt.participant
        previous_answered_at = None
        row_data = {
            "survey_id": _to_csv_value(survey.id),
            "survey_name": _to_csv_value(survey.name),
            "participant_id": _to_csv_value(participant.id if participant else None),
            "participant_code": _to_csv_value(participant.code if participant else None),
            "consent_answer": _to_csv_value(participant.consent if participant else None),
            "participant_name": _to_csv_value(participant.name if participant else None),
            "school": _to_csv_value(participant.school if participant else None),
            "grade": _to_csv_value(participant.grade if participant else None),
            "dob": _to_csv_value(participant.dob if participant else None),
            "attempt_id": _to_csv_value(attempt.id),
            "attempt_start_time": _to_csv_value(attempt.start_time),
            "attempt_end_time": _to_csv_value(attempt.end_time),
            "attempt_status": _to_csv_value(attempt.status),
            "completion_percentage": _to_csv_value(attempt.completion_percentage),
        }

        for index, question in enumerate(questions, start=1):
            prefix = f"Q{index}"
            answer_rows = answers_by_attempt_question.get((attempt.id, question.id), [])
            non_empty_answers = [answer for answer in answer_rows if _is_non_empty_answer(answer)]
            angle_answer_value = ""
            deviation_answer_value = ""
            correct_angle = question.config.correct_angle if question.config else None

            answered_at = None
            if non_empty_answers:
                answered_at = max(answer.created_at for answer in non_empty_answers)

            response_time_sec = None
            if answered_at is not None:
                baseline_time = previous_answered_at or attempt.start_time
                if baseline_time is not None:
                    elapsed = (answered_at - baseline_time).total_seconds()
                    response_time_sec = round(max(elapsed, 0.0), 2)
                previous_answered_at = answered_at

            if question.type == "mcq":
                option_values = []
                for answer in non_empty_answers:
                    if answer.selected_option_id is None:
                        continue
                    label = _format_mcq_option_label(answer)
                    if label:
                        option_values.append(label)
                option_values = _unique_preserve_order(option_values)
                answer_value = ", ".join(option_values) if option_values else "(no answer)"

            elif question.type == "text_entry":
                text_values = _unique_preserve_order(
                    [
                        answer.text_answer.strip()
                        for answer in non_empty_answers
                        if isinstance(answer.text_answer, str) and answer.text_answer.strip() != ""
                    ]
                )
                answer_value = " | ".join(text_values) if text_values else "(no answer)"

            elif question.type == "arrow":
                angle_values = []
                deviation_values = []
                for answer in non_empty_answers:
                    if answer.user_angle is not None:
                        angle_values.append(_format_decimal(float(answer.user_angle)))

                    if answer.angle_deviation is not None:
                        deviation_values.append(_format_decimal(float(answer.angle_deviation)))
                    elif answer.user_angle is not None and correct_angle is not None:
                        computed_deviation = _compute_arrow_deviation(answer.user_angle, correct_angle)
                        if computed_deviation is not None:
                            deviation_values.append(_format_decimal(float(computed_deviation)))

                angle_values = _unique_preserve_order(angle_values)
                deviation_values = _unique_preserve_order(deviation_values)

                angle_answer_value = ", ".join(angle_values)
                deviation_answer_value = ", ".join(deviation_values)
                if angle_answer_value and deviation_answer_value:
                    answer_value = f"{angle_answer_value} | {deviation_answer_value}"
                else:
                    answer_value = angle_answer_value or deviation_answer_value or "(no answer)"
            else:
                answer_value = _format_answer_summary(question.type, non_empty_answers)

            row_data[f"{prefix}_Order"] = _to_csv_value(question.order_index)
            row_data[f"{prefix}_Type"] = _to_csv_value(question.type)
            row_data[f"{prefix}_Title"] = _to_csv_value(question.title)
            row_data[f"{prefix}_Answer"] = _to_csv_value(answer_value)
            row_data[f"{prefix}_Angle_Answer"] = _to_csv_value(angle_answer_value)
            row_data[f"{prefix}_Deviation_Answer"] = _to_csv_value(deviation_answer_value)
            row_data[f"{prefix}_Answered_At"] = _to_csv_value(answered_at)
            row_data[f"{prefix}_Response_Time_Sec"] = _to_csv_value(response_time_sec)

        writer.writerow(row_data)

    filename = f"survey_{survey.id}_all_questions_responses.csv"
    return output.getvalue().encode("utf-8-sig"), filename


def get_question_analytics_by_id(db: Session, survey_id: UUID, question_id: UUID, current_user: User):
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

    question = (
        db.query(Question)
        .options(selectinload(Question.options))
        .filter(Question.id == question_id, Question.survey_id == survey_id)
        .first()
    )
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found in this survey",
        )

    attempts = (
        db.query(Attempt)
        .options(selectinload(Attempt.participant))
        .filter(Attempt.survey_id == survey_id)
        .order_by(Attempt.start_time.desc(), Attempt.id.desc())
        .all()
    )

    if not attempts:
        return QuestionAnalyticsResponse(
            survey_id=survey.id,
            survey_name=survey.name,
            question=QuestionAnalyticsMetaResponse(
                id=question.id,
                order_index=question.order_index,
                type=question.type,
                title=question.title,
            ),
            total_attempts=0,
            answered_attempts=0,
            rows=[],
        )

    attempt_ids = [attempt.id for attempt in attempts]

    question_answers = (
        db.query(Answer)
        .options(selectinload(Answer.selected_option))
        .filter(
            Answer.question_id == question.id,
            Answer.attempt_id.in_(attempt_ids),
        )
        .order_by(Answer.created_at.asc())
        .all()
    )

    answers_by_attempt: Dict[UUID, List[Answer]] = defaultdict(list)
    for answer in question_answers:
        answers_by_attempt[answer.attempt_id].append(answer)

    non_empty_answer_filter = or_(
        Answer.selected_option_id.isnot(None),
        Answer.user_angle.isnot(None),
        and_(Answer.text_answer.isnot(None), func.length(func.trim(Answer.text_answer)) > 0),
    )

    previous_answer_rows = (
        db.query(Answer.attempt_id, func.max(Answer.created_at))
        .join(Question, Question.id == Answer.question_id)
        .filter(
            Answer.attempt_id.in_(attempt_ids),
            Question.survey_id == survey_id,
            Question.order_index < question.order_index,
            non_empty_answer_filter,
        )
        .group_by(Answer.attempt_id)
        .all()
    )
    previous_answered_at_by_attempt = {
        attempt_id: answered_at for attempt_id, answered_at in previous_answer_rows
    }

    rows: List[QuestionAnalyticsRowResponse] = []
    answered_attempts = 0

    for attempt in attempts:
        participant = attempt.participant
        if participant is None:
            continue

        answers = answers_by_attempt.get(attempt.id, [])
        non_empty_answers = [answer for answer in answers if _is_non_empty_answer(answer)]

        answered_at = None
        if non_empty_answers:
            answered_at = max(answer.created_at for answer in non_empty_answers)
            answered_attempts += 1

        response_time_sec = None
        if answered_at is not None:
            baseline_time = previous_answered_at_by_attempt.get(attempt.id) or attempt.start_time
            if baseline_time is not None:
                elapsed = (answered_at - baseline_time).total_seconds()
                response_time_sec = round(max(elapsed, 0.0), 2)

        selected_option_ids = _unique_preserve_order(
            [answer.selected_option_id for answer in non_empty_answers if answer.selected_option_id is not None]
        )
        selected_option_orders = _unique_preserve_order(
            [
                int(answer.selected_option.order_index)
                for answer in non_empty_answers
                if answer.selected_option is not None and answer.selected_option.order_index is not None
            ]
        )
        user_angles = _unique_preserve_order(
            [float(answer.user_angle) for answer in non_empty_answers if answer.user_angle is not None]
        )
        angle_deviations = _unique_preserve_order(
            [float(answer.angle_deviation) for answer in non_empty_answers if answer.angle_deviation is not None]
        )
        text_answers = _unique_preserve_order(
            [
                answer.text_answer.strip()
                for answer in non_empty_answers
                if isinstance(answer.text_answer, str) and answer.text_answer.strip() != ""
            ]
        )

        rows.append(
            QuestionAnalyticsRowResponse(
                attempt_id=attempt.id,
                participant_id=participant.id,
                participant_code=participant.code,
                participant_name=participant.name,
                participant_school=participant.school,
                participant_grade=participant.grade,
                participant_dob=participant.dob,
                participant_consent=participant.consent,
                attempt_status=attempt.status,
                attempt_start_time=attempt.start_time,
                attempt_end_time=attempt.end_time,
                answered_at=answered_at,
                response_time_sec=response_time_sec,
                answer_summary=_format_answer_summary(question.type, non_empty_answers),
                selected_option_ids=selected_option_ids,
                selected_option_orders=selected_option_orders,
                user_angles=user_angles,
                angle_deviations=angle_deviations,
                text_answers=text_answers,
            )
        )

    return QuestionAnalyticsResponse(
        survey_id=survey.id,
        survey_name=survey.name,
        question=QuestionAnalyticsMetaResponse(
            id=question.id,
            order_index=question.order_index,
            type=question.type,
            title=question.title,
        ),
        total_attempts=len(attempts),
        answered_attempts=answered_attempts,
        rows=rows,
    )


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
        arrow_time_limit_sec=survey.arrow_time_limit_sec,
        mcq_time_limit_sec=survey.mcq_time_limit_sec,
        text_entry_time_limit_sec=survey.text_entry_time_limit_sec,
        participant_form_config=survey.participant_form_config,
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


def copy_survey(db: Session, survey_id: UUID, current_user: User):
    source_survey = (
        db.query(Survey)
        .options(
            selectinload(Survey.questions).selectinload(Question.options),
            selectinload(Survey.questions).selectinload(Question.config),
        )
        .filter(Survey.id == survey_id, Survey.created_by == current_user.id)
        .first()
    )

    if not source_survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found",
        )

    cloned_name = f"{source_survey.name} (Copy)"

    try:
        cloned_survey = Survey(
            name=cloned_name,
            token=_generate_unique_survey_token(db=db),
            created_by=current_user.id,
            start_time=source_survey.start_time,
            end_time=source_survey.end_time,
            status="pending",
            arrow_time_limit_sec=source_survey.arrow_time_limit_sec,
            mcq_time_limit_sec=source_survey.mcq_time_limit_sec,
            text_entry_time_limit_sec=source_survey.text_entry_time_limit_sec,
            participant_form_config=copy.deepcopy(source_survey.participant_form_config),
        )
        db.add(cloned_survey)
        db.flush()

        ordered_questions = sorted(
            source_survey.questions,
            key=lambda item: (
                item.order_index if item.order_index is not None else 0,
                item.created_at if item.created_at is not None else datetime.min,
            ),
        )
        for source_question in ordered_questions:
            cloned_question = Question(
                survey_id=cloned_survey.id,
                type=source_question.type,
                title=source_question.title,
                question_image=source_question.question_image,
                is_visible=source_question.is_visible,
                is_required=source_question.is_required,
                allow_multiple_selection=source_question.allow_multiple_selection,
                order_index=source_question.order_index,
            )
            db.add(cloned_question)
            db.flush()

            if source_question.type == "mcq":
                ordered_options = sorted(
                    source_question.options,
                    key=lambda item: item.order_index if item.order_index is not None else 0,
                )
                for source_option in ordered_options:
                    db.add(
                        QuestionOption(
                            question_id=cloned_question.id,
                            image_url=source_option.image_url,
                            order_index=source_option.order_index,
                        )
                    )

            if source_question.type == "arrow" and source_question.config is not None:
                db.add(
                    QuestionConfig(
                        question_id=cloned_question.id,
                        correct_angle=source_question.config.correct_angle,
                        tolerance=source_question.config.tolerance,
                        standing_position=source_question.config.standing_position,
                        looking_direction=source_question.config.looking_direction,
                    )
                )

        db.commit()
        copied_survey = (
            db.query(Survey)
            .options(
                selectinload(Survey.questions).selectinload(Question.options),
                selectinload(Survey.questions).selectinload(Question.config),
            )
            .filter(Survey.id == cloned_survey.id)
            .first()
        )
        return copied_survey
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


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
