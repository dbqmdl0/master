"""테스트용 가상 테넌트 구성(모든 사람·메일·데이터는 가상)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "emulator"))
from fakes import Faults, FakeExcel, FakeOneDrive, FakeOutlook, FakeSharePoint, FakeTeams, FakeUsers  # noqa: E402
from runtime import Flow, Runtime  # noqa: E402

SITE = "https://contoso-my.sharepoint.com/personal/seoyeon_han_example_com"
ME = "seoyeon.han@example.com"
HOST = "/Documents/P3/P3_AutomationHost.xlsx"  # 본인 OneDrive 안 경로(Run script 'File')
SCRIPTS = "/Documents/Office Scripts"  # Run script가 스크립트를 찾는 OneDrive 기본 위치
DIRECTORY = {ME: "한서연", "doyun.park@example.com": "박도윤", "minjae.lee@example.com": "이민재",
             "haeun.choi@example.com": "최하은"}
SITE_MAP = {"{{SITE_URL}}": SITE, "{{ME}}": ME, "{{HOST_WORKBOOK}}": HOST, "{{SCRIPT_FOLDER}}": SCRIPTS,
            "{{VIEW_MY_ACTIONS}}": f"{SITE}/Lists/ActionItems/my.aspx",
            "{{VIEW_DECISION_QUEUE}}": f"{SITE}/Lists/DecisionLog/queue.aspx",
            "{{VIEW_CANDIDATES}}": f"{SITE}/Lists/ActionCandidates/pending.aspx", "{{NOTIFY_CHANNEL}}": "teams",
            "{{FACTORY_FOLDER}}": "/SCM_수신"}
KST = timezone(timedelta(hours=9))


class Clock:
    def __init__(self, kst: str):
        self.now = datetime.fromisoformat(kst).replace(tzinfo=KST).astimezone(timezone.utc)

    def __call__(self):
        return self.now

    def set_kst(self, kst: str):
        self.now = datetime.fromisoformat(kst).replace(tzinfo=KST).astimezone(timezone.utc)


class Env:
    def __init__(self, kst="2026-10-26T07:40:00", acl_override=None, flows=None, flow_paths=None, channel="teams"):
        self.clock = Clock(kst)
        self.faults = Faults()
        self.sp = FakeSharePoint(self.clock, self.faults, DIRECTORY)
        schema = json.loads((ROOT / "lists/lists_schema.json").read_text(encoding="utf-8"))
        for lst in schema["lists"]:
            acl = {ME: "edit"}
            acl.update((acl_override or {}).get(lst["name"], {}))
            acl = {k: v for k, v in acl.items() if v}
            self.sp.add_list(SITE, lst["name"], lst["columns"], acl)
        self.outlook = FakeOutlook(self.faults)
        self.teams = FakeTeams(self.faults, DIRECTORY)
        self.excel = FakeExcel(self.faults)
        for name in ("BuildDailyBrief", "BuildReminderDigest", "GuardExtraction", "ParseDueHint", "BuildMeetingPrep",
                     "BuildWeeklyDigest"):
            self.excel.add_file(f"{SCRIPTS}/{name}.osts", [ME])
        self.excel.add_file(HOST, [ME])
        self.users = FakeUsers(self.faults, DIRECTORY)
        self.onedrive = FakeOneDrive(self.faults)
        self.rt = Runtime(self.sp, self.outlook, self.teams, self.excel, self.users, self.clock, self.onedrive)
        paths = flow_paths or sorted((ROOT / "flows").glob("*.flow.json"))
        for p in paths:
            fl = Flow(Path(p), ME, {**SITE_MAP, "{{NOTIFY_CHANNEL}}": channel})
            # 기본은 B안 전체(P3P-*). A안(P3A-*)은 같은 트리거를 쓰므로 flows=[...] 로 명시할 때만 등록(실제로도 동시에 켜지 않음)
            if (flows is None and not fl.id.startswith("P3A")) or (flows is not None and fl.id in flows):
                self.rt.register(fl)
        # 시드 데이터(가상): 명부·휴무일
        for name, email, aliases in (("한서연", ME, "한 매니저"), ("박도윤", "doyun.park@example.com", ""),
                                     ("이민재", "minjae.lee@example.com", ""), ("최하은", "haeun.choi@example.com", "PLT-A 최하은")):
            self.sp.create(ME, SITE, "TeamRoster", {"Title": name, "Email": email, "Aliases": aliases})
        self.sp.create(ME, SITE, "Holidays", {"Title": "[샘플] 한글날", "HolidayDate": "2026-10-09"})
        self.sp.events.clear()

    # ---- 사람이 화면에서 하는 행동(같은 권한·검증·이벤트 경로)
    def ui_create(self, lst, fields, user=ME):
        item = self.sp.create(user, SITE, lst, fields)
        self.rt.drain()
        return item

    def ui_update(self, lst, item_id, fields, user=ME):
        item = self.sp.update(user, SITE, lst, item_id, fields, ui=True)
        self.rt.drain()
        return item

    def items(self, lst):
        return self.sp.items(SITE, lst)

    def flag_email(self, msg_id, subject="11월 증량 요청 건 확인 부탁드립니다", preview="해외-1 법인 11월 증량 1.2만 가능 여부",
                   due=None, folder="Inbox", parallel=0, categories=None, imid="auto", flag_status="flagged",
                   sender="doyun.park@example.com", received="2026-10-25T23:00:00Z", force_race=False):
        """imid='auto' 이면 msg_id 로 internetMessageId 를 만든다(폴더 이동 재현: 같은 imid + 다른 msg_id). None 이면 필드 없음."""
        if imid == "auto":
            imid = f"<{msg_id}@mail.example.com>" if msg_id else None
        body = {"id": msg_id, "subject": subject, "bodyPreview": preview, "from": sender,
                "webLink": f"https://outlook.office.com/mail/id/{msg_id}" if msg_id else None,
                "receivedDateTime": received, "categories": categories or [],
                "flag": {"flagStatus": flag_status, "dueDateTime": {"dateTime": due, "timeZone": "UTC"} if due else None}}
        if imid is not None:
            body["internetMessageId"] = imid
        out = {"body": body, "_folder": folder}
        fid = next((f.id for f in self.rt.flows if f.enabled and f.trigger["kind"] == "Outlook.WhenAnEmailIsFlaggedV4"
                    and f.trigger["inputs"]["folder"] == folder), None)
        if parallel:
            runs = self.rt.fire_parallel("Outlook.WhenAnEmailIsFlaggedV4", [out] * parallel, fid, force_race=force_race)
        else:
            runs = self.rt.fire("Outlook.WhenAnEmailIsFlaggedV4", out, fid)
        self.rt.drain()
        return runs

    def new_email(self, msg_id, sender, subject="[PLT-A] 주간 생산실적", attachments=None, received="2026-10-26T01:10:00Z"):
        """받은 편지함에 첨부 메일 도착(When a new email arrives (V3), 첨부 포함)."""
        body = {"id": msg_id, "from": sender, "subject": subject, "receivedDateTime": received, "hasAttachments": True,
                "attachments": [{"name": n, "contentBytes": "UEsDBAoAAAAAAA==", "contentType": "application/octet-stream"}
                                for n in (attachments or [])]}
        runs = self.rt.fire("Outlook.WhenANewEmailArrivesV3", {"body": body, "_folder": "Inbox"}, "P3P-F10")
        self.rt.drain()
        return runs[0]

    def select_message(self, msg_id, content, kind="액션", title="", owner="", due="", decision_id=""):
        out = {"body": {"cardOutputs": {"kind": kind, "title": title, "ownerEmail": owner, "dueDate": due,
                                        "decisionId": decision_id},
                        "messagePayload": {"id": msg_id, "body": {"content": content, "contentType": "html"},
                                           "from": {"user": {"displayName": "박도윤"}}},
                        "linkToMessage": f"https://teams.microsoft.com/l/message/19:abc/{msg_id}" if msg_id else None}}
        runs = self.rt.fire("Teams.ForASelectedMessage", out, "P3P-F5")
        self.rt.drain()
        return runs[0]

    def recurrence(self, fid):
        runs = self.rt.fire("Recurrence", {}, fid)
        self.rt.drain()
        return runs[0]

    def errors(self):
        return self.items("FlowErrorLog")
