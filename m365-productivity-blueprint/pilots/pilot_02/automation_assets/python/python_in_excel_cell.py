# Python in Excel 셀(=PY)에 붙여넣는 검증 코드 — 데이터 계약 v1.0 핵심 규칙(E06·E07·E08·W01·W02)
# 전제: 통합 문서에 표 tblSubmit 존재. 결과는 오류 행만 담은 DataFrame(정상이면 빈 표).
# Python in Excel은 Microsoft 클라우드에서 실행되며 로컬 파일·인터넷에 접근하지 않는다(회사 정책 확인 후 사용).
import pandas as pd
df = xl("tblSubmit[#All]", headers=True)
num = ["BeginInv","Production","Receipt","Shipment","Adjustment","EndInv","PlanNextWeek","RunHours","AvailHours"]
df = df.dropna(how="all")
for c in num:
    df[c] = pd.to_numeric(df[c], errors="coerce")
issues = []
for i, r in df.iterrows():
    row = int(i) + 1
    bad_num = [c for c in num if pd.isna(r[c]) and c != "Adjustment"]
    if bad_num: issues.append((row, "E06", ",".join(bad_num)))
    inflow = (r["BeginInv"] or 0) + (r["Production"] or 0) + (r["Receipt"] or 0)
    diff = inflow - (r["Shipment"] or 0) + (0 if pd.isna(r["Adjustment"]) else r["Adjustment"]) - (r["EndInv"] or 0)
    if abs(diff) > max(1, inflow * 0.001): issues.append((row, "E08", f"PSI 차이 {diff:.1f}"))
    if (not pd.isna(r["Adjustment"])) and r["Adjustment"] != 0 and (pd.isna(r["Remark"]) or str(r["Remark"]).strip() == ""):
        issues.append((row, "W01", "조정 사유 없음"))
    if (r["AvailHours"] or 0) <= 0 or (r["RunHours"] or 0) > (r["AvailHours"] or 0):
        issues.append((row, "W02", "가동>가용"))
dup = df[df.duplicated(subset=["Week","PlantCode","SKU","LineCode"], keep="first")]
issues += [(int(i) + 1, "E07", "중복 키") for i in dup.index]
pd.DataFrame(issues, columns=["행", "코드", "내용"]).sort_values(["행", "코드"])
