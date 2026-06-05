from typing import Any, List, Optional
import uuid
import json
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
import httpx
import boto3
import redis
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
from app.core.database import AsyncSessionLocal

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Redis for conversion status tracking
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

async def run_pdf_conversion(pv_id: str, docx_key: str, pdf_key: str):
    """
    Robust background task for OnlyOffice PDF conversion.
    Tracks status in Redis to prevent stale downloads.
    """
    status_key = f"pdf_converting_{pv_id}"
    try:
        # Note: Redis key is now set in the callback for immediate visibility
        conv_url = "http://onlyoffice/converter"
        source_url = f"http://backend:8000/api/v1/pv/{pv_id}/onlyoffice/download?file_key={docx_key}"
        
        payload = {
            "async": False,
            "filetype": "docx",
            "key": f"{pv_id}_{uuid.uuid4().hex[:8]}", # Unique cache-busting key
            "outputtype": "pdf",
            "url": source_url,
        }
        conv_token = jwt.encode(payload, settings.ONLYOFFICE_SECRET, algorithm="HS256")
        payload["token"] = conv_token
        
        async with httpx.AsyncClient() as client:
            conv_resp = await client.post(
                conv_url,
                json=payload,
                headers={"Authorization": f"Bearer {conv_token}", "Accept": "application/json"},
                timeout=60.0
            )
            
            if conv_resp.status_code == 200:
                conv_data = conv_resp.json()
                if conv_data.get("error") == 0 or "fileUrl" in conv_data:
                    pdf_url = conv_data.get("fileUrl")
                    if pdf_url:
                        # Internal network fix
                        if pdf_url.startswith(settings.ONLYOFFICE_URL):
                            pdf_url = pdf_url.replace(settings.ONLYOFFICE_URL, "http://onlyoffice:80")
                        elif "localhost:8080" in pdf_url:
                            pdf_url = pdf_url.replace("localhost:8080", "onlyoffice:80")

                        pdf_resp = await client.get(pdf_url)
                        if pdf_resp.status_code == 200:
                            s3 = boto3.client("s3", endpoint_url=settings.S3_ENDPOINT,
                                            aws_access_key_id=settings.S3_ACCESS_KEY,
                                            aws_secret_access_key=settings.S3_SECRET_KEY)
                            s3.put_object(Bucket=settings.S3_BUCKET_NAME, Key=pdf_key, Body=pdf_resp.content)
                            logger.info(f"Background PDF conversion successful for {pv_id}")
                else:
                    logger.error(f"OnlyOffice converter returned error for {pv_id}: {conv_data}")
            else:
                logger.error(f"OnlyOffice converter connection failed for {pv_id}: {conv_resp.status_code}")
    except Exception as e:
        logger.error(f"Background PDF conversion failed for {pv_id}: {e}")
    finally:
        # Always clear the status so the download can proceed (even on failure)
        redis_client.delete(status_key)


