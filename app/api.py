from datetime import datetime
import io
import re
from urllib.parse import urlparse

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from .config import BOT_NAME, ADMIN_CONTACT
from .db import get_session
from .models import Dataset, Record, CryptoInvoice, User, WalletTransaction
from .init_db import init_db

app = FastAPI(title="CYCLONE ULP SEARCHER API")

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.I)


@app.on_event("startup")
def startup():
    init_db()


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    return str(value).replace("\x00", "").strip() or None


def _truncate(value: str | None, limit: int) -> str | None:
    value = _clean_text(value)
    if value is None:
        return None
    return value[:limit]


def _detect_domain(value: str) -> str | None:
    value = _clean_text(value)
    if not value:
        return None

    if value.startswith(("http://", "https://")):
        try:
            parsed = urlparse(value)
            host = (parsed.hostname or "").strip().lower()
            return _truncate(host, 255)
        except Exception:
            return None

    if EMAIL_RE.match(value):
        return _truncate(value.split("@", 1)[1].lower(), 255)

    if "." in value and " " not in value and "/" not in value and ":" not in value:
        return _truncate(value.lower(), 255)

    return None


def _extract_email(value: str) -> str | None:
    value = _clean_text(value)
    if value and EMAIL_RE.match(value):
        return _truncate(value.lower(), 255)
    return None


def _extract_url(value: str) -> str | None:
    value = _clean_text(value)
    if value and value.startswith(("http://", "https://")):
        return value
    return None


def _parse_line_to_record(line: str) -> dict | None:
    line = _clean_text(line)
    if not line:
        return None

    return {
        "record_type": "generic",
        "domain": _detect_domain(line),
        "email": _extract_email(line),
        "username": None,
        "phone": None,
        "company": None,
        "country": None,
        "url": _extract_url(line),
        "notes": line,
    }


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="upload.html",
        context={
            "request": request,
            "bot_name": BOT_NAME,
            "admin_contact": ADMIN_CONTACT,
            "message": "Open /ui to upload files.",
            "error": None,
            "results": None,
        },
    )


@app.get("/ui", response_class=HTMLResponse)
async def ui_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="upload.html",
        context={
            "request": request,
            "bot_name": BOT_NAME,
            "admin_contact": ADMIN_CONTACT,
            "message": None,
            "error": None,
            "results": None,
        },
    )


@app.post("/ui/upload", response_class=HTMLResponse)
async def ui_upload(
    request: Request,
    dataset_name: str = Form(...),
    uploaded_by_telegram_id: str | None = Form(None),
    files: list[UploadFile] = File(...),
):
    db = get_session()

    try:
        results = []
        uploader_id = (
            int(uploaded_by_telegram_id)
            if uploaded_by_telegram_id and uploaded_by_telegram_id.isdigit()
            else None
        )

        for up in files:
            dataset = Dataset(
                name=_truncate(up.filename if len(files) == 1 else f"{dataset_name} - {up.filename}", 255) or "upload",
                source_type="upload",
                uploaded_by_telegram_id=uploader_id,
                record_count=0,
                skipped_count=0,
                notes=None,
            )
            db.add(dataset)
            db.flush()

            inserted = 0
            skipped = 0
            batch = []

            wrapper = io.TextIOWrapper(
                up.file,
                encoding="utf-8",
                errors="ignore",
                newline=None,
            )

            for raw_line in wrapper:
                parsed = _parse_line_to_record(raw_line)

                if not parsed:
                    skipped += 1
                    continue

                batch.append(
                    Record(
                        dataset_id=dataset.id,
                        record_type=parsed["record_type"],
                        domain=parsed["domain"],
                        email=parsed["email"],
                        username=parsed["username"],
                        phone=parsed["phone"],
                        company=parsed["company"],
                        country=parsed["country"],
                        url=parsed["url"],
                        notes=parsed["notes"],
                        source_name=_truncate(up.filename, 255),
                        source_type="upload",
                    )
                )
                inserted += 1

                if len(batch) >= 1000:
                    db.add_all(batch)
                    db.flush()
                    batch.clear()

            if batch:
                db.add_all(batch)
                db.flush()

            dataset.record_count = inserted
            dataset.skipped_count = skipped

            results.append(
                {
                    "file": up.filename,
                    "rows_inserted": inserted,
                    "rows_skipped": skipped,
                    "dataset_id": dataset.id,
                }
            )

        db.commit()

        return templates.TemplateResponse(
            request=request,
            name="upload.html",
            context={
                "request": request,
                "bot_name": BOT_NAME,
                "admin_contact": ADMIN_CONTACT,
                "message": "Upload completed successfully.",
                "error": None,
                "results": results,
            },
        )

    except Exception as e:
        db.rollback()

        return templates.TemplateResponse(
            request=request,
            name="upload.html",
            context={
                "request": request,
                "bot_name": BOT_NAME,
                "admin_contact": ADMIN_CONTACT,
                "message": None,
                "error": str(e),
                "results": None,
            },
            status_code=500,
        )

    finally:
        db.close()
