import csv
import io
import time

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..config import EXPORT_FETCH_LIMIT, RESULTS_PREVIEW_LIMIT
from ..models import Record, SearchLog


def normalize_query(value: str) -> str:
    return value.strip().lower()


def _contains(expr, q: str):
    return func.lower(func.coalesce(expr, "")).like(f"%{q}%")


def _build_query(db: Session, search_type: str, query: str):
    q = normalize_query(query)
    raw = query.strip()

    if search_type == "domain":
        return db.query(Record).filter(
            or_(
                _contains(Record.domain, q),
                _contains(Record.email, q),
                _contains(Record.url, q),
                _contains(Record.notes, q),
                _contains(Record.company, q),
                _contains(Record.username, q),
            )
        )

    if search_type == "country":
        return db.query(Record).filter(
            or_(
                _contains(Record.country, q),
                _contains(Record.notes, q),
                _contains(Record.company, q),
                _contains(Record.domain, q),
                _contains(Record.url, q),
            )
        )

    return db.query(Record).filter(
        or_(
            _contains(Record.domain, q),
            _contains(Record.email, q),
            _contains(Record.username, q),
            Record.phone.like(f"%{raw}%"),
            _contains(Record.company, q),
            _contains(Record.url, q),
            _contains(Record.notes, q),
            _contains(Record.country, q),
        )
    )


def search_records(db: Session, search_type: str, query: str):
    start = time.perf_counter()
    db_query = _build_query(db, search_type, query)
    total = db_query.count()
    preview = db_query.limit(RESULTS_PREVIEW_LIMIT).all()
    elapsed = time.perf_counter() - start
    return {"total": total, "records": preview, "elapsed": elapsed}


def fetch_export_records(db: Session, search_type: str, query: str):
    return _build_query(db, search_type, query).limit(EXPORT_FETCH_LIMIT).all()


def _record_full_line(record: Record) -> str:
    if record.notes and record.notes.strip():
        return record.notes.strip()
    for value in [record.url, record.email, record.domain, record.username, record.phone, record.company]:
        if value and str(value).strip():
            return str(value).strip()
    return ""


def build_safe_txt_report(query: str, search_type: str, total: int, records):
    lines = []
    seen = set()

    for record in records:
        line = _record_full_line(record)
        if not line:
            continue
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)

    return "\n".join(lines)


def build_safe_csv(records):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["full_line"])

    seen = set()
    for record in records:
        line = _record_full_line(record)
        if not line:
            continue
        if line in seen:
            continue
        seen.add(line)
        writer.writerow([line])

    return out.getvalue()


def log_search(
    db: Session,
    telegram_id: int,
    search_type: str,
    query: str,
    results_count: int,
    credits_used: int = 0,
    wallet_cents_used: int = 0,
):
    db.add(
        SearchLog(
            telegram_id=telegram_id,
            search_type=search_type,
            query=query,
            results_count=results_count,
            credits_used=credits_used,
            wallet_cents_used=wallet_cents_used,
        )
    )
    db.commit()