@router.post("/generate/{meeting_id}", status_code=202)
async def initiate_pv_generation_with_id(
    meeting_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
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
    Downloads the PV as a PDF. Prefers the OnlyOffice converted version if it is up-to-date.
    Uses Redis and S3 metadata comparison to avoid race conditions.
    """
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    
    docx_key = f"pv_exports/{pv_id}/edited_document.docx"
    pdf_key = f"pv_exports/{pv_id}/final_document.pdf"
    status_key = f"pdf_converting_{pv_id}"
    
    # Retry mechanism: Wait if a conversion is in progress or PDF is stale
    max_retries = 25 # Increased to 50 seconds total
    import asyncio
    
    for attempt in range(max_retries):
        # 1. Check Redis status first (set by callback)
        if redis_client.get(status_key):
            logger.info(f"PDF conversion for PV {pv_id} flagged in Redis. Waiting... ({attempt+1}/{max_retries})")
            await asyncio.sleep(2.0)
            continue
            
        try:
            # 2. Check if edited DOCX exists
            docx_meta = s3.head_object(Bucket=settings.S3_BUCKET_NAME, Key=docx_key)
            docx_time = docx_meta['LastModified']
            
            try:
                # 3. Check if converted PDF exists
                pdf_meta = s3.head_object(Bucket=settings.S3_BUCKET_NAME, Key=pdf_key)
                pdf_time = pdf_meta['LastModified']
                
                # Use 1-second margin to account for S3 timestamp granularity
                if pdf_time >= docx_time:
                    logger.info(f"Serving up-to-date edited PDF from S3 for PV {pv_id}")
                    local_pdf_path = f"/tmp/final_{pv_id}_{uuid.uuid4().hex[:6]}.pdf"
                    s3.download_file(settings.S3_BUCKET_NAME, pdf_key, local_pdf_path)
                    
                    return FileResponse(
                        path=local_pdf_path,
                        filename=f"final_{pv_id}.pdf",
                        media_type="application/pdf",
                        headers={
                            "Cache-Control": "no-cache, no-store, must-revalidate, proxy-revalidate",
                            "Pragma": "no-cache",
                            "Expires": "0",
                            "Content-Disposition": f"attachment; filename=final_{pv_id}.pdf"
                        }
                    )
                else:
                    logger.info(f"PDF ({pdf_time}) is older than DOCX ({docx_time}). Waiting... ({attempt+1}/{max_retries})")
                    await asyncio.sleep(2.0)
                    continue
            except Exception:
                # PDF not found (likely deleted by callback to trigger refresh)
                logger.info(f"DOCX exists but PDF not ready. Waiting... ({attempt+1}/{max_retries})")
                await asyncio.sleep(2.0)
                continue
        except Exception:
            # No edited DOCX found at all, fall back to standard HTML->PDF generation
            logger.info(f"No edited DOCX found for {pv_id}. Falling back to standard generation.")
            break

    # Fallback to standard PDF generation from HTML (Database content)
    try:
        pdf_service = PDFService(db)
        pdf_path = await pdf_service.generate_pv_pdf(
            pv_id=pv_id, 
            client_id=current_user.client_id,
            branding_id=branding_id, 
            watermark=watermark,
            language=language
        )
        return FileResponse(path=pdf_path, filename=f"meeting_minutes_{pv_id}.pdf", media_type="application/pdf")
    except Exception as ex:
        logger.error(f"Fallback PDF generation failed: {ex}")
        raise HTTPException(status_code=500, detail=str(ex))



@router.get("/{pv_id}/docx")
async def download_pv_docx(
    pv_id: str,
    language: Optional[str] = "fr",
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    s3_key = f"pv_exports/{pv_id}/edited_document.docx"
    s3 = boto3.client("s3", endpoint_url=settings.S3_ENDPOINT, aws_access_key_id=settings.S3_ACCESS_KEY, aws_secret_access_key=settings.S3_SECRET_KEY)
    try:
        local_docx_path = f"/tmp/final_{pv_id}_{uuid.uuid4().hex[:6]}.docx"
        s3.download_file(settings.S3_BUCKET_NAME, s3_key, local_docx_path)
        return FileResponse(local_docx_path, filename=f"final_minutes_{pv_id}.docx", media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    except Exception:
        try:
            docx_service = DOCXService(db)
            docx_path = await docx_service.generate_pv_docx(pv_id, current_user.client_id, language=language)
            return FileResponse(docx_path, filename=f"meeting_minutes_{pv_id}.docx", media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/meeting/{meeting_id}")
async def get_pv_by_meeting(meeting_id: str, db: AsyncSession = Depends(deps.get_db), current_user: UserModel = Depends(deps.get_current_user)) -> Any:
    stmt = select(PVModel).options(selectinload(PVModel.sections)).where(PVModel.meeting_id == meeting_id, PVModel.client_id == current_user.client_id)
    result = await db.execute(stmt)
    pv = result.scalars().first()
    if not pv: raise HTTPException(status_code=404, detail="PV for meeting not found")
    actions_result = await db.execute(select(ActionModel).where(ActionModel.meeting_id == meeting_id, ActionModel.client_id == current_user.client_id))
    actions = actions_result.scalars().all()
    return {"id": pv.id, "meeting_id": pv.meeting_id, "content": pv.content_html, "status": pv.status, "actions": [{"id": a.id, "description": a.title, "priority": a.priority, "status": a.status} for a in actions]}


@router.get("/{pv_id}")
async def get_pv(pv_id: str, db: AsyncSession = Depends(deps.get_db), current_user: UserModel = Depends(deps.get_current_user)) -> Any:
    stmt = select(PVModel).options(selectinload(PVModel.sections)).where(PVModel.id == pv_id, PVModel.client_id == current_user.client_id)
    result = await db.execute(stmt)
    pv = result.scalars().first()
    if not pv: raise HTTPException(status_code=404, detail="PV not found")
    actions_result = await db.execute(select(ActionModel).where(ActionModel.meeting_id == pv.meeting_id, ActionModel.client_id == current_user.client_id))
    actions = actions_result.scalars().all()
    return {"id": pv.id, "meeting_id": pv.meeting_id, "title": pv.title, "content": pv.content_html, "status": pv.status, "actions": [{"id": a.id, "description": a.description, "assigned_to": "Mocked User"} for a in actions]}


@router.post("/{pv_id}/validate")
async def validate_pv(pv_id: str, db: AsyncSession = Depends(deps.get_db), current_user: UserModel = Depends(deps.get_current_user)) -> Any:
    service = PVService(db)
    pv = await service.validate_pv(pv_id, current_user.id, current_user.client_id)
    if not pv: raise HTTPException(status_code=404, detail="PV not found")
    return {"message": "PV validated successfully", "status": pv.status}


@router.put("/{pv_id}", response_model=dict)
async def update_pv(pv_id: str, pv_in: PVUpdate, db: AsyncSession = Depends(deps.get_db), current_user: UserModel = Depends(deps.get_current_user)) -> Any:
    stmt = select(PVModel).options(selectinload(PVModel.sections)).where(PVModel.id == pv_id, PVModel.client_id == current_user.client_id)
    result = await db.execute(stmt)
    pv = result.scalars().first()
    if not pv: raise HTTPException(status_code=404, detail="PV not found")
    v_stmt = select(PVVersionModel).where(PVVersionModel.pv_id == pv_id).order_by(desc(PVVersionModel.version_number))
    v_result = await db.execute(v_stmt)
    latest_version = v_result.scalars().first()
    next_version_num = latest_version.version_number + 1 if latest_version else 1
    snapshot = {"title": pv.title, "content_html": pv.content_html, "status": pv.status, "is_validated": pv.is_validated}
    pv_version = PVVersionModel(id=str(uuid.uuid4()), pv_id=pv.id, version_number=next_version_num, snapshot_data=json.dumps(snapshot), change_summary=f"Updated by {current_user.email}", created_by_id=current_user.id)
    db.add(pv_version)
    update_data = pv_in.model_dump(exclude_unset=True)
    for field, value in update_data.items(): setattr(pv, field, value)
    await db.commit()
    await db.refresh(pv)
    return {"message": "PV updated successfully", "version_created": next_version_num}


@router.get("/{pv_id}/versions", response_model=List[PVVersionSchema])
async def list_pv_versions(pv_id: str, db: AsyncSession = Depends(deps.get_db), current_user: UserModel = Depends(deps.get_current_user)) -> Any:
    pv_stmt = select(PVModel.id).where(PVModel.id == pv_id, PVModel.client_id == current_user.client_id)
    if not (await db.execute(pv_stmt)).scalar_one_or_none(): raise HTTPException(status_code=404, detail="PV not found")
    stmt = select(PVVersionModel).where(PVVersionModel.pv_id == pv_id).order_by(desc(PVVersionModel.version_number))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{pv_id}/versions/{version_id}", response_model=PVVersionSchema)
async def get_pv_version(pv_id: str, version_id: str, db: AsyncSession = Depends(deps.get_db), current_user: UserModel = Depends(deps.get_current_user)) -> Any:
    pv_stmt = select(PVModel.id).where(PVModel.id == pv_id, PVModel.client_id == current_user.client_id)
    if not (await db.execute(pv_stmt)).scalar_one_or_none(): raise HTTPException(status_code=404, detail="PV not found")
    stmt = select(PVVersionModel).where(PVVersionModel.id == version_id, PVVersionModel.pv_id == pv_id)
    result = await db.execute(stmt)
    version = result.scalars().first()
    if not version: raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.post("/{pv_id}/restore/{version_id}", response_model=dict)
async def restore_pv_version(pv_id: str, version_id: str, db: AsyncSession = Depends(deps.get_db), current_user: UserModel = Depends(deps.get_current_user)) -> Any:
    stmt = select(PVVersionModel).where(PVVersionModel.id == version_id, PVVersionModel.pv_id == pv_id)
    result = await db.execute(stmt)
    version = result.scalars().first()
    if not version: raise HTTPException(status_code=404, detail="Version not found")
    pv_stmt = select(PVModel).where(PVModel.id == pv_id, PVModel.client_id == current_user.client_id)
    pv = (await db.execute(pv_stmt)).scalars().first()
    if not pv: raise HTTPException(status_code=404, detail="PV not found")
    v_stmt = select(PVVersionModel).where(PVVersionModel.pv_id == pv_id).order_by(desc(PVVersionModel.version_number))
    latest_version = (await db.execute(v_stmt)).scalars().first()
    next_version_num = latest_version.version_number + 1 if latest_version else 1
    current_snapshot = {"title": pv.title, "content_html": pv.content_html, "status": pv.status, "is_validated": pv.is_validated}
    db.add(PVVersionModel(id=str(uuid.uuid4()), pv_id=pv.id, version_number=next_version_num, snapshot_data=json.dumps(current_snapshot), change_summary=f"Auto-backup before restoring to version {version.version_number}", created_by_id=current_user.id))
    try:
        restore_data = json.loads(version.snapshot_data)
        for key, value in restore_data.items():
            if hasattr(pv, key): setattr(pv, key, value)
    except Exception: raise HTTPException(status_code=500, detail="Invalid snapshot data")
    await db.commit()
    await db.refresh(pv)
    return {"message": f"Successfully restored to version {version.version_number}"}


@router.get("/{pv_id}/onlyoffice/config")
async def get_onlyoffice_config(pv_id: str, language: str = "fr", db: AsyncSession = Depends(deps.get_db), current_user: UserModel = Depends(deps.get_current_user)) -> Any:
    stmt = select(PVModel).where(PVModel.id == pv_id, PVModel.client_id == current_user.client_id)
    pv = (await db.execute(stmt)).scalars().first()
    if not pv: raise HTTPException(status_code=404, detail="PV not found")
    docx_service = DOCXService(db)
    local_path = await docx_service.generate_pv_docx(pv_id, current_user.client_id, language=language)
    file_key = f"tmp_edits/{pv_id}/{os.path.basename(local_path)}"
    s3 = boto3.client("s3", endpoint_url=settings.S3_ENDPOINT, aws_access_key_id=settings.S3_ACCESS_KEY, aws_secret_access_key=settings.S3_SECRET_KEY)
    with open(local_path, "rb") as f: s3.upload_fileobj(f, settings.S3_BUCKET_NAME, file_key)
    download_url = f"{settings.PUBLIC_BACKEND_URL}/api/v1/pv/{pv_id}/onlyoffice/download?file_key={file_key}"
    callback_url = f"{settings.PUBLIC_BACKEND_URL}/api/v1/pv/{pv_id}/onlyoffice/callback"
    oo_lang = "ar-SA" if (language == "ar") else language
    config = {
        "document": {"fileType": "docx", "key": f"{pv_id}_{int(datetime.now(timezone.utc).timestamp())}", "title": f"PV_{pv.title}.docx", "url": download_url, "permissions": {"edit": True, "download": True}},
        "editorConfig": {"callbackUrl": callback_url, "user": {"id": current_user.id, "name": current_user.full_name or current_user.email}, "lang": oo_lang, "customization": {"forcesave": True, "onlyOfficeUrl": settings.ONLYOFFICE_URL}}
    }
    config["token"] = jwt.encode(config, settings.ONLYOFFICE_SECRET, algorithm="HS256")
    return config


@router.get("/{pv_id}/onlyoffice/download")
async def onlyoffice_download(pv_id: str, file_key: str) -> Any:
    s3 = boto3.client("s3", endpoint_url=settings.S3_ENDPOINT, aws_access_key_id=settings.S3_ACCESS_KEY, aws_secret_access_key=settings.S3_SECRET_KEY)
    try:
        response = s3.get_object(Bucket=settings.S3_BUCKET_NAME, Key=file_key)
        return StreamingResponse(response['Body'].iter_chunks(), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    except Exception: raise HTTPException(status_code=404, detail="File not found")


@router.post("/{pv_id}/onlyoffice/callback")
async def onlyoffice_callback(pv_id: str, data: dict, request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(deps.get_db)) -> Any:
    auth_header = request.headers.get("Authorization")
    token = auth_header.split(" ")[1] if (auth_header and auth_header.startswith("Bearer ")) else data.get("token", "")
    try:
        decoded = jwt.decode(token, settings.ONLYOFFICE_SECRET, algorithms=["HS256"])
        if "payload" in decoded: data = decoded["payload"]
    except JWTError: return {"error": 1}
    
    status = data.get("status")
    logger.info(f"OnlyOffice callback for PV {pv_id} with status {status}")
    
    if status in [2, 6]:  # 2: Ready for saving, 6: Forcesave
        download_url = data.get("url")
        if not download_url: return {"error": 0}
        
        # Internal network mapping for Docker
        if download_url.startswith(settings.ONLYOFFICE_URL): 
            download_url = download_url.replace(settings.ONLYOFFICE_URL, "http://onlyoffice:80")
        elif "localhost:8080" in download_url: 
            download_url = download_url.replace("localhost:8080", "onlyoffice:80")
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(download_url)
            if resp.status_code != 200: return {"error": 1}
            content = resp.content
            
        # Get PV object
        pv_stmt = select(PVModel).where(PVModel.id == pv_id)
        pv = (await db.execute(pv_stmt)).scalars().first()
        if not pv: return {"error": 1}
        
        docx_key = f"pv_exports/{pv_id}/edited_document.docx"
        pdf_key = f"pv_exports/{pv_id}/final_document.pdf"
        s3 = boto3.client("s3", endpoint_url=settings.S3_ENDPOINT, aws_access_key_id=settings.S3_ACCESS_KEY, aws_secret_access_key=settings.S3_SECRET_KEY)
        
        # 1. Update DOCX in S3
        s3.put_object(Bucket=settings.S3_BUCKET_NAME, Key=docx_key, Body=content)
        
        # 2. Synchronous Sync-State: Set Redis conversion key BEFORE responding to OnlyOffice
        # This ensures download_pv_pdf immediately sees the "in-progress" state.
        status_key = f"pdf_converting_{pv_id}"
        redis_client.set(status_key, "true", ex=300)
        
        # 3. Cache-Busting: Delete old PDF to force a wait in the download endpoint
        try: 
            s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=pdf_key)
            logger.info(f"Old PDF deleted for PV {pv_id} to ensure fresh conversion")
        except Exception:
            pass
        
        # 4. Versioning (ISO 27001)
        v_stmt = select(PVVersionModel).where(PVVersionModel.pv_id == pv_id).order_by(desc(PVVersionModel.version_number))
        latest_v = (await db.execute(v_stmt)).scalars().first()
        next_v = latest_v.version_number + 1 if latest_v else 1
        
        change_msg = "Edited via OnlyOffice Online (Forcesave)" if status == 6 else "Edited via OnlyOffice Online (Final Save)"
        db.add(PVVersionModel(
            id=str(uuid.uuid4()), 
            pv_id=pv.id, 
            version_number=next_v, 
            snapshot_data=json.dumps({"title": pv.title, "s3_path": docx_key, "edited_online": True, "callback_status": status}), 
            change_summary=change_msg, 
            created_by_id=data.get("users", ["system"])[0]
        ))
        await db.commit()
        
        # 5. Trigger Background PDF Conversion
        background_tasks.add_task(run_pdf_conversion, pv_id, docx_key, pdf_key)
        
    elif status in [3, 7]: # Error saving or force saving
        logger.error(f"OnlyOffice callback error for PV {pv_id}: status {status}")
        redis_client.delete(f"pdf_converting_{pv_id}")
        
    return {"error": 0}

