"""샌드박스(가상 데이터) 파일 생성: lists/*.csv (Lists '새 목록 › CSV에서' 용), sandbox/P3_AutomationHost.xlsx
실행: python3 tools/make_sandbox_files.py   (openpyxl 없으면 xlsx 생략)
CSV 머리글은 '내부 이름'이다 — CSV로 목록을 만들면 첫 생성 시 이 이름이 내부 이름이 되고, 표시 이름은 나중에 한글로 바꾼다.
모든 사람·메일·업무 내용은 가상이다.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT.parent / "automation_assets" / "sample_data"
ME = "seoyeon.han@example.com"

ROWS = {
    "ActionItems": [
        {"Title": "[가상] PLT-B 11월 CAPA 확인", "Owner": ME, "DueDate": "2026-10-22", "Status": "진행중", "ActionType": "실행", "Priority": "높음", "Source": "회의"},
        {"Title": "[가상] 해외-1 이월 수량 안내", "Owner": ME, "DueDate": "2026-10-26", "Status": "미착수", "ActionType": "실행", "Priority": "보통", "Source": "회의"},
        {"Title": "[가상] 구매팀 포장재 단가 회신", "Owner": ME, "DueDate": "2026-10-21", "Status": "진행중", "ActionType": "회신대기", "Priority": "보통", "Source": "이메일"},
        {"Title": "[가상] 12월 계획 초안", "Owner": ME, "DueDate": "2026-11-05", "Status": "미착수", "ActionType": "실행", "Priority": "보통", "Source": "기타"},
    ],
    "DecisionLog": [
        {"Title": "[가상] 단산 SKU-MOCK-310 잔량 처리 방식", "DecisionText": "잔량 판촉 소진 vs 폐기 결정 필요", "Status": "결정요청", "Decider": ME, "RequestedAt": "2026-10-20"},
        {"Title": "[가상] 10월 생산 동결 구간 2주 유지", "DecisionText": "Frozen fence 2주 유지", "Status": "확정", "Decider": ME, "DecidedAt": "2026-10-19"},
    ],
    "TeamRoster": [{"Title": p["name"], "Email": p["email"], "Aliases": "; ".join(p.get("aliases", []))}
                   for p in json.loads((SAMPLES / "roster.json").read_text(encoding="utf-8"))],
    "Holidays": [{"Title": "[샘플-회사 달력으로 교체] 한글날", "HolidayDate": "2026-10-09"},
                 {"Title": "[샘플-회사 달력으로 교체] 성탄절", "HolidayDate": "2026-12-25"}],
    "FactorySenders": [{"Title": "[가상] A공장", "PlantCode": "PLT-A", "SenderPattern": "@plta.example.com"},
                       {"Title": "[가상] 해외-1 법인", "PlantCode": "OVS-1", "SenderPattern": "planner@ovs1.example.com"}],
    "FactoryInbox": [],
    "MeetingIntake": [],
    "ActionCandidates": [],
    "FlowErrorLog": [],
}


def main():
    schema = json.loads((ROOT / "lists/lists_schema.json").read_text(encoding="utf-8"))
    for lst in schema["lists"]:
        cols = [c["internalName"] for c in lst["columns"]]
        with (ROOT / "lists" / f"{lst['name']}.csv").open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for r in ROWS.get(lst["name"], []):
                unknown = set(r) - set(cols)
                assert not unknown, (lst["name"], unknown)
                w.writerow([r.get(c, "") for c in cols])
        print("wrote lists/" + lst["name"] + ".csv")
    try:
        from openpyxl import Workbook
    except ImportError:
        print("openpyxl 없음: 호스트 통합 문서 생략(빈 Excel 파일을 직접 만들어도 됨)")
        return
    (ROOT / "sandbox").mkdir(exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "README"
    for line in ["P3_AutomationHost.xlsx — Office Scripts 계산 호스트(가상)",
                 "Power Automate 'Run script from SharePoint library'가 이 파일을 대상으로 스크립트를 실행한다.",
                 "스크립트(BuildDailyBrief·BuildReminderDigest·GuardExtraction)는 이 파일의 내용을 읽거나 바꾸지 않는다.",
                 "업무 데이터를 이 파일에 넣지 말 것. 삭제·이동하면 아침 브리핑·리마인더·AI 검증 흐름이 실패한다."]:
        ws.append([line])
    wb.save(ROOT / "sandbox/P3_AutomationHost.xlsx")
    print("wrote sandbox/P3_AutomationHost.xlsx")


def smoke():
    """테넌트에서 스크립트를 처음 실행할 때 쓸 입력값과, 로컬에서 같은 입력으로 얻은 기대 결과를 저장."""
    import subprocess
    t = (SAMPLES / "mock_transcript.txt").read_text(encoding="utf-8")
    cases = {
        "BuildDailyBrief": {"meEmail": ME, "todayKst": "2026-10-26",
                            "eventsJson": json.dumps([{"subject": "[가상] 주간 공급 조정 회의", "start": "2026-10-26T00:30:00.0000000",
                                                       "end": "2026-10-26T01:30:00.0000000", "isAllDay": False, "organizer": ME}], ensure_ascii=False),
                            "actionsJson": json.dumps([{"ActionID": "ACT-2026-00001", "Title": "[가상] PLT-B 11월 CAPA 확인", "DueDate": "2026-10-22",
                                                        "Status": {"Value": "진행중"}, "ActionType": {"Value": "실행"}, "Owner": {"Email": ME}}], ensure_ascii=False),
                            "decisionsJson": "[]", "requestsJson": "[]", "holidaysJson": "[]", "linksJson": "{}"},
        "GuardExtraction": {"transcript": t, "rosterJson": (SAMPLES / "roster.json").read_text(encoding="utf-8"),
                            "extractionJson": (SAMPLES / "extraction_good.json").read_text(encoding="utf-8"), "meetingDate": "2026-10-26"},
        "BuildReminderDigest": {"todayKst": "2026-10-26", "holidaysJson": "[]", "viewUrl": "",
                                "actionsJson": json.dumps([{"ID": 1, "ActionID": "ACT-2026-00001", "Title": "[가상] 초과 건", "DueDate": "2026-10-23",
                                                            "Status": {"Value": "미착수"}, "Owner": {"Email": ME}}], ensure_ascii=False)},
    }
    cases["ParseDueHint"] = {"text": "[긴급] PLT-B 11월 CAPA 확인 요청 내일까지 회신 부탁드립니다", "receivedKst": "2026-10-26",
                             "holidaysJson": "[]"}
    cases["BuildMeetingPrep"] = {"meEmail": ME, "todayKst": "2026-10-26", "holidaysJson": "[]",
                                 "eventsJson": json.dumps([{"subject": "[가상] 주간 공급 조정", "start": "2026-10-27T00:30:00.0000000",
                                                            "end": "2026-10-27T01:30:00.0000000", "organizer": ME,
                                                            "requiredAttendees": "doyun.park@example.com;"}], ensure_ascii=False),
                                 "actionsJson": json.dumps([{"ActionID": "ACT-2026-00002", "Title": "[가상] 이월 수량 안내", "DueDate": "2026-10-23",
                                                             "Status": {"Value": "미착수"}, "Owner": {"Email": "doyun.park@example.com"}}], ensure_ascii=False),
                                 "decisionsJson": "[]"}
    cases["BuildWeeklyDigest"] = {"meEmail": ME, "todayKst": "2026-10-30", "decisionsJson": "[]",
                                  "actionsJson": json.dumps([{"ActionID": "ACT-2026-00001", "Title": "[가상] 완료 건", "Status": {"Value": "완료"},
                                                              "CompletedAt": "2026-10-28T05:00:00Z", "Created": "2026-10-26T00:00:00Z",
                                                              "Owner": {"Email": ME}}], ensure_ascii=False),
                                  "inboxJson": json.dumps([{"PlantCode": "PLT-A", "FileCount": 2, "ReceivedAt": "2026-10-27T01:00:00Z"}])}
    out = ROOT / "sandbox" / "smoke"
    out.mkdir(parents=True, exist_ok=True)
    for name, params in cases.items():
        r = subprocess.run(["node", str(ROOT / "emulator/run_office_script.js")], input=json.dumps({"script": name, "params": params}),
                           capture_output=True, text=True, check=True)
        res = json.loads(r.stdout)
        assert res["ok"], res
        (out / f"{name}.params.json").write_text(json.dumps(params, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out / f"{name}.expected.json").write_text(json.dumps(res["result"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("wrote sandbox/smoke/" + name)


if __name__ == "__main__":
    main()
    smoke()
