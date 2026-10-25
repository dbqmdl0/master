// Scenario A-lite: Power Automate 없이 Excel 데스크톱 Power Query로 공장 제출 파일을 결합·검증
// 사용: Excel > 데이터 > 데이터 가져오기 > 기타 원본에서 > 빈 쿼리 > 고급 편집기 > 아래 붙여넣기
// 변경할 값: SiteUrl, LibraryFolder, TargetWeek (TargetWeek는 '매개변수' 표로 빼면 매주 수정 불필요)
// 결과: 계약 열 + SourceFile + PSI_Diff + CheckFlag. 새로 고침(Ctrl+Alt+F5) 한 번으로 전 공장 결합.
let
    SiteUrl       = "https://<tenant>.sharepoint.com/sites/<SCM-site>",
    LibraryFolder = "/SCM_Submissions/",
    TargetWeek    = "2026-W44",
    ContractCols  = {"Week","PlantCode","SKU","LineCode","BeginInv","Production","Receipt","Shipment",
                     "Adjustment","EndInv","PlanNextWeek","RunHours","AvailHours","Remark"},
    NumberCols    = {"BeginInv","Production","Receipt","Shipment","Adjustment","EndInv","PlanNextWeek","RunHours","AvailHours"},

    Source   = SharePoint.Files(SiteUrl, [ApiVersion = 15]),
    Filtered = Table.SelectRows(Source, each
                   Text.Contains([Folder Path], LibraryFolder & TargetWeek & "/")
                   and Text.EndsWith(Text.Lower([Name]), ".xlsx")
                   and not Text.StartsWith([Name], "~$")),
    WithData = Table.AddColumn(Filtered, "Data", each
                   try Excel.Workbook([Content], true){[Item = "tblSubmit", Kind = "Table"]}[Data]
                   otherwise null),
    Loaded   = Table.SelectRows(WithData, each [Data] <> null),
    Missing  = Table.SelectRows(WithData, each [Data] = null),   // 표 없는 파일 → 별도 확인
    Slim     = Table.SelectColumns(Loaded, {"Name", "Data"}),
    Expanded = Table.ExpandTableColumn(Slim, "Data", ContractCols),
    Renamed  = Table.RenameColumns(Expanded, {{"Name", "SourceFile"}}),
    Typed    = Table.TransformColumnTypes(Renamed,
                   List.Transform(NumberCols, each {_, type number}), "en-US"),
    NonBlank = Table.SelectRows(Typed, each [SKU] <> null and [SKU] <> ""),
    WithDiff = Table.AddColumn(NonBlank, "PSI_Diff", each
                   (([BeginInv] ?? 0) + ([Production] ?? 0) + ([Receipt] ?? 0) - ([Shipment] ?? 0)
                    + ([Adjustment] ?? 0)) - ([EndInv] ?? 0), type number),
    WithFlag = Table.AddColumn(WithDiff, "CheckFlag", each
                   if [Week] <> TargetWeek then "E03 주차"
                   else if Number.Abs([PSI_Diff]) > List.Max({1, (([BeginInv] ?? 0) + ([Production] ?? 0) + ([Receipt] ?? 0)) * 0.001}) then "E08 PSI"
                   else if ([Adjustment] ?? 0) <> 0 and ([Remark] = null or [Remark] = "") then "W01 조정사유"
                   else if ([AvailHours] ?? 0) <= 0 or ([RunHours] ?? 0) > ([AvailHours] ?? 0) then "W02 가동시간"
                   else "OK", type text)
in
    WithFlag
// 한계: 숫자 변환 실패 셀은 Error 값으로 남는다(열 머리글의 오류 표시 확인). 중복(E07)·SKU 마스터(E05)는
//       이 쿼리를 SKU 표와 병합(Merge)하거나 피벗으로 확인. 자동 알림이 필요하면 Scenario B(Flow+Office Scripts)로 전환.
