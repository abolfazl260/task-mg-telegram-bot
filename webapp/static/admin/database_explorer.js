(() => {
  const q = (selector) => document.querySelector(selector);
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[char]));

  const tg = window.Telegram?.WebApp;
  const initData = tg?.initData || "";
  let tables = [];
  let activeTable = null;
  let offset = 0;
  let limit = 50;
  let sort = "";
  let direction = "asc";
  let filters = {};
  let loaded = false;
  let requestSerial = 0;

  async function request(url) {
    const headers = {};
    if (initData) headers["X-Telegram-Init-Data"] = initData;
    const response = await fetch(url, {headers, cache: "no-store"});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    return payload;
  }

  function showState(message, kind = "") {
    const state = q("#dbGridState");
    state.hidden = !message;
    state.className = `db-grid-state ${kind}`.trim();
    state.textContent = message || "";
  }

  function typePlaceholder(column) {
    if (column.type === "number") return "Number";
    if (column.type === "datetime") return "ISO date/time";
    if (column.type === "boolean") return "true / false";
    return "Search";
  }

  function operatorLabel(operator) {
    return ({
      contains: "Contains",
      exact: "Exact",
      equals: "=",
      greater_than: ">",
      less_than: "<",
      range: "Range",
      before: "Before",
      after: "After",
    })[operator] || operator;
  }

  function currentFilter(column) {
    const firstOperator = column.operators?.[0] || "exact";
    return filters[column.name] || {operator: firstOperator, value: "", value_to: ""};
  }

  function renderHeader() {
    const head = q("#dbGridHead");
    if (!head || !activeTable) return;
    head.innerHTML = `
      <tr class="db-column-row">
        ${activeTable.columns.map(column => `
          <th>
            <button class="db-sort-button" type="button" data-db-sort="${esc(column.name)}">
              <span>${esc(column.name)}</span>
              <small>${esc(column.type)}</small>
              <i class="db-sort-indicator"></i>
            </button>
          </th>`).join("")}
      </tr>
      <tr class="db-filter-row">
        ${activeTable.columns.map(column => {
          const filter = currentFilter(column);
          const range = filter.operator === "range";
          const boolean = column.type === "boolean";
          return `
            <th>
              <div class="db-filter-cell">
                <select data-db-operator="${esc(column.name)}" aria-label="Filter operator for ${esc(column.name)}">
                  ${column.operators.map(operator => `<option value="${esc(operator)}" ${filter.operator === operator ? "selected" : ""}>${esc(operatorLabel(operator))}</option>`).join("")}
                </select>
                ${boolean
                  ? `<select data-db-value="${esc(column.name)}" aria-label="Filter value for ${esc(column.name)}"><option value="">Any</option><option value="true" ${filter.value === "true" ? "selected" : ""}>true</option><option value="false" ${filter.value === "false" ? "selected" : ""}>false</option></select>`
                  : `<input data-db-value="${esc(column.name)}" value="${esc(filter.value)}" placeholder="${esc(typePlaceholder(column))}" autocomplete="off">`}
                ${range ? `<input data-db-value-to="${esc(column.name)}" value="${esc(filter.value_to)}" placeholder="To" autocomplete="off">` : ""}
              </div>
            </th>`;
        }).join("")}
      </tr>`;

    head.querySelectorAll("[data-db-sort]").forEach(button => button.addEventListener("click", () => {
      const column = button.dataset.dbSort;
      if (sort === column) direction = direction === "asc" ? "desc" : "asc";
      else {
        sort = column;
        direction = "asc";
      }
      offset = 0;
      updateSortIndicators();
      loadRows();
    }));

    head.querySelectorAll("[data-db-operator]").forEach(select => select.addEventListener("change", () => {
      const column = select.dataset.dbOperator;
      filters[column] = {...currentFilter(activeTable.columns.find(item => item.name === column)), operator: select.value};
      offset = 0;
      renderHeader();
      loadRows();
    }));

    let debounce;
    const onValue = (event) => {
      const column = event.target.dataset.dbValue || event.target.dataset.dbValueTo;
      const meta = activeTable.columns.find(item => item.name === column);
      const state = {...currentFilter(meta)};
      if (event.target.dataset.dbValue) state.value = event.target.value;
      else state.value_to = event.target.value;
      filters[column] = state;
      offset = 0;
      clearTimeout(debounce);
      debounce = setTimeout(loadRows, 300);
    };
    head.querySelectorAll("[data-db-value], [data-db-value-to]").forEach(input => {
      input.addEventListener(input.tagName === "SELECT" ? "change" : "input", onValue);
    });
    updateSortIndicators();
  }

  function updateSortIndicators() {
    document.querySelectorAll("[data-db-sort]").forEach(button => {
      const indicator = button.querySelector(".db-sort-indicator");
      if (!indicator) return;
      indicator.textContent = button.dataset.dbSort === sort ? (direction === "asc" ? "↑" : "↓") : "";
    });
  }

  function collectFilters() {
    return Object.entries(filters).flatMap(([column, state]) => {
      const value = String(state.value ?? "").trim();
      if (!value) return [];
      const item = {column, operator: state.operator, value};
      if (state.operator === "range") {
        const valueTo = String(state.value_to ?? "").trim();
        if (!valueTo) return [];
        item.value_to = valueTo;
      }
      return [item];
    });
  }

  function formatCell(column, value) {
    if (value === null || value === undefined) return '<span class="db-null">NULL</span>';
    if (column.type === "boolean") return `<span class="db-boolean">${value ? "true" : "false"}</span>`;
    const text = String(value);
    const idLike = column.name === "id" || column.name.endsWith("_id") || column.name.endsWith("_key");
    const cls = idLike ? "db-id" : text.length > 70 ? "db-long" : "";
    return `<span class="${cls}" title="${esc(text)}">${esc(text || "—")}</span>`;
  }

  function renderRows(payload) {
    const body = q("#dbGridBody");
    const columns = activeTable?.columns || [];
    if (!payload.rows.length) {
      body.innerHTML = `<tr><td colspan="${columns.length}" class="db-empty">No matching records.</td></tr>`;
    } else {
      body.innerHTML = payload.rows.map(row => `
        <tr>${columns.map(column => `<td>${formatCell(column, row[column.name])}</td>`).join("")}</tr>
      `).join("");
    }

    const page = Math.floor(payload.offset / payload.limit) + 1;
    const pages = Math.max(1, Math.ceil(payload.total / payload.limit));
    q("#dbPageInfo").textContent = `Page ${page} of ${pages}`;
    q("#dbExplorerMeta").textContent = `${payload.total} records · read-only`;
    q("#dbPrev").disabled = payload.offset <= 0;
    q("#dbNext").disabled = payload.offset + payload.limit >= payload.total;
  }

  function renderGridShell() {
    const wrap = q("#dbGridWrap");
    if (!activeTable) {
      wrap.innerHTML = "";
      return;
    }
    wrap.innerHTML = `
      <table class="db-grid">
        <thead id="dbGridHead"></thead>
        <tbody id="dbGridBody"></tbody>
      </table>`;
    renderHeader();
  }

  async function loadRows() {
    if (!activeTable) return;
    const serial = ++requestSerial;
    showState("Loading records…", "loading");
    const params = new URLSearchParams({
      table: activeTable.name,
      limit: String(limit),
      offset: String(offset),
      sort,
      direction,
      filters: JSON.stringify(collectFilters()),
    });
    try {
      const payload = await request("/api/admin/database/rows?" + params.toString());
      if (serial !== requestSerial) return;
      showState("");
      renderRows(payload);
    } catch (error) {
      if (serial !== requestSerial) return;
      showState("Could not load database records: " + error.message, "error");
      const body = q("#dbGridBody");
      if (body) body.innerHTML = "";
    }
  }

  function selectTable(name) {
    activeTable = tables.find(table => table.name === name) || tables[0] || null;
    filters = {};
    offset = 0;
    if (!activeTable) {
      sort = "";
      direction = "asc";
      renderGridShell();
      return;
    }
    sort = activeTable.default_sort || activeTable.columns[0]?.name || "";
    direction = activeTable.default_direction || "asc";
    q("#dbTableSelect").value = activeTable.name;
    renderGridShell();
    loadRows();
  }

  async function loadTables() {
    if (loaded) return;
    showState("Loading database schema…", "loading");
    try {
      const payload = await request("/api/admin/database/tables");
      tables = payload.tables || [];
      const select = q("#dbTableSelect");
      select.innerHTML = tables.map(table => `<option value="${esc(table.name)}">${esc(table.label)}</option>`).join("");
      loaded = true;
      showState("");
      if (!tables.length) {
        showState("No database tables are configured for admin inspection.", "empty");
        return;
      }
      selectTable(tables[0].name);
    } catch (error) {
      showState("Could not load Database Explorer: " + error.message, "error");
    }
  }

  function setTab(name) {
    q("#overviewView").hidden = name !== "overview";
    q("#databaseView").hidden = name !== "database";
    document.querySelectorAll("[data-admin-tab]").forEach(button => {
      const active = button.dataset.adminTab === name;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
    });
    if (name === "database") loadTables();
  }

  document.querySelectorAll("[data-admin-tab]").forEach(button => button.addEventListener("click", () => setTab(button.dataset.adminTab)));
  q("#dbTableSelect")?.addEventListener("change", event => selectTable(event.target.value));
  q("#dbResetFilters")?.addEventListener("click", () => {
    filters = {};
    offset = 0;
    renderHeader();
    loadRows();
  });
  q("#dbPageSize")?.addEventListener("change", event => {
    limit = Number(event.target.value) || 50;
    offset = 0;
    loadRows();
  });
  q("#dbPrev")?.addEventListener("click", () => {
    offset = Math.max(0, offset - limit);
    loadRows();
  });
  q("#dbNext")?.addEventListener("click", () => {
    offset += limit;
    loadRows();
  });
})();
