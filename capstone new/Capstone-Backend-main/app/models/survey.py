import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.timezone import now_canberra_naive


class Survey(Base):
    __tablename__ = "surveys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    token = Column(String, nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=now_canberra_naive)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="pending")
    arrow_time_limit_sec = Column(Integer, nullable=True)
    mcq_time_limit_sec = Column(Integer, nullable=True)
    text_entry_time_limit_sec = Column(Integer, nullable=True)
    participant_form_config = Column(JSON, nullable=True)

    created_by_user = relationship("User", back_populates="created_surveys")
    questions = relationship("Question", back_populates="survey", cascade="all, delete-orphan")
    participants = relationship("Participant", back_populates="survey", cascade="all, delete-orphan")
    attempts = relationship("Attempt", back_populates="survey", cascade="all, delete-orphan")

    


class Question(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    survey_id = Column(UUID(as_uuid=True), ForeignKey("surveys.id"), nullable=False)
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    question_image = Column(String, nullable=True)
    is_visible = Column(Boolean, nullable=False, default=False)
    is_required = Column(Boolean, nullable=False, default=False)
    allow_multiple_selection = Column(Boolean, nullable=False, default=False)
    order_index = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=now_canberra_naive)

    survey = relationship("Survey", back_populates="questions")
    options = relationship("QuestionOption", back_populates="question", cascade="all, delete-orphan")
    config = relationship("QuestionConfig", back_populates="question", uselist=False, cascade="all, delete-orphan")
    answers = relationship("Answer", back_populates="question", cascade="all, delete-orphan")


class QuestionOption(Base):
    __tablename__ = "question_options"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    image_url = Column(String, nullable=False)
    order_index = Column(Integer, nullable=False)

    question = relationship("Question", back_populates="options")
    answers = relationship("Answer", back_populates="selected_option")


class QuestionConfig(Base):
    __tablename__ = "question_config"

    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), primary_key=True)
    correct_angle = Column(Float, nullable=False)
    tolerance = Column(Float, nullable=False)
    standing_position = Column(String, nullable=True)
    looking_direction = Column(String, nullable=True)
    allow_multiple_selection = Column(Boolean, nullable=False, default=False)

    question = relationship("Question", back_populates="config")


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (
        UniqueConstraint("survey_id", "code", name="uq_participants_survey_code"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    survey_id = Column(UUID(as_uuid=True), ForeignKey("surveys.id"), nullable=False, index=True)
    code = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    school = Column(String, nullable=True)
    grade = Column(String, nullable=True)
    dob = Column(Date, nullable=True)
    consent = Column(String, nullable=True)
    created_at = Column(DateTime, default=now_canberra_naive)

    survey = relationship("Survey", back_populates="participants")
    attempts = relationship("Attempt", back_populates="participant", cascade="all, delete-orphan")


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    survey_id = Column(UUID(as_uuid=True), ForeignKey("surveys.id"), nullable=False)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id"), nullable=False)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="pending")
    score = Column(Float, nullable=True)
    completion_percentage = Column(Float, nullable=False, default=0)

    survey = relationship("Survey", back_populates="attempts")
    participant = relationship("Participant", back_populates="attempts")
    answers = relationship("Answer", back_populates="attempt", cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "answers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("attempts.id"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    selected_option_id = Column(UUID(as_uuid=True), ForeignKey("question_options.id"), nullable=True)
    user_angle = Column(Float, nullable=True)
    angle_deviation = Column(Float, nullable=True)
    text_answer = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now_canberra_naive)

    attempt = relationship("Attempt", back_populates="answers")
    question = relationship("Question", back_populates="answers")
    selected_option = relationship("QuestionOption", back_populates="answers")


