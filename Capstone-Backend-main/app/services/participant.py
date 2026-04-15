from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.survey import Answer, Attempt, Participant, Question, QuestionOption, Survey
from app.schemas.participant import ParticipantAnswerSubmitRequest, ParticipantSubmitRequest


def get_participant_by_survey_and_code(db: Session, survey_id, code: str):
    return (
        db.query(Participant)
        .filter(
            Participant.survey_id == survey_id,
            Participant.code == code
        )
        .first()
    )


def _get_survey_or_404(db: Session, survey_id: UUID):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found",
        )
    return survey


def _ensure_survey_active(survey: Survey):
    if survey.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Survey is not active",
        )


def _ensure_survey_answer_window_open(survey: Survey):
    now = datetime.utcnow()
    if survey.start_time and now < survey.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Survey has not started yet",
        )
    if survey.end_time and now > survey.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Survey has expired",
        )


def _get_attempt_or_404(db: Session, attempt_id: UUID):
    attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found",
        )
    return attempt


def _get_visible_question_or_404(db: Session, survey_id: UUID, question_id: UUID):
    question = (
        db.query(Question)
        .filter(
            Question.id == question_id,
            Question.survey_id == survey_id,
            Question.is_visible.is_(True),
        )
        .first()
    )
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found or not visible",
        )
    return question


def _is_empty_answer_payload(payload: ParticipantAnswerSubmitRequest):
    text_answer = payload.text_answer.strip() if isinstance(payload.text_answer, str) else ""
    return (
        payload.selected_option_id is None
        and not payload.selected_option_ids
        and payload.user_angle is None
        and not payload.user_angles
        and not text_answer
    )


def _validate_payload_for_question_type(question: Question, payload: ParticipantAnswerSubmitRequest):
    is_empty = _is_empty_answer_payload(payload)

    if is_empty:
        if getattr(question, "is_required", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Answer is required for this question",
            )
        return

    if question.type == "mcq":
        allow_multiple = bool(getattr(question, "allow_multiple_selection", False))
        if allow_multiple:
            if payload.selected_option_ids is None or len(payload.selected_option_ids) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="selected_option_ids is required for mcq question with allow_multiple_selection=true",
                )
            if payload.selected_option_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="selected_option_id must be null when allow_multiple_selection=true",
                )
        else:
            if payload.selected_option_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="selected_option_id is required for mcq question",
                )
            if payload.selected_option_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="selected_option_ids must be null when allow_multiple_selection=false",
                )
        if payload.user_angle is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_angle must be null for mcq question",
            )
        if payload.user_angles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_angles must be null for mcq question",
            )
        if payload.text_answer is not None and payload.text_answer.strip() != "":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="text_answer must be null for mcq question",
            )

    elif question.type == "arrow":
        if payload.user_angle is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_angle is required for arrow question",
            )
        if payload.user_angle < 0 or payload.user_angle > 360:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_angle must be in range [0, 360]",
            )
        if payload.user_angles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_angles must be null for arrow question",
            )

        if payload.selected_option_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="selected_option_id must be null for arrow question",
            )
        if payload.selected_option_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="selected_option_ids must be null for arrow question",
            )
        if payload.text_answer is not None and payload.text_answer.strip() != "":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="text_answer must be null for arrow question",
            )

    elif question.type == "text_entry":
        if payload.selected_option_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="selected_option_id must be null for text_entry question",
            )
        if payload.selected_option_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="selected_option_ids must be null for text_entry question",
            )
        if payload.user_angle is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_angle must be null for text_entry question",
            )
        if payload.user_angles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_angles must be null for text_entry question",
            )

        text_value = payload.text_answer.strip() if isinstance(payload.text_answer, str) else ""
        if not text_value and getattr(question, "is_required", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="text_answer is required for text_entry question",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported question type",
        )


def _validate_option_belongs_to_question(db: Session, question: Question, selected_option_id: UUID):
    option = (
        db.query(QuestionOption)
        .filter(
            QuestionOption.id == selected_option_id,
            QuestionOption.question_id == question.id,
        )
        .first()
    )
    if not option:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="selected_option_id does not belong to the question",
        )


def _validate_options_belong_to_question(db: Session, question: Question, selected_option_ids):
    option_ids = list({item for item in selected_option_ids if item is not None})
    if not option_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="selected_option_ids is required",
        )

    option_count = (
        db.query(func.count(QuestionOption.id))
        .filter(
            QuestionOption.question_id == question.id,
            QuestionOption.id.in_(option_ids),
        )
        .scalar()
    ) or 0

    if option_count != len(option_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more selected_option_ids do not belong to the question",
        )


