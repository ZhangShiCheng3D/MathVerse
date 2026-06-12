"""Ownership enforcement for DeepTutor server-ID'd resources (see models.DtResource).

The reusable C2 tenancy mechanism for domains where DeepTutor assigns the id
(notebook/book/…): record (user, domain, dt_id) on create, then filter lists and
gate every id-based op by ownership so users never see or touch each other's data.
"""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.all import DtResource


def record(db: Session, user_id: str, domain: str, dt_id: str, title: str = "") -> None:
    # Idempotent: a re-record (e.g. tutor reconnect to the same engine session)
    # is a no-op. The owns() pre-check covers the common case; the IntegrityError
    # catch covers a concurrent insert racing past it (check-then-insert isn't
    # atomic), so the shared db session never ends up poisoned mid-request.
    if owns(db, user_id, domain, dt_id):
        return
    db.add(DtResource(user_id=user_id, domain=domain, dt_id=dt_id, title=title))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def owned_ids(db: Session, user_id: str, domain: str) -> set[str]:
    rows = db.query(DtResource).filter(
        DtResource.user_id == user_id, DtResource.domain == domain
    ).all()
    return {r.dt_id for r in rows}


def owns(db: Session, user_id: str, domain: str, dt_id: str) -> bool:
    return db.query(DtResource).filter(
        DtResource.user_id == user_id,
        DtResource.domain == domain,
        DtResource.dt_id == dt_id,
    ).first() is not None


def release(db: Session, user_id: str, domain: str, dt_id: str) -> None:
    db.query(DtResource).filter(
        DtResource.user_id == user_id,
        DtResource.domain == domain,
        DtResource.dt_id == dt_id,
    ).delete()
    db.commit()
