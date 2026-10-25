// ExcelScript 최소 모의 객체. 스크립트가 쓰는 메서드만 구현한다(테스트 전용).
"use strict";

class MockRange {
  constructor(getter, setter) { this._get = getter; this._set = setter; }
  getValues() { return this._get().map(r => r.slice()); }
  setValues(v) { if (!this._set) throw new Error("read-only range"); this._set(v); }
}

class MockTable {
  constructor(header, rows) { this.header = header.slice(); this.rows = rows.map(r => r.slice()); this.calls = []; }
  getHeaderRowRange() { return new MockRange(() => [this.header]); }
  getRangeBetweenHeaderAndTotal() {
    // 실제 Excel처럼 빈 표도 빈 행 1개를 돌려준다 → 스크립트는 getRowCount()로 먼저 확인해야 함
    return new MockRange(() => (this.rows.length ? this.rows : [this.header.map(() => "")]));
  }
  getRowCount() { return this.rows.length; }
  getColumnByName(name) {
    const i = this.header.indexOf(name);
    if (i < 0) throw new Error(`column ${name} not found`);
    return { getRangeBetweenHeaderAndTotal: () => new MockRange(() => this.rows.map(r => [r[i]])) };
  }
  addRows(index, values) {
    this.calls.push(["addRows", index, values.length]);
    values.forEach(v => { if (v.length !== this.header.length) throw new Error("column count mismatch"); });
    if (index === undefined || index === -1) this.rows.push(...values.map(v => v.slice()));
    else this.rows.splice(index, 0, ...values.map(v => v.slice()));
  }
  deleteRowsAt(index, count = 1) {
    this.calls.push(["deleteRowsAt", index, count]);
    if (index < 0 || index + count > this.rows.length) throw new Error("deleteRowsAt out of range");
    this.rows.splice(index, count);
  }
}

class MockWorksheet {
  constructor(name) { this.name = name; this.cells = []; }
  getUsedRange() {
    if (!this.cells.length) return undefined;
    return { clear: () => { this.cells = []; } };
  }
  getRange(addr) {
    if (addr !== "A1") throw new Error("mock supports A1 only");
    const self = this;
    return {
      getResizedRange(dr, dc) {
        return new MockRange(() => self.cells, v => {
          if (v.length !== dr + 1 || v.some(r => r.length !== dc + 1)) throw new Error("setValues size mismatch");
          self.cells = v.map(r => r.slice());
        });
      },
    };
  }
}

class MockWorkbook {
  constructor() { this.tables = {}; this.sheets = {}; }
  addMockTable(name, header, rows) { this.tables[name] = new MockTable(header, rows); return this.tables[name]; }
  getTable(name) { return this.tables[name]; }
  getWorksheet(name) { return this.sheets[name]; }
  addWorksheet(name) { this.sheets[name] = new MockWorksheet(name); return this.sheets[name]; }
}

module.exports = { MockWorkbook };