def _upsert_answer(db: Session, attempt_id: UUID, payload: ParticipantAnswerSubmitRequest, angle_deviation=None):
    answer = (
        db.query(Answer)
        .filter(
            Answer.attempt_id == attempt_id,
            Answer.question_id == payload.question_id,
        )
        .first()
    )

    if answer:
        answer.selected_option_id = payload.selected_option_id
        answer.user_angle = payload.user_angle
        answer.angle_deviation = angle_deviation
        answer.text_answer = payload.text_answer.strip() if isinstance(payload.text_answer, str) else None
        return answer

    answer = Answer(
        attempt_id=attempt_id,
        question_id=payload.question_id,
        selected_option_id=payload.selected_option_id,
        user_angle=payload.user_angle,
        angle_deviation=angle_deviation,
        text_answer=payload.text_answer.strip() if isinstance(payload.text_answer, str) else None,
    )
    db.add(answer)
    db.flush()
    return answer


def _replace_multi_angle_answers(db: Session, attempt_id: UUID, question_id: UUID, user_angles):
    existing_answers = (
        db.query(Answer)
        .filter(
            Answer.attempt_id == attempt_id,
            Answer.question_id == question_id,
        )
        .all()
    )
    for existing_answer in existing_answers:
        db.delete(existing_answer)
    db.flush()

    created_answers = []
    for angle in user_angles:
        answer = Answer(
            attempt_id=attempt_id,
            question_id=question_id,
            selected_option_id=None,
            user_angle=angle,
            angle_deviation=None,
            text_answer=None,
        )
        db.add(answer)
        db.flush()
        created_answers.append(answer)

    return created_answers


def _replace_multi_option_answers(db: Session, attempt_id: UUID, question_id: UUID, selected_option_ids):
    existing_answers = (
        db.query(Answer)
        .filter(
            Answer.attempt_id == attempt_id,
            Answer.question_id == question_id,
        )
        .all()
    )
    for existing_answer in existing_answers:
        db.delete(existing_answer)
    db.flush()

    created_answers = []
    for option_id in selected_option_ids:
        answer = Answer(
            attempt_id=attempt_id,
            question_id=question_id,
            selected_option_id=option_id,
            user_angle=None,
            angle_deviation=None,
            text_answer=None,
        )
        db.add(answer)
        db.flush()
        created_answers.append(answer)

    return created_answers


def _replace_with_empty_answer(db: Session, attempt_id: UUID, question_id: UUID):
    existing_answers = (
        db.query(Answer)
        .filter(
            Answer.attempt_id == attempt_id,
            Answer.question_id == question_id,
        )
        .all()
    )
    for existing_answer in existing_answers:
        db.delete(existing_answer)
    db.flush()

    answer = Answer(
        attempt_id=attempt_id,
        question_id=question_id,
        selected_option_id=None,
        user_angle=None,
        angle_deviation=None,
        text_answer=None,
    )
    db.add(answer)
    db.flush()
    return answer


def _compute_arrow_deviation(user_angle, correct_angle):
    if user_angle is None or correct_angle is None:
        return None
    difference = abs((float(user_angle) - float(correct_angle)) % 360)
    return min(difference, 360 - difference)


def _calculate_attempt_progress(db: Session, attempt_id: UUID, survey_id: UUID):
    total_questions = (
        db.query(func.count(Question.id))
        .filter(
            Question.survey_id == survey_id,
            Question.is_visible.is_(True),
        )
        .scalar()
    ) or 0

    answered_count = (
        db.query(func.count(func.distinct(Answer.question_id)))
        .join(Question, Question.id == Answer.question_id)
        .filter(
            Answer.attempt_id == attempt_id,
            Question.survey_id == survey_id,
            Question.is_visible.is_(True),
        )
        .scalar()
    ) or 0

    completion_percentage = round((answered_count / total_questions) * 100, 2) if total_questions > 0 else 0.0
    return answered_count, total_questions, completion_percentage


