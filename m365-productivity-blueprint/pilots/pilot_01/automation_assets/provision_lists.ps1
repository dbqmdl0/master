<#
.SYNOPSIS
  Pilot 01 Lists(RequestHub, RequestLog, SLAPolicy, Holidays, FlowErrorLog)를 lists_schema.json대로 만든다.

.DESCRIPTION
  Scenario B 전용(팀 사이트 소유자 권한 + 조직이 승인한 PnP용 Entra ID 앱 등록 필요).
  - 2024-09 이후 PnP 공용 멀티테넌트 앱이 제거되어, 조직 IT가 등록한 ClientId 가 반드시 필요하다.
  - 기본은 '미리보기(Dry-run)'다. 실제 생성은 -Apply 스위치를 명시해야 한다.
  - 이미 있는 목록·열은 건너뛴다(덮어쓰기·삭제 없음). 운영 중 목록에는 실행하지 말고 테스트 사이트에서 먼저 실행하라.
  - 비밀정보(비밀번호·토큰)를 이 파일에 넣지 마라. 대화형 로그인만 사용한다.
  - 이 스크립트는 작성 환경에 PowerShell이 없어 실행 검증되지 않았다. 테스트 사이트에서 Dry-run 출력부터 확인하라.

.EXAMPLE
  ./provision_lists.ps1 -SiteUrl https://contoso.sharepoint.com/sites/SCM-Test -ClientId <IT가 발급한 앱 ID>
  ./provision_lists.ps1 -SiteUrl https://contoso.sharepoint.com/sites/SCM-Test -ClientId <앱 ID> -Apply
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)] [string] $SiteUrl,
  [Parameter(Mandatory)] [string] $ClientId,
  [string] $SchemaPath = (Join-Path $PSScriptRoot 'lists_schema.json'),
  [switch] $Apply
)

$ErrorActionPreference = 'Stop'
$schema = Get-Content -Raw -Encoding UTF8 $SchemaPath | ConvertFrom-Json

function Esc([string] $s) { [System.Security.SecurityElement]::Escape($s) }

function Get-FieldXml($col) {
  $req = if ($col.required) { 'TRUE' } else { 'FALSE' }
  $common = "DisplayName='$(Esc $col.displayName)' Name='$($col.internalName)' StaticName='$($col.internalName)' Required='$req'"
  if ($col.indexed) { $common += " Indexed='TRUE'" }
  if ($col.unique) { $common += " EnforceUniqueValues='TRUE' Indexed='TRUE'" }
  if ($col.hidden) { $common += " ShowInNewForm='FALSE' ShowInEditForm='FALSE'" }
  switch ($col.type) {
    'Text'     { return "<Field Type='Text' $common MaxLength='255' />" }
    'Note'     { return "<Field Type='Note' $common NumLines='6' RichText='FALSE' />" }
    'Number'   {
      $min = if ($null -ne $col.min) { " Min='$($col.min)'" } else { '' }
      $def = if ($null -ne $col.default) { "<Default>$($col.default)</Default>" } else { '' }
      return "<Field Type='Number' $common$min>$def</Field>"
    }
    'DateTime' {
      $fmt = if ($col.dateOnly) { 'DateOnly' } else { 'DateTime' }
      return "<Field Type='DateTime' $common Format='$fmt' />"
    }
    'Boolean'  {
      $def = if ($col.default) { '1' } else { '0' }
      return "<Field Type='Boolean' $common><Default>$def</Default></Field>"
    }
    'User'     { return "<Field Type='User' $common UserSelectionMode='PeopleOnly' UserSelectionScope='0' />" }
    'Choice'   {
      $choices = ($col.choices | ForEach-Object { "<CHOICE>$(Esc $_)</CHOICE>" }) -join ''
      $def = if ($col.default) { "<Default>$(Esc $col.default)</Default>" } else { '' }
      return "<Field Type='Choice' $common Format='Dropdown'><CHOICES>$choices</CHOICES>$def</Field>"
    }
    default    { throw "지원하지 않는 형식: $($col.type) ($($col.internalName))" }
  }
}

if ($Apply) {
  Import-Module PnP.PowerShell -ErrorAction Stop
  Connect-PnPOnline -Url $SiteUrl -ClientId $ClientId -Interactive
} else {
  Write-Host "[DRY-RUN] 실제 변경 없음. 생성될 내용만 출력합니다. 적용하려면 -Apply" -ForegroundColor Yellow
}

foreach ($list in $schema.lists) {
  Write-Host "== 목록: $($list.name) ($($list.displayName))" -ForegroundColor Cyan
  $existing = $null
  if ($Apply) { $existing = Get-PnPList -Identity $list.name -ErrorAction SilentlyContinue }
  if (-not $existing) {
    Write-Host "  + 목록 생성"
    if ($Apply) {
      New-PnPList -Title $list.name -Template GenericList -EnableVersioning | Out-Null
      Set-PnPList -Identity $list.name -Title $list.displayName | Out-Null  # URL은 영문 유지, 표시 이름만 한글
    }
  } else {
    Write-Host "  = 이미 존재 → 열만 점검"
  }
  foreach ($col in $list.columns) {
    if ($col.internalName -eq 'Title') {
      Write-Host "  ~ Title 표시 이름 → $($col.displayName)"
      if ($Apply) { Set-PnPField -List $list.name -Identity Title -Values @{ Title = $col.displayName } | Out-Null }
      continue
    }
    $field = $null
    if ($Apply) { $field = Get-PnPField -List $list.name -Identity $col.internalName -ErrorAction SilentlyContinue }
    if ($field) { Write-Host "  = 열 존재: $($col.internalName)"; continue }
    $xml = Get-FieldXml $col
    Write-Host "  + 열: $($col.internalName) [$($col.type)]"
    Write-Verbose $xml
    if ($Apply) { Add-PnPFieldFromXml -List $list.name -FieldXml $xml | Out-Null }
  }
}
Write-Host "완료. 보기(View)·권한·열 서식은 implementation_guide.md 4장 절차로 화면에서 설정합니다." -ForegroundColor Green
