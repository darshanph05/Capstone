from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.models.user import User
from app.schemas.upload import UploadFileResponse
from app.services.auth import get_current_user
from app.services.storage import upload_file_to_r2

router = APIRouter(
    prefix="/upload",
    tags=["Upload"],
)

@router.post("/image", response_model=UploadFileResponse)
def upload_image(
    file: UploadFile = File(...),
    folder: str = Query("images", min_length=1, description="R2 folder path"),
    current_user: User = Depends(get_current_user),
):
    return upload_file_to_r2(file=file, folder=folder, allowed_content_prefix="image/")
