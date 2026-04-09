import csv
import io
import time

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..config import EXPORT_FETCH_LIMIT, RESULTS_PREVIEW_LIMIT
from ..models import Record, SearchLog


def normalize_query(value: str) -> str:
    return value.strip().lower()


def mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return "-"
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        masked = name[0] + "*"
    else:
        masked = name[:1] + "*" * max(1, len(name) - 2) + name[-1]
    return f"{masked}@{domain}"


def mask_phone(phone: str | None) -> str:
    if not phone:
        return "-"
    digits = str(phone)
    if len(digits) <= 4:
        return "*" * len(digits)
    return "*" * (len(digits) - 4) + digits[-4:]


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


def summarize_records(records):
    counts = {"domains": 0, "emails": 0, "usernames": 0, "phones": 0, "urls": 0, "companies": 0}
    for r in records:
        if r.domain:
            counts["domains"] += 1
        if r.email:
            counts["emails"] += 1
        if r.username:
            counts["usernames"] += 1
        if r.phone:
            counts["phones"] += 1
        if r.url:
            counts["urls"] += 1
        if r.company:
            counts["companies"] += 1
    return counts


def build_safe_txt_report(query: str, search_type: str, total: int, records):
    counts = summarize_records(records)
    lines = [
        "==============================",
        "CYCLONE ULP SEARCHER REPORT",
        "==============================",
        "",
        "[SEARCH]",
        f"query={query}",
        f"filter={search_type}",
        f"result_count={total}",
        "",
        "[CATEGORY_COUNTS]",
        f"domains={counts['domains']}",
        f"emails={counts['emails']}",
        f"usernames={counts['usernames']}",
        f"phones={counts['phones']}",
        f"urls={counts['urls']}",
        f"companies={counts['companies']}",
        "",
        "[MASKED_ROWS]",
        "",
    ]
    for i, r in enumerate(records, start=1):
        lines += [
            f"# row_{i}",
            f"domain={r.domain or '-'}",
            f"email={mask_email(r.email)}",
            f"username={r.username or '-'}",
            f"phone={mask_phone(r.phone)}",
            f"url={r.url or '-'}",
            f"company={r.company or '-'}",
            f"country={r.country or '-'}",
            f"source={r.source_name or 'upload'}",
            "",
        ]
    return "\n".join(lines)


def build_safe_csv(records):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["domain", "email_masked", "username", "phone_masked", "company", "country", "url", "source"])
    for r in records:
        writer.writerow([
            r.domain or "",
            mask_email(r.email),
            r.username or "",
            mask_phone(r.phone),
            r.company or "",
            r.country or "",
            r.url or "",
            r.source_name or "upload",
        ])
    return out.getvalue()


def log_search(db: Session, telegram_id: int, search_type: str, query: str, results_count: int, credits_used: int = 0, wallet_cents_used: int = 0):
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
