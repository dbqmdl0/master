// 로컬 타입 검사 전용 최소 스텁. 실제 Office Scripts 런타임의 ExcelScript 네임스페이스 중
// 이 파일럿 스크립트가 쓰는 메서드만 공식 시그니처와 같은 형태로 선언했다. (Excel에 업로드하지 않음)
declare namespace ExcelScript {
  type CellValue = string | number | boolean;
  interface Range {
    getValues(): CellValue[][];
    setValues(values: CellValue[][]): void;
    getResizedRange(deltaRows: number, deltaColumns: number): Range;
    clear(applyTo?: string): void;
  }
  interface TableColumn {
    getRangeBetweenHeaderAndTotal(): Range;
  }
  interface Table {
    getHeaderRowRange(): Range;
    getRangeBetweenHeaderAndTotal(): Range;
    getRowCount(): number;
    getColumnByName(key: string): TableColumn;
    addRows(index?: number, values?: CellValue[][]): void;
    deleteRowsAt(index: number, count?: number): void;
  }
  interface Worksheet {
    getRange(address?: string): Range;
    getUsedRange(valuesOnly?: boolean): Range | undefined;
  }
  interface Workbook {
    getTable(key: string): Table | undefined;
    getWorksheet(name: string): Worksheet | undefined;
    addWorksheet(name?: string): Worksheet;
  }
}
