import aiofiles
import asyncio
import uuid
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import PROJECT_ROOT
from app.core.dependencies import get_current_admin, get_excel_parser, get_session
from app.models.domain import User
from app.services.excel_parser import ExcelParser, ExcelParsingError, LeaveRecordSchema


router = APIRouter(prefix="/leave", tags=["Leave Management"])


UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"


@router.post(
    "/upload-leave-schedule",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Upload HR Excel file for leave schedule",
)
async def upload_leave_schedule(
    file: UploadFile = File(..., description="HR Excel file with leave records."),
    session: AsyncSession = Depends(get_session),
    current_admin: User = Depends(get_current_admin),
    excel_parser_service: ExcelParser = Depends(get_excel_parser),
) -> Dict[str, Any]:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    temp_file_path = UPLOAD_DIR / unique_filename

    try:
        async with aiofiles.open(temp_file_path, "wb") as buffer:
            while content := await file.read(1024 * 1024):  # 1MB 緩衝
                await buffer.write(content)


        parsed_records: list[LeaveRecordSchema] = await asyncio.to_thread(
            excel_parser_service.parse_excel_file, temp_file_path
        )

        # TODO: 執行資料庫操作：先刪除舊紀錄，再批量寫入新紀錄

        return {
            "message": f"Successfully processed {len(parsed_records)} leave records.",
            "records_count": len(parsed_records)
        }

    except ExcelParsingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Excel parsing failed", "errors": e.errors}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during file processing: {str(e)}"
        )
    finally:
        if temp_file_path.exists():
            temp_file_path.unlink()
