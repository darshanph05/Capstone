from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class QuestionAnalyticsMetaResponse(BaseModel):
    id: UUID
    order_index: int
    type: str
    title: str


class QuestionAnalyticsRowResponse(BaseModel):
    attempt_id: UUID
    participant_id: UUID
    participant_code: str
    participant_name: str
    participant_school: Optional[str] = None
    participant_grade: Optional[str] = None
    participant_dob: Optional[date] = None
    participant_consent: Optional[str] = None
    attempt_status: str
    attempt_start_time: Optional[datetime] = None
    attempt_end_time: Optional[datetime] = None
    answered_at: Optional[datetime] = None
    response_time_sec: Optional[float] = None
    answer_summary: str
    selected_option_ids: List[UUID] = Field(default_factory=list)
    selected_option_orders: List[int] = Field(default_factory=list)
    user_angles: List[float] = Field(default_factory=list)
    angle_deviations: List[float] = Field(default_factory=list)
    text_answers: List[str] = Field(default_factory=list)


class QuestionAnalyticsResponse(BaseModel):
    survey_id: UUID
    survey_name: str
    question: QuestionAnalyticsMetaResponse
    total_attempts: int
    answered_attempts: int
    rows: List[QuestionAnalyticsRowResponse] = Field(default_factory=list)
