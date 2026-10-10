"""Behavioral smoke tests for the Web Reports dashboard (issue #221)."""

from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path

import pytest

from webapp.report_routes import handle_report_get, web_report_html


class FakeResponse:
    def __init__(self, path: str):
        self.path = path
        self.command = "GET"
        self.status = None
        self.headers = {}
        self.wfile = io.BytesIO()

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.headers[name] = value

    def end_headers(self):
        pass


def test_report_javascript_uses_executable_mime_and_nosniff():
    response = FakeResponse("/report-dashboard.js")
    assert handle_report_get(response) is True
    assert response.status == 200
    assert response.headers["Content-Type"] == "application/javascript; charset=utf-8"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert int(response.headers["Content-Length"]) == len(response.wfile.getvalue())
    assert b"window.loadSummary" in response.wfile.getvalue()


def test_report_page_bootstraps_data_only_and_escapes_html_attribute():
    report = web_report_html('report-token" onmouseover="bad')
    assert 'data-report-token="report-token&quot; onmouseover=&quot;bad"' in report
    assert report.count("<script") == 1
    assert '<script src="/report-dashboard.js"></script>' in report
    assert "function loadSummary()" not in report
    assert "addEventListener('click'" not in report


# Execute the actual unmodified dashboard source in a tiny DOM/fetch harness.
# This tests runtime control interactions rather than asserting source substrings.
# No third-party Node packages or real credentials are required.
_NODE_DASHBOARD_SMOKE = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const calls = [];
const nodes = new Map();
const stored = new Map([['task-report-dashboard-filter', JSON.stringify({
  period: 'custom', start: '2026-08-01', end: '2026-08-31',
  search: 'needle', filters: {
    status: 'done', priority: 'high', category: 'work',
    assignee: '42', has_deadline: 'yes', overdue: 'no', sort: 'oldest'
  }
})]]);
const stateKey = 'task-report-dashboard-filter';

class Element {
  constructor(id = '') {
    this.id = id;
    this.dataset = {};
    this.style = {};
    this.value = '';
    this.listeners = {};
    this.classList = { toggle(name, state) { this[name] = !!state; }, add() {}, remove() {} };
    this.innerHTML = '';
    this.textContent = '';
  }
  addEventListener(event, fn) {
    (this.listeners[event] ||= []).push(fn);
  }
  click() {
    for (const fn of this.listeners.click || []) fn({target: this});
  }
  set outerHTML(value) {
    this.innerHTML = value;
    if (this.id === 'reportFilters') mountFilterCard();
  }
  insertAdjacentHTML(position, value) {
    if (value.includes('id="reportFilters"')) mountFilterCard();
  }
  insertAdjacentElement(position, element) {
    if (element.id) nodes.set(element.id, element);
  }
  querySelectorAll() { return []; }
  querySelector() { return null; }
}

const nav = ['tasks', 'week', 'status'].map(section => {
  const button = new Element();
  button.dataset.section = section;
  return button;
});
let periods = [];
function mountFilterCard() {
  nodes.set('reportFilters', new Element('reportFilters'));
  const fields = [
    'filterSummary', 'taskSearch', 'filterStart', 'filterEnd',
    'filterStatus', 'filterPriority', 'filterCategory', 'filterAssignee',
    'filterHasDeadline', 'filterOverdue', 'taskSort',
    'customDates', 'applyReportFilter', 'clearReportFilters',
    'exportCsv', 'exportPdf'
  ];
  for (const id of fields) nodes.set(id, new Element(id));
  periods = ['today', 'week', 'month', 'custom'].map(period => {
    const button = new Element();
    button.dataset.period = period;
    return button;
  });
}

nodes.set('reportRoot', {dataset: {reportToken: 'smoke-test-token'}});
for (const id of ['app', 'details', 'priorityTop']) nodes.set(id, new Element(id));

const doc = {
  head: {appendChild() {}},
  createElement(tag) { return new Element(tag); },
  getElementById(id) { return nodes.get(id) || null; },
  querySelector() { return null; },
  querySelectorAll(selector) {
    if (selector === '[data-section]') return nav;
    if (selector === '.filter-period') return periods;
    return [];
  }
};