def submit_participant(db: Session, payload: ParticipantSubmitRequest):
    survey = _get_survey_or_404(db, payload.survey_id)
    _ensure_survey_active(survey)

    code = (payload.code or "").strip()
    name = (payload.name or "").strip()
    school = (payload.school or "").strip() or None
    grade = (payload.grade or "").strip() or None
    dob = payload.dob
    consent = (payload.consent or "").strip().lower() or None

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Participant code is required",
        )

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Participant name is required",
        )

    if consent is not None and consent not in {"yes", "no"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="consent must be either 'yes' or 'no'",
        )

    form_config = survey.participant_form_config or {}
    fields_config = form_config.get("fields", {}) if isinstance(form_config, dict) else {}
    school_default = form_config.get("school_default") if isinstance(form_config, dict) else None
    if not school and isinstance(school_default, str) and school_default.strip():
        school = school_default.strip()

    def _is_required(field_name: str, default_required: bool):
        field_meta = fields_config.get(field_name, {}) if isinstance(fields_config, dict) else {}
        if isinstance(field_meta, dict) and field_meta.get("visible") is False:
            return False
        if isinstance(field_meta, dict) and "required" in field_meta:
            return bool(field_meta.get("required"))
        return default_required

    if _is_required("dob", True) and dob is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date of birth is required",
        )

    if _is_required("grade", True) and not grade:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Grade is required",
        )

    if _is_required("school", True) and not school:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="School is required",
        )

    participant = get_participant_by_survey_and_code(db, payload.survey_id, code)

    if participant:
        participant.name = name
        participant.school = school
        participant.grade = grade
        participant.dob = dob
        participant.consent = consent
    else:
        participant = Participant(
            survey_id=payload.survey_id,
            code=code,
            name=name,
            school=school,
            grade=grade,
            dob=dob,
            consent=consent,
        )
        db.add(participant)
        db.flush()

    attempt = Attempt(
        survey_id=payload.survey_id,
        participant_id=participant.id,
        start_time=datetime.utcnow(),
        status="in_progress",
        completion_percentage=0,
    )
    db.add(attempt)

    db.commit()
    db.refresh(participant)
    db.refresh(attempt)
    return {
        "participant": participant,
        "attempt": attempt,
    }


def submit_answer_one(db: Session, attempt_id: UUID, payload: ParticipantAnswerSubmitRequest):
    attempt = _get_attempt_or_404(db, attempt_id)
    if attempt.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Attempt is already completed",
        )

    survey = _get_survey_or_404(db, attempt.survey_id)
    _ensure_survey_active(survey)
    _ensure_survey_answer_window_open(survey)

    question = _get_visible_question_or_404(db, survey.id, payload.question_id)
    _validate_payload_for_question_type(question, payload)

    if payload.selected_option_id is not None:
        _validate_option_belongs_to_question(db, question, payload.selected_option_id)
    if payload.selected_option_ids:
        _validate_options_belong_to_question(db, question, payload.selected_option_ids)

    allow_multi_mcq = question.type == "mcq" and bool(getattr(question, "allow_multiple_selection", False))
    is_empty_payload = _is_empty_answer_payload(payload)
    arrow_deviation = None
    if question.type == "arrow" and payload.user_angle is not None:
        correct_angle = question.config.correct_angle if question.config is not None else None
        arrow_deviation = _compute_arrow_deviation(payload.user_angle, correct_angle)

    if is_empty_payload:
        answer = _replace_with_empty_answer(
            db=db,
            attempt_id=attempt.id,
            question_id=payload.question_id,
        )
        answer_ids = [answer.id]
    elif allow_multi_mcq:
        answers = _replace_multi_option_answers(
            db=db,
            attempt_id=attempt.id,
            question_id=payload.question_id,
            selected_option_ids=payload.selected_option_ids or [],
        )
        answer = answers[0]
        answer_ids = [item.id for item in answers]
    elif question.type == "arrow" and payload.user_angles:
        answers = _replace_multi_angle_answers(
            db=db,
            attempt_id=attempt.id,
            question_id=payload.question_id,
            user_angles=payload.user_angles or [],
        )
        answer = answers[0]
        answer_ids = [item.id for item in answers]
    else:
        answer = _upsert_answer(db, attempt.id, payload, angle_deviation=arrow_deviation)
        answer_ids = [answer.id]

    answered_count, total_questions, completion_percentage = _calculate_attempt_progress(db, attempt.id, survey.id)

    attempt.completion_percentage = completion_percentage
    if attempt.status == "pending":
        attempt.status = "in_progress"

    db.commit()
    db.refresh(attempt)
    db.refresh(answer)

    return {
        "attempt_id": attempt.id,
        "answer_id": answer.id,
        "answer_ids": answer_ids,
        "completion_percentage": attempt.completion_percentage,
        "answered_count": answered_count,
        "total_questions": total_questions,
        "status": attempt.status,
    }


def done_attempt(db: Session, attempt_id: UUID):
    attempt = _get_attempt_or_404(db, attempt_id)
    survey = _get_survey_or_404(db, attempt.survey_id)

    answered_count, total_questions, completion_percentage = _calculate_attempt_progress(db, attempt.id, survey.id)
    attempt.completion_percentage = completion_percentage
    attempt.status = "completed"
    if attempt.end_time is None:
        attempt.end_time = datetime.utcnow()

    db.commit()
    db.refresh(attempt)

    return {
        "attempt_id": attempt.id,
        "completion_percentage": attempt.completion_percentage,
        "answered_count": answered_count,
        "total_questions": total_questions,
        "status": attempt.status,
    }