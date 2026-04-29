from pydantic import BaseModel


class UploadFileResponse(BaseModel):
    filename: str
    key: str
    url: str
    content_type: str
    size: int
