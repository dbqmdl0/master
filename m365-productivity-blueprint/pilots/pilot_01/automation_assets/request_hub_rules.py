"""Pilot 01 통합 업무요청 허브 — 업무 규칙 참조 구현(Reference Implementation).

Power Automate Flow에 들어갈 규칙(상태 전이, 영업일 SLA, 요청번호, 중복검사, 다이제스트, 에스컬레이션)을
같은 의미로 파이썬에 구현해 둔 것이다. 목적은 두 가지다.
1) 모의 데이터로 규칙을 미리 테스트해 Flow 구현 전에 오류를 잡는다.
2) Flow가 정상 동작하는지 운영 중 교차 검증(같은 입력 → 같은 결과)하는 기준으로 쓴다.

실제 M365 데이터에 접속하지 않는다. 표준 라이브러리만 사용.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

KST = timezone(timedelta(hours=9))
INTAKE_CUTOFF_HOUR_KST = 17  # 17시 이후 접수는 다음 영업일 접수로 간주

STATUSES = ["접수", "정보보완", "검토중", "승인대기", "진행중", "보류", "완료", "반려", "취소"]
CLOSED = {"완료", "반려", "취소"}

# 허용 상태 전이. Flow F2는 이 표에 없는 전이를 '규칙 위반'으로 기록하고 되돌리지 않고 담당자에게 알린다.
TRANSITIONS: dict[str, set[str]] = {
    "접수": {"정보보완", "검토중", "반려", "취소"},
    "정보보완": {"접수", "검토중", "취소"},
    "검토중": {"정보보완", "승인대기", "진행중", "보류", "반려"},
    "승인대기": {"진행중", "반려", "보류"},
    "진행중": {"완료", "보류", "정보보완"},
    "보류": {"검토중", "진행중", "취소"},
    "완료": {"진행중"},  # 재개(Re-open)만 허용, 이력에 남김
    "반려": set(),
    "취소": set(),
}

ESCALATE_AFTER_OVERDUE_BDAYS = 2
DUPLICATE_WINDOW_DAYS = 14
REPEATED_CHANGE_THRESHOLD = 3


def is_valid_transition(old: str, new: str) -> bool:
    if old == new:
        return True
    if old not in TRANSITIONS or new not in STATUSES:
        return False
    return new in TRANSITIONS[old]


def request_id(created_utc: datetime, item_id: int) -> str:
    """Flow 식: concat('REQ-', convertFromUtc(...,'Korea Standard Time','yyyy'), '-', formatNumber(ID,'00000'))"""
    year = created_utc.astimezone(KST).year
    return f"REQ-{year}-{item_id:05d}"


def is_business_day(d: date, holidays: set[date]) -> bool:
    return d.weekday() < 5 and d not in holidays


def next_business_day(d: date, holidays: set[date]) -> date:
    d = d + timedelta(days=1)
    while not is_business_day(d, holidays):
        d += timedelta(days=1)
    return d


def intake_date(created_utc: datetime, holidays: set[date]) -> date:
    """접수 기준일: KST 영업일 17시 이전이면 당일, 아니면 다음 영업일."""
    local = created_utc.astimezone(KST)
    d = local.date()
    if is_business_day(d, holidays) and local.hour < INTAKE_CUTOFF_HOUR_KST:
        return d
    return next_business_day(d, holidays)


def add_business_days(start: date, n: int, holidays: set[date]) -> date:
    """start(영업일) 기준 n 영업일 후. n=0이면 start. Flow에서는 Do until 루프로 동일 구현."""
    d = start
    added = 0
    while added < n:
        d += timedelta(days=1)
        if is_business_day(d, holidays):
            added += 1
    return d


def business_days_between(a: date, b: date, holidays: set[date]) -> int:
    """a 다음날부터 b까지의 영업일 수(b > a). b <= a 이면 0 이하의 음수 의미로 -(b..a) 반환."""
    if a == b:
        return 0
    sign = 1
    if b < a:
        a, b, sign = b, a, -1
    count = 0
    d = a
    while d < b:
        d += timedelta(days=1)
        if is_business_day(d, holidays):
            count += 1
    return sign * count


def sla_target(created_utc: datetime, sla_bdays: int, holidays: set[date]) -> date:
    return add_business_days(intake_date(created_utc, holidays), sla_bdays, holidays)


def sla_state(target: date, today: date, holidays: set[date], status: str) -> str:
    """'closed' | 'overdue' | 'due_soon'(1영업일 이내) | 'ok'"""
    if status in CLOSED:
        return "closed"
    if today > target:
        return "overdue"
    if business_days_between(today, target, holidays) <= 1:
        return "due_soon"
    return "ok"


def should_escalate(target: date, today: date, holidays: set[date], status: str) -> bool:
    if status in CLOSED or today <= target:
        return False
    return business_days_between(target, today, holidays) >= ESCALATE_AFTER_OVERDUE_BDAYS


def escalation_cutoff(today: date, holidays: set[date]) -> date:
    """F3에서 쓰는 단일 비교 기준일. SLA 목표일 <= 이 날짜이면 에스컬레이션.
    should_escalate()와 같은 결과를 내도록 설계(테스트로 동치 확인). Flow는 Do until로 날짜를 거꾸로 걸으며 계산."""
    d = today
    count = 0
    while True:
        if is_business_day(d, holidays):
            count += 1
            if count == ESCALATE_AFTER_OVERDUE_BDAYS:
                return d - timedelta(days=1)
        d -= timedelta(days=1)


def duplicate_key(request_type: str, product_code: str | None, plant: str | None,
                  requester_email: str, due_requested: date) -> str:
    """Flow 식: toLower(concat(RequestType,'|',trim(ProductCode),'|',Plant,'|',Requester/Email,'|',formatDateTime(DueDateRequested,'yyyy-MM-dd')))"""
    parts = [request_type, (product_code or "").strip(), plant or "", requester_email, due_requested.isoformat()]
    return "|".join(parts).lower()


@dataclass
class Request:
    item_id: int
    title: str
    request_type: str
    requester_email: str
    created_utc: datetime
    due_requested: date
    status: str = "접수"
    owner_email: str | None = None
    product_code: str | None = None
    plant: str | None = None
    sla_target: date | None = None
    due_committed: date | None = None
    change_count: int = 0
    log: list[dict] = field(default_factory=list)

    @property
    def dkey(self) -> str:
        return duplicate_key(self.request_type, self.product_code, self.plant,
                             self.requester_email, self.due_requested)


def find_duplicates(new: Request, existing: Iterable[Request]) -> list[Request]:
    """같은 중복검사키 + 미종료 + 14일 이내 생성 → 중복 의심(자동 병합하지 않고 담당자 확인)."""
    window = new.created_utc - timedelta(days=DUPLICATE_WINDOW_DAYS)
    return [r for r in existing
            if r.item_id != new.item_id and r.dkey == new.dkey
            and r.status not in CLOSED and r.created_utc >= window]


def change_commitment(req: Request, new_date: date, reason: str, actor: str, now_utc: datetime) -> list[str]:
    """약속일 변경 처리. 반환: 경고 목록. 사유 없는 변경은 거부."""
    if not reason or not reason.strip():
        raise ValueError("약속일 변경 사유가 필요합니다")
    warnings: list[str] = []
    old = req.due_committed
    req.due_committed = new_date
    if old is not None and old != new_date:
        req.change_count += 1
        req.log.append({"EventType": "약속일변경", "FromValue": old.isoformat(),
                        "ToValue": new_date.isoformat(), "Actor": actor,
                        "EventAt": now_utc.isoformat(), "Comment": reason})
        if req.change_count >= REPEATED_CHANGE_THRESHOLD:
            warnings.append("반복변경")
    if new_date > req.due_requested:
        warnings.append("희망일초과")
    return warnings


def apply_status_change(req: Request, new_status: str, actor: str, now_utc: datetime) -> bool:
    """상태 변경 적용. 허용되지 않은 전이면 False(이력에 '규칙위반' 기록)."""
    old = req.status
    if old == new_status:
        return True
    ok = is_valid_transition(old, new_status)
    req.log.append({"EventType": "상태변경", "FromValue": old, "ToValue": new_status,
                    "Actor": actor, "EventAt": now_utc.isoformat(),
                    "Comment": "" if ok else "규칙위반: 허용되지 않은 전이"})
    if ok:
        req.status = new_status
    return ok


def build_digest(requests: Iterable[Request], today: date, holidays: set[date]) -> dict[str, dict]:
    """F3 일일 SLA 다이제스트: 담당자별 1장(건별 알림 금지 → 알림 피로 방지)."""
    out: dict[str, dict] = {}
    for r in requests:
        if r.status in CLOSED or r.sla_target is None or not r.owner_email:
            continue
        state = sla_state(r.sla_target, today, holidays, r.status)
        if state not in ("overdue", "due_soon"):
            continue
        bucket = out.setdefault(r.owner_email, {"overdue": [], "due_soon": [], "escalate": []})
        bucket[state].append(r.item_id)
        if should_escalate(r.sla_target, today, holidays, r.status):
            bucket["escalate"].append(r.item_id)
    for b in out.values():
        for k in b:
            b[k].sort()
    return out


def lead_time_bdays(created_utc: datetime, closed_utc: datetime, holidays: set[date]) -> int:
    """KPI: 요청→완료 리드타임(영업일)."""
    start = intake_date(created_utc, holidays)
    end = closed_utc.astimezone(KST).date()
    return max(0, business_days_between(start, end, holidays))