const summary = {
  period: {gregorian: '2026-10', jalali: '1405/07'},
  summary: {total: 1, done: 0, pending: 1, productivity: {}},
  by_status: [{key: 'pending', label: 'Pending', count: 1}],
  by_priority: [{key: 'medium', count: 1}],
  filter_options: {}
};
async function fetchResponse(url) {
  calls.push(String(url));
  if (String(url).includes('/export/')) {
    return {ok: true, blob: async () => Buffer.from('download')};
  }
  if (String(url).includes('/section/tasks')) {
    return {
      ok: true,
      json: async () => ({
        section: 'tasks', page: 1, pages: 1, total: 1,
        rows: [{id: 'task-1', title: 'Visible task', status_label: 'Pending',
          priority: 'medium', deadline: '', category: '', assignee: ''}]
      })
    };
  }
  return {ok: true, json: async () => summary};
}
let downloads = 0;
const realCreate = doc.createElement;
doc.createElement = tag => {
  const item = realCreate(tag);
  if (tag === 'a') item.click = () => { downloads++; };
  return item;
};

const sandbox = {
  document: doc, sessionStorage: {
    getItem(key) { return stored.get(key) || null; },
    setItem(key, value) { stored.set(key, value); }
  },
  fetch: fetchResponse, URL: {
    createObjectURL() { return 'blob:fake'; },
    revokeObjectURL() {}
  },
  setTimeout() {}, console, alert(message) { throw new Error('Unexpected alert: ' + message); },
  CSS: {escape(value) { return value; }}
};
sandbox.window = sandbox;
const source = fs.readFileSync(process.argv[1], 'utf8');
vm.runInNewContext(source, sandbox, {filename: 'report_dashboard.js'});

async function settle() {
  for (let i = 0; i < 20; i++) await Promise.resolve();
}

(async () => {
  await settle();
  assert.equal(calls.length, 1, 'dashboard must fetch one initial summary');
  assert.equal(nav[0].listeners.click.length, 1, 'section navigation must bind once');
  assert.equal(nodes.get('filterStatus').value, 'done');
  assert.equal(nodes.get('filterStart').value, '2026-08-01');

  nav[0].click();
  await settle();
  assert.equal(sandbox.activeReportSection, 'tasks');
  assert.match(nodes.get('details').innerHTML, /Visible task/);

  const reset = nodes.get('clearReportFilters');
  assert.equal(reset.listeners.click.length, 1);
  reset.click();  // formerly infinite recursion
  await settle();

  const state = JSON.parse(stored.get(stateKey));
  assert.equal(state.period, 'month');
  assert.equal(state.start, '');
  assert.equal(state.end, '');
  assert.equal(state.search, '');
  assert.equal(state.filters.status, '');
  assert.equal(state.filters.priority, '');
  assert.equal(state.filters.sort, 'newest');
  assert.equal(nodes.get('filterStatus').value, '');
  assert.equal(nodes.get('filterStart').value, '');
  assert.equal(nodes.get('taskSort').value, 'newest');
  assert.equal(nodes.get('taskSearch').value, '');
  assert.equal(nodes.get('clearReportFilters').listeners.click.length, 1);
  assert.match(nodes.get('details').innerHTML, /Visible task/,
    'refreshing summary must not overwrite active section');
  assert.equal(nav[0].listeners.click.length, 1, 'section listeners should not multiply');
  assert.equal(calls.filter(url => url.includes('/section/tasks')).length, 2);
  assert.equal(calls.filter(url => !url.includes('/section/') && !url.includes('/export/')).length, 2);

  nodes.get('exportCsv').click();
  await settle();
  assert.equal(downloads, 1, 'CSV export click still works');
  assert(calls.some(url => url.includes('/export/csv?period=month')));
  console.log('report dashboard interaction smoke passed');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js runtime not installed")
def test_dashboard_behavior_reset_navigation_export_and_single_init():
    script = Path(__file__).parents[1] / "webapp" / "report_dashboard.js"
    result = subprocess.run(
        ["node", "-e", _NODE_DASHBOARD_SMOKE, str(script)],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "report dashboard interaction smoke passed" in result.stdout
