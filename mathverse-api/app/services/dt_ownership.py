"""Ownership enforcement for DeepTutor server-ID'd resources (see models.DtResource).

The reusable C2 tenancy mechanism for domains where DeepTutor assigns the id
(notebook/book/…): record (user, domain, dt_id) on create, then filter lists and
gate every id-based op by ownership so users never see or touch each other's data.
"""
from sqlalchemy.orm import Session

from app.models.all import DtResource


def record(db: Session, user_id: str, domain: str, dt_id: str, title: str = "") -> None:
    db.add(DtResource(user_id=user_id, domain=domain, dt_id=dt_id, title=title))
    db.commit()


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
