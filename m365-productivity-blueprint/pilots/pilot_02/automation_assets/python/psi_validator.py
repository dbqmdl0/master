"""Pilot 02 데이터 계약 검증기 — Python 버전 (로컬 일괄 검증 / 교차 검증용)

Office Scripts(ValidateSubmission.ts)와 같은 규칙(E01~E08, W01~W02)을 data_contract.json에서 읽어 적용한다.
용도
  1) Power Automate 없이(Scenario A-lite) 공장 제출 CSV/Excel 내보내기를 PC에서 일괄 검증
  2) Office Scripts 결과와 교차 검증(같은 입력 → 같은 오류 코드)
실행: python3 psi_validator.py <제출.csv> --week 2026-W44 --plant PLT-A --skus SKU-1,SKU-2
표준 라이브러리만 사용(회사 PC 추가 설치 불필요). 외부 전송 없음.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

CONTRACT_PATH = Path(__file__).resolve().parent.parent / "data_contract.json"


def load_contract(path: Path = CONTRACT_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _blank(v) -> bool:
    return v is None or str(v).strip() == ""


def _num(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip()
    return float(s) if re.fullmatch(r"-?\d+(\.\d+)?", s) else None


def validate(header: list[str], body: list[list], expected_week: str, plant: str,
             valid_skus: list[str], contract: dict | None = None) -> dict:
    c = contract or load_contract()
    cols = [x["name"] for x in c["columns"]]
    required = [x["name"] for x in c["columns"] if x["required"]]
    numeric = [x["name"] for x in c["columns"] if x["type"] == "number"]
    non_negative = [x["name"] for x in c["columns"] if x["type"] == "number" and x.get("min") == 0]
    issues: list[dict] = []

    def add(code, sev, row, col, msg):
        issues.append({"code": code, "severity": sev, "row": row, "column": col, "message": msg})

    if not valid_skus:
        add("E05", "Error", 0, "SKU", "SKU 마스터 목록 없음")
    if not re.fullmatch(r"\d{4}-W\d{2}", expected_week):
        add("E03", "Error", 0, "Week", f"제출 대상 주차 형식 오류: {expected_week}")
    idx = {h.strip(): i for i, h in enumerate(header)}
    missing = [x for x in required if x not in idx]
    if missing:
        add("E01", "Error", 0, ",".join(missing), "필수 열 누락")
        return _result(issues, 0, [])

    sku_set = set(valid_skus)
    seen: dict[str, int] = {}
    rows_out: list[list] = []
    data_row = 0
    for raw in body:
        if all(_blank(v) for v in raw):
            continue
        data_row += 1
        get = lambda k: raw[idx[k]] if k in idx and idx[k] < len(raw) else ""  # noqa: E731
        start_errors = sum(1 for i in issues if i["severity"] == "Error")
        for k in required:
            if _blank(get(k)):
                add("E02", "Error", data_row, k, f"필수 값 공란: {k}")
        week, pl, sku, line = (str(get(k)).strip() for k in ("Week", "PlantCode", "SKU", "LineCode"))
        if week and week != expected_week:
            add("E03", "Error", data_row, "Week", f"{week} ≠ {expected_week}")
        if pl and pl != plant:
            add("E04", "Error", data_row, "PlantCode", f"{pl} ≠ {plant}")
        if sku and sku_set and sku not in sku_set:
            add("E05", "Error", data_row, "SKU", f"마스터에 없는 SKU: {sku}")
        n = {}
        for k in numeric:
            v = get(k)
            if _blank(v):
                n[k] = 0.0
                continue
            x = _num(v)
            if x is None:
                add("E06", "Error", data_row, k, f"숫자가 아님: {v}")
                n[k] = 0.0
                continue
            if k in non_negative and x < 0:
                add("E06", "Error", data_row, k, f"음수 불가: {x}")
            n[k] = x
        key = f"{week}|{pl}|{sku}|{line}"
        if key in seen:
            add("E07", "Error", data_row, "SKU", f"중복 행({seen[key]}행)")
        else:
            seen[key] = data_row
        inflow = n["BeginInv"] + n["Production"] + n["Receipt"]
        diff = inflow - n["Shipment"] + n["Adjustment"] - n["EndInv"]
        if abs(diff) > max(1.0, inflow * 0.001):
            add("E08", "Error", data_row, "EndInv", f"PSI 수지 불일치: {diff:.2f}")
        remark = "" if _blank(get("Remark")) else str(get("Remark")).strip()
        if n["Adjustment"] != 0 and not remark:
            add("W01", "Warning", data_row, "Remark", "재고조정 사유 없음")
        if n["AvailHours"] <= 0 or n["RunHours"] > n["AvailHours"]:
            add("W02", "Warning", data_row, "RunHours", "가동시간 > 가용시간")
        if sum(1 for i in issues if i["severity"] == "Error") == start_errors:
            rows_out.append([week, pl, sku, line] + [n[k] for k in cols[4:13]] + [remark])
    if data_row == 0:
        add("E02", "Error", 0, "", "데이터 행이 없습니다")
    return _result(issues, data_row, rows_out)


def _result(issues, row_count, rows):
    errors = sum(1 for i in issues if i["severity"] == "Error")
    return {"ok": errors == 0, "rowCount": row_count, "errorCount": errors,
            "warningCount": len(issues) - errors, "issues": issues, "rows": rows if errors == 0 else []}


def read_csv(path: Path) -> tuple[list[str], list[list]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        data = list(csv.reader(f))
    return data[0], data[1:]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="공장 주간 제출 데이터 계약 검증")
    ap.add_argument("file", type=Path)
    ap.add_argument("--week", required=True)
    ap.add_argument("--plant", required=True)
    ap.add_argument("--skus", required=True, help="쉼표 구분 SKU 목록 또는 @파일경로(한 줄에 1개)")
    a = ap.parse_args(argv)
    skus = (Path(a.skus[1:]).read_text(encoding="utf-8").split() if a.skus.startswith("@")
            else [s.strip() for s in a.skus.split(",") if s.strip()])
    header, body = read_csv(a.file)
    r = validate(header, body, a.week, a.plant, skus)
    print(json.dumps({k: v for k, v in r.items() if k != "rows"}, ensure_ascii=False, indent=2))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
