from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SurveyStatusEnum(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"


class QuestionTypeEnum(str, Enum):
    MCQ = "mcq"
    ARROW = "arrow"
    TEXT_ENTRY = "text_entry"


class QuestionOptionCreate(BaseModel):
    id: Optional[UUID] = None
    image_url: str
    order_index: int


class QuestionConfigCreate(BaseModel):
    id: Optional[UUID] = None
    correct_angle: float
    tolerance: float
    standing_position: Optional[str] = None
    looking_direction: Optional[str] = None


class QuestionCreate(BaseModel):
    id: Optional[UUID] = None
    type: QuestionTypeEnum
    title: str
    question_image: Optional[str] = None
    is_visible: bool = False
    is_required: bool = False
    allow_multiple_selection: bool = False
    order_index: int
    options: Optional[List[QuestionOptionCreate]] = None
    config: Optional[QuestionConfigCreate] = None


class SurveyCreateRequest(BaseModel):
    id: Optional[UUID] = None
    name: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[SurveyStatusEnum] = None
    arrow_time_limit_sec: Optional[int] = None
    mcq_time_limit_sec: Optional[int] = None
    text_entry_time_limit_sec: Optional[int] = None
    participant_form_config: Optional[Dict[str, Any]] = None
    questions: List[QuestionCreate] = Field(default_factory=list)


class QuestionOptionResponse(BaseModel):
    id: UUID
    question_id: UUID
    image_url: str
    order_index: int

    class Config:
        from_attributes = True


class QuestionConfigResponse(BaseModel):
    question_id: UUID
    correct_angle: float
    tolerance: float
    standing_position: Optional[str] = None
    looking_direction: Optional[str] = None

    class Config:
        from_attributes = True


class QuestionResponse(BaseModel):
    id: UUID
    survey_id: UUID
    type: QuestionTypeEnum
    title: str
    question_image: Optional[str] = None
    is_visible: bool
    is_required: bool
    allow_multiple_selection: bool
    order_index: int
    created_at: datetime
    options: List[QuestionOptionResponse] = Field(default_factory=list)
    config: Optional[QuestionConfigResponse] = None

    class Config:
        from_attributes = True


class SurveyCreateResponse(BaseModel):
    id: UUID
    name: str
    token: str
    created_by: UUID
    created_at: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: SurveyStatusEnum
    arrow_time_limit_sec: Optional[int] = None
    mcq_time_limit_sec: Optional[int] = None
    text_entry_time_limit_sec: Optional[int] = None
    participant_form_config: Optional[Dict[str, Any]] = None
    questions: List[QuestionResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True

class GenerateTokenResponse(BaseModel):
    id: UUID
    token: str

    class Config:
        from_attributes = True


class SurveyDeleteResponse(BaseModel):
    id: UUID
    detail: str


class SurveyListItemResponse(BaseModel):
    id: UUID
    name: str
    token: str
    created_by: UUID
    created_at: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: SurveyStatusEnum
    arrow_time_limit_sec: Optional[int] = None
    mcq_time_limit_sec: Optional[int] = None
    text_entry_time_limit_sec: Optional[int] = None

    class Config:
        from_attributes = True


class PublicQuestionOptionResponse(BaseModel):
    id: UUID
    question_id: UUID
    image_url: str
    order_index: int


class PublicQuestionConfigResponse(BaseModel):
    question_id: UUID
    tolerance: float
    standing_position: Optional[str] = None
    looking_direction: Optional[str] = None


class PublicQuestionResponse(BaseModel):
    id: UUID
    survey_id: UUID
    type: QuestionTypeEnum
    title: str
    question_image: Optional[str] = None
    is_visible: bool
    is_required: bool
    allow_multiple_selection: bool
    order_index: int
    options: List[PublicQuestionOptionResponse] = Field(default_factory=list)
    config: Optional[PublicQuestionConfigResponse] = None


class SurveyShowByTokenResponse(BaseModel):
    id: UUID
    name: str
    token: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: SurveyStatusEnum
    arrow_time_limit_sec: Optional[int] = None
    mcq_time_limit_sec: Optional[int] = None
    text_entry_time_limit_sec: Optional[int] = None
    participant_form_config: Optional[Dict[str, Any]] = None
    questions: List[PublicQuestionResponse] = Field(default_factory=list)
