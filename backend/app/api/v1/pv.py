from typing import Any, List, Optional
import uuid
import json
import os
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
import httpx
import boto3
from jose import jwt, JWTError

from app.api import deps
from app.models.user import User as UserModel
from app.models.pv import PV as PVModel, PVVersion as PVVersionModel
from app.models.action import Action as ActionModel
from app.services.pv_service import PVService
from app.services.pdf_service import PDFService
from app.services.docx_service import DOCXService
from app.schemas.pv import PVUpdate, PVVersion as PVVersionSchema
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate/{meeting_id}", status_code=202)
async def initiate_pv_generation_with_id(
    meeting_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Generates a PV (meeting minutes) for a meeting.
    """
    return {
        "message": "PV generation initiated",
        "pv_id": str(uuid.uuid4()),
        "status": "in_progress",
    }


@router.post("/generate", status_code=202)
async def initiate_pv_generation(
    data: dict,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Generates a PV (meeting minutes) from a transcription.
    """
    transcription_id = data.get("transcription_id")
    if not transcription_id:
        raise HTTPException(status_code=400, detail="transcription_id is required")

    return {
        "message": "PV generation initiated",
        "pv_id": str(uuid.uuid4()),
        "status": "in_progress",
    }


@router.get("/{pv_id}/pdf")
async def download_pv_pdf(
    pv_id: str,
    branding_id: Optional[str] = None,
    watermark: Optional[bool] = None,
    language: Optional[str] = "fr",
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Generates and downloads the PV as a PDF.
    Prefers the manually edited version from OnlyOffice if available in S3.
    Includes a retry mechanism to handle race conditions during conversion.
    """
    s3_key = f"pv_exports/{pv_id}/final_document.pdf"
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    
    # Retry mechanism: Conversion might take 2-3 seconds
    max_retries = 3
    for attempt in range(max_retries):
        try:
            s3.head_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
            
            logger.info(f"Serving edited PDF from S3 for PV {pv_id} (Attempt {attempt+1})")
            local_pdf_path = f"/tmp/final_{pv_id}_{uuid.uuid4().hex[:6]}.pdf"
            s3.download_file(settings.S3_BUCKET_NAME, s3_key, local_pdf_path)
            
            return FileResponse(
                path=local_pdf_path,
                filename=f"final_minutes_{pv_id}.pdf",
                media_type="application/pdf",
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )
        except Exception:
            if attempt < max_retries - 1:
                # If we don't find the PDF, but a DOCX edit exists, wait and retry
                docx_key = f"pv_exports/{pv_id}/edited_document.docx"
                try:
                    s3.head_object(Bucket=settings.S3_BUCKET_NAME, Key=docx_key)
                    logger.info(f"DOCX exists but PDF not ready for {pv_id}. Waiting 2s... (Attempt {attempt+1})")
                    import asyncio
                    await asyncio.sleep(2.0)
                    continue
                except:
                    break # No edited docx either, fall back immediately
            break

    # Fallback to standard PDF generation from HTML
    logger.info(f"No edited PDF found after retries for {pv_id}. Falling back to PDFService.")
    try:
        pdf_service = PDFService(db)
        pdf_path = await pdf_service.generate_pv_pdf(
            pv_id=pv_id, 
            client_id=current_user.client_id,
            branding_id=branding_id, 
            watermark=watermark,
            language=language
        )

        return FileResponse(
            path=pdf_path,
            filename=f"meeting_minutes_{pv_id}.pdf",
            media_type="application/pdf",
        )
    except Exception as ex:
        logger.error(f"PDF generation failed: {ex}")
        raise HTTPException(status_code=500, detail=str(ex))


@router.get("/{pv_id}/docx")
async def download_pv_docx(
    pv_id: str,
    language: Optional[str] = "fr",
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Generates and downloads the PV as a Word document (DOCX).
    Prefers the manually edited version from OnlyOffice if available.
    """
    s3_key = f"pv_exports/{pv_id}/edited_document.docx"
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    
    try:
        local_docx_path = f"/tmp/final_{pv_id}_{uuid.uuid4().hex[:6]}.docx"
        s3.download_file(settings.S3_BUCKET_NAME, s3_key, local_docx_path)
        
        return FileResponse(
            path=local_docx_path,
            filename=f"final_minutes_{pv_id}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception:
        try:
            docx_service = DOCXService(db)
            docx_path = await docx_service.generate_pv_docx(
                pv_id=pv_id, 
                client_id=current_user.client_id,
                language=language
            )

            return FileResponse(
                path=docx_path,
                filename=f"meeting_minutes_{pv_id}.docx",
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        except Exception as e:
            logger.error(f"DOCX generation failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/meeting/{meeting_id}")
async def get_pv_by_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    stmt = (
        select(PVModel)
        .options(selectinload(PVModel.sections))
        .where(PVModel.meeting_id == meeting_id)
        .where(PVModel.client_id == current_user.client_id)
    )
    result = await db.execute(stmt)
    pv = result.scalars().first()
    if not pv:
        raise HTTPException(status_code=404, detail="PV for meeting not found")

    actions_result = await db.execute(
        select(ActionModel).where(ActionModel.meeting_id == meeting_id).where(ActionModel.client_id == current_user.client_id)
    )
    actions = actions_result.scalars().all()

    return {
        "id": pv.id,
        "meeting_id": pv.meeting_id,
        "content": pv.content_html,
        "status": pv.status,
        "actions": [
            {
                "id": a.id,
                "description": a.title,
                "priority": a.priority,
                "status": a.status,
            }
            for a in actions
        ],
    }


@router.get("/{pv_id}")
async def get_pv(
    pv_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieves the generated PV content.
    """
    stmt = (
        select(PVModel)
        .options(selectinload(PVModel.sections))
        .where(PVModel.id == pv_id)
        .where(PVModel.client_id == current_user.client_id)
    )

    result = await db.execute(stmt)
    pv = result.scalars().first()

    if not pv:
        raise HTTPException(status_code=404, detail="PV not found")

    actions_result = await db.execute(
        select(ActionModel).where(ActionModel.meeting_id == pv.meeting_id).where(ActionModel.client_id == current_user.client_id)
    )
    actions = actions_result.scalars().all()

    return {
        "id": pv.id,
        "meeting_id": pv.meeting_id,
        "content": pv.content_html,
        "status": pv.status,
        "actions": [
            {
                "id": a.id,
                "description": a.description,
                "assigned_to": "Mocked User", 
            }
            for a in actions
        ],
    }


@router.post("/{pv_id}/validate")
async def validate_pv(
    pv_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Marks a PV as validated.
    """
    service = PVService(db)
    pv = await service.validate_pv(pv_id, current_user.id, current_user.client_id)

    if not pv:
        raise HTTPException(status_code=404, detail="PV not found")

    return {"message": "PV validated successfully", "status": pv.status}


@router.put("/{pv_id}", response_model=dict)
async def update_pv(
    pv_id: str,
    pv_in: PVUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Updates a PV and automatically creates an ISO 27001 compliant version snapshot.
    """
    stmt = select(PVModel).options(selectinload(PVModel.sections)).where(PVModel.id == pv_id).where(PVModel.client_id == current_user.client_id)
    result = await db.execute(stmt)
    pv = result.scalars().first()
    
    if not pv:
        raise HTTPException(status_code=404, detail="PV not found")
        
    v_stmt = select(PVVersionModel).where(PVVersionModel.pv_id == pv_id).order_by(desc(PVVersionModel.version_number))
    v_result = await db.execute(v_stmt)
    latest_version = v_result.scalars().first()
    next_version_num = latest_version.version_number + 1 if latest_version else 1
    
    snapshot = {
        "title": pv.title,
        "content_html": pv.content_html,
        "status": pv.status,
        "is_validated": pv.is_validated,
    }
    
    pv_version = PVVersionModel(
        id=str(uuid.uuid4()),
        pv_id=pv.id,
        version_number=next_version_num,
        snapshot_data=json.dumps(snapshot),
        change_summary=f"Updated by {current_user.email}",
        created_by_id=current_user.id
    )
    db.add(pv_version)
    
    update_data = pv_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(pv, field, value)
        
    await db.commit()
    await db.refresh(pv)
    
    return {"message": "PV updated successfully", "version_created": next_version_num}


@router.get("/{pv_id}/versions", response_model=List[PVVersionSchema])
async def list_pv_versions(
    pv_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    pv_stmt = select(PVModel.id).where(PVModel.id == pv_id).where(PVModel.client_id == current_user.client_id)
    pv_exists = (await db.execute(pv_stmt)).scalar_one_or_none()
    if not pv_exists:
        raise HTTPException(status_code=404, detail="PV not found")

    stmt = select(PVVersionModel).where(PVVersionModel.pv_id == pv_id).order_by(desc(PVVersionModel.version_number))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{pv_id}/versions/{version_id}", response_model=PVVersionSchema)
async def get_pv_version(
    pv_id: str,
    version_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    stmt = select(PVVersionModel).where(PVVersionModel.id == version_id, PVVersionModel.pv_id == pv_id)
    result = await db.execute(stmt)
    version = result.scalars().first()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.post("/{pv_id}/restore/{version_id}", response_model=dict)
async def restore_pv_version(
    pv_id: str,
    version_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    stmt = select(PVVersionModel).where(PVVersionModel.id == version_id, PVVersionModel.pv_id == pv_id)
    result = await db.execute(stmt)
    version = result.scalars().first()
    
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
        
    pv_stmt = select(PVModel).where(PVModel.id == pv_id).where(PVModel.client_id == current_user.client_id)
    pv_result = await db.execute(pv_stmt)
    pv = pv_result.scalars().first()
    
    if not pv:
        raise HTTPException(status_code=404, detail="PV not found")
        
    v_stmt = select(PVVersionModel).where(PVVersionModel.pv_id == pv_id).order_by(desc(PVVersionModel.version_number))
    v_result = await db.execute(v_stmt)
    latest_version = v_result.scalars().first()
    next_version_num = latest_version.version_number + 1 if latest_version else 1
    
    current_snapshot = {
        "title": pv.title,
        "content_html": pv.content_html,
        "status": pv.status,
        "is_validated": pv.is_validated,
    }
    
    backup_version = PVVersionModel(
        id=str(uuid.uuid4()),
        pv_id=pv.id,
        version_number=next_version_num,
        snapshot_data=json.dumps(current_snapshot),
        change_summary=f"Auto-backup before restoring to version {version.version_number}",
        created_by_id=current_user.id
    )
    db.add(backup_version)
    
    try:
        restore_data = json.loads(version.snapshot_data)
        for key, value in restore_data.items():
            if hasattr(pv, key):
                setattr(pv, key, value)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid snapshot data format")
        
    await db.commit()
    await db.refresh(pv)
    
    return {"message": f"Successfully restored to version {version.version_number}"}


@router.get("/{pv_id}/onlyoffice/config")
async def get_onlyoffice_config(
    pv_id: str,
    language: str = "fr",
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Returns the configuration required by OnlyOffice Document Editor.
    Includes on-the-fly translation via Mistral if languages mismatch.
    """
    stmt = select(PVModel).where(PVModel.id == pv_id).where(PVModel.client_id == current_user.client_id)
    result = await db.execute(stmt)
    pv = result.scalars().first()
    if not pv:
        raise HTTPException(status_code=404, detail="PV not found")

    # Generate the DOCX file (includes translation if needed)
    docx_service = DOCXService(db)
    local_path = await docx_service.generate_pv_docx(pv_id, current_user.client_id, language=language)
    filename = os.path.basename(local_path)
    file_key = f"tmp_edits/{pv_id}/{filename}"

    # Upload to MinIO for OnlyOffice access
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    with open(local_path, "rb") as f:
        s3.upload_fileobj(f, settings.S3_BUCKET_NAME, file_key)
    
    # URL for OnlyOffice to download the file (Proxied via backend)
    download_url = f"{settings.ONLYOFFICE_BACKEND_URL}/api/v1/pv/{pv_id}/onlyoffice/download?file_key={file_key}"
    callback_url = f"{settings.ONLYOFFICE_BACKEND_URL}/api/v1/pv/{pv_id}/onlyoffice/callback"

    config = {
        "document": {
            "fileType": "docx",
            "key": f"{pv_id}_{int(datetime.utcnow().timestamp())}", 
            "title": f"PV_{pv.title}.docx",
            "url": download_url,
            "permissions": {
                "edit": True,
                "download": True,
            }
        },
        "editorConfig": {
            "callbackUrl": callback_url,
            "user": {
                "id": current_user.id,
                "name": current_user.full_name or current_user.email
            },
            "lang": language,
            "customization": {
                "forcesave": True,
                "onlyOfficeUrl": settings.ONLYOFFICE_URL 
            }
        }
    }

    token = jwt.encode(config, settings.ONLYOFFICE_SECRET, algorithm="HS256")
    config["token"] = token

    return config


@router.get("/{pv_id}/onlyoffice/download")
async def onlyoffice_download(
    pv_id: str,
    file_key: str,
) -> Any:
    """
    Proxies the file download from MinIO to OnlyOffice.
    """
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    try:
        response = s3.get_object(Bucket=settings.S3_BUCKET_NAME, Key=file_key)
        return StreamingResponse(
            response['Body'].iter_chunks(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception:
        raise HTTPException(status_code=404, detail="File not found")


@router.post("/{pv_id}/onlyoffice/callback")
async def onlyoffice_callback(
    pv_id: str,
    data: dict,
    request: Request,
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Handles the callback from OnlyOffice.
    Saves edited DOCX and triggers PDF conversion.
    """
    auth_header = request.headers.get("Authorization")
    token = ""
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    elif "token" in data:
        token = data["token"]

    try:
        decoded = jwt.decode(token, settings.ONLYOFFICE_SECRET, algorithms=["HS256"])
        if "payload" in decoded:
            data = decoded["payload"]
    except JWTError:
        return {"error": 1}

    status = data.get("status")
    
    if status == 2:
        download_url = data.get("url")
        if not download_url:
            return {"error": 0}

        if download_url.startswith(settings.ONLYOFFICE_URL):
            download_url = download_url.replace(settings.ONLYOFFICE_URL, "http://onlyoffice:80")
        elif "localhost:8080" in download_url:
            download_url = download_url.replace("localhost:8080", "onlyoffice:80")

        async with httpx.AsyncClient() as client:
            resp = await client.get(download_url)
            if resp.status_code != 200:
                logger.error(f"OnlyOffice callback download failed: {resp.status_code}")
                return {"error": 1}
            content = resp.content

        stmt = select(PVModel).where(PVModel.id == pv_id)
        result = await db.execute(stmt)
        pv = result.scalars().first()
        if not pv:
             return {"error": 1}

        docx_key = f"pv_exports/{pv_id}/edited_document.docx"
        s3 = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
        )
        s3.put_object(Bucket=settings.S3_BUCKET_NAME, Key=docx_key, Body=content)

        v_stmt = select(PVVersionModel).where(PVVersionModel.pv_id == pv_id).order_by(desc(PVVersionModel.version_number))
        v_result = await db.execute(v_stmt)
        latest_version = v_result.scalars().first()
        next_version_num = latest_version.version_number + 1 if latest_version else 1
        
        snapshot = {"title": pv.title, "s3_path": docx_key, "edited_online": True}
        pv_version = PVVersionModel(
            id=str(uuid.uuid4()),
            pv_id=pv.id,
            version_number=next_version_num,
            snapshot_data=json.dumps(snapshot),
            change_summary="Edited via OnlyOffice Online",
            created_by_id=data.get("users", ["system"])[0]
        )
        db.add(pv_version)
        await db.commit()

        try:
            # Modern endpoint is /converter
            conv_url = "http://onlyoffice/converter"
            # Use internal backend name for OnlyOffice to reach proxy
            source_url = f"http://backend:8000/api/v1/pv/{pv_id}/onlyoffice/download?file_key={docx_key}"
            
            payload = {
                "async": False,
                "filetype": "docx",
                "key": f"{pv_id}_{int(datetime.utcnow().timestamp())}",
                "outputtype": "pdf",
                "url": source_url,
            }
            # Sign the payload - OnlyOffice requires the token to be in the payload AND/OR header
            conv_token = jwt.encode(payload, settings.ONLYOFFICE_SECRET, algorithm="HS256")
            payload["token"] = conv_token
            
            async with httpx.AsyncClient() as client:
                conv_resp = await client.post(
                    conv_url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {conv_token}",
                        "Accept": "application/json"
                    },
                    timeout=45.0
                )
                
                if conv_resp.status_code == 200:
                    conv_data = conv_resp.json()
                    # Check for conversion errors (OnlyOffice uses "error" field)
                    if "error" in conv_data and conv_data["error"] != 0:
                        logger.error(f"OnlyOffice conversion error code: {conv_data['error']}")
                    else:
                        pdf_url = conv_data.get("fileUrl")
                        if pdf_url:
                            # OnlyOffice might return localhost in URL, fix for internal network
                            if pdf_url.startswith(settings.ONLYOFFICE_URL):
                                pdf_url = pdf_url.replace(settings.ONLYOFFICE_URL, "http://onlyoffice:80")
                            elif "localhost:8080" in pdf_url:
                                pdf_url = pdf_url.replace("localhost:8080", "onlyoffice:80")

                            pdf_resp = await client.get(pdf_url)
                            if pdf_resp.status_code == 200:
                                pdf_key = f"pv_exports/{pv_id}/final_document.pdf"
                                s3.put_object(Bucket=settings.S3_BUCKET_NAME, Key=pdf_key, Body=pdf_resp.content)
                                snapshot["pdf_s3_path"] = pdf_key
                                pv_version.snapshot_data = json.dumps(snapshot)
                                await db.commit()
                                logger.info(f"Successfully auto-converted edited PV {pv_id} to PDF")
                else:
                    logger.error(f"OnlyOffice converter returned status {conv_resp.status_code}: {conv_resp.text}")
        except Exception as e:
            logger.error(f"Auto-conversion to PDF failed: {e}")

    return {"error": 0}
