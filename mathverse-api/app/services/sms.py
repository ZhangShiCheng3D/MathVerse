"""Phone + SMS one-time-code login.

When `sms_enabled` is False the provider send is a no-op and the code is
surfaced to the caller (dev mode), so the whole login flow is testable
without a real SMS account — the same deferred-credentials pattern as WeChat.
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.models.all import SmsCode

logger = logging.getLogger(__name__)


def _utc(dt: datetime) -> datetime:
    # SQLite reads timestamps back naive; normalize before comparing.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def can_resend(db, phone: str) -> bool:
    last = db.query(SmsCode).filter(
        SmsCode.phone == phone
    ).order_by(SmsCode.created_at.desc()).first()
    if last is None or last.created_at is None:
        return True
    return _utc(last.created_at) + timedelta(
        seconds=settings.sms_resend_interval
    ) <= datetime.now(timezone.utc)


def generate_and_store(db, phone: str) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    # Send first: if the provider fails we raise before storing, so a failed
    # attempt does not leave a row that rate-limits the user's retry.
    _provider_send(phone, code)
    db.add(SmsCode(
        phone=phone,
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(
            seconds=settings.sms_code_ttl_seconds
        ),
    ))
    db.commit()
    return code


def verify(db, phone: str, code: str) -> bool:
    # Interim master code (SMS approval pending): accepts any phone with no real
    # code sent. Dev mode only — real SMS (sms_enabled=True) ignores it.
    if (not settings.sms_enabled
            and settings.sms_master_code
            and code == settings.sms_master_code):
        return True
    rec = db.query(SmsCode).filter(
        SmsCode.phone == phone,
        SmsCode.code == code,
        SmsCode.consumed == False,  # noqa: E712 — SQLAlchemy boolean column
    ).order_by(SmsCode.created_at.desc()).first()
    if rec is None or _utc(rec.expires_at) < datetime.now(timezone.utc):
        return False
    rec.consumed = True
    db.commit()
    return True


def _provider_send(phone: str, code: str) -> None:
    if not settings.sms_enabled:
        logger.info("SMS dev mode: code for %s is %s", phone, code)
        return
    if settings.sms_provider != "tencent":
        raise RuntimeError(f"Unsupported SMS provider: {settings.sms_provider}")
    _send_tencent(phone, code)


def _send_tencent(phone: str, code: str) -> None:
    # Lazy import: the Tencent SDK is only needed when SMS is actually enabled,
    # so dev mode and the test suite don't require the package installed.
    from tencentcloud.common import credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.sms.v20210111 import models, sms_client

    cred = credential.Credential(
        settings.tencent_sms_secret_id, settings.tencent_sms_secret_key
    )
    http_profile = HttpProfile()
    http_profile.endpoint = "sms.tencentcloudapi.com"
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client = sms_client.SmsClient(cred, settings.tencent_sms_region, client_profile)

    req = models.SendSmsRequest()
    req.PhoneNumberSet = [f"+86{phone}"]
    req.SmsSdkAppId = settings.tencent_sms_sdk_app_id
    req.SignName = settings.tencent_sms_sign
    req.TemplateId = settings.tencent_sms_template_id
    req.TemplateParamSet = [code]  # template's {1}

    resp = client.SendSms(req)
    status = resp.SendStatusSet[0] if resp.SendStatusSet else None
    if status is None or status.Code != "Ok":
        raise RuntimeError(
            f"Tencent SMS send failed: "
            f"{getattr(status, 'Code', '?')} {getattr(status, 'Message', '')}"
        )
