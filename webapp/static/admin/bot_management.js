(() => {
  const q = (s) => document.querySelector(s);
  const esc2 = (v) => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const tg2 = window.Telegram?.WebApp;
  const initData2 = tg2?.initData || "";
  let registry = [];
  let templates = {};
  let editingKey = "";

  async function request(url, options = {}) {
    const headers = {"Content-Type": "application/json", ...(options.headers || {})};
    if (initData2) headers["X-Telegram-Init-Data"] = initData2;
    const response = await fetch(url, {...options, headers, cache:"no-store"});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    return payload;
  }

  function message(text, error=false) {
    const el = q("#botConfigMessage");
    if (!el) return;
    el.hidden = !text;
    el.className = error ? "bot-config-message error" : "bot-config-message success";
    el.textContent = text || "";
  }

  function selectedFeatures() {
    return [...document.querySelectorAll("#botFeatureGrid input[type=checkbox]:checked")].map(x => x.value);
  }

  function renderFeatureGrid(selected = []) {
    const set = new Set(selected);
    const grid = q("#botFeatureGrid");
    grid.innerHTML = registry.map(f => `
      <label class="feature-option" title="${esc2((f.dependencies || []).length ? "Requires: " + f.dependencies.join(", ") : "No dependency")}">
        <input type="checkbox" value="${esc2(f.key)}" ${set.has(f.key) ? "checked" : ""}>
        <span><b>${esc2(f.label)}</b><small>${esc2(f.key)}</small></span>
      </label>`).join("");
  }

  function resetEditor() {
    editingKey = "";
    q("#botEditorTitle").textContent = "Create Bot";
    q("#botKey").disabled = false;
    q("#botKey").value = "";
    q("#botDisplayName").value = "";
    q("#botUsername").value = "";
    q("#botToken").value = "";
    q("#botDescription").value = "";
    q("#botStatus").value = "inactive";
    q("#botProfileType").value = "custom";
    renderFeatureGrid(["core","tasks"]);
    q("#cancelBotEdit").hidden = true;
    message("");
  }

  async function editBot(key) {
    const data = await request("/api/admin/bots/" + encodeURIComponent(key));
    const bot = data.bot;
    editingKey = bot.bot_key;
    q("#botEditorTitle").textContent = "Edit Bot · " + bot.bot_key;
    q("#botKey").value = bot.bot_key;
    q("#botKey").disabled = true;
    q("#botDisplayName").value = bot.display_name || "";
    q("#botUsername").value = bot.bot_username || "";
    q("#botToken").value = "";
    q("#botToken").placeholder = bot.token_masked || "Leave blank to keep current token";
    q("#botDescription").value = bot.description || "";
    q("#botStatus").value = bot.status || "inactive";
    q("#botProfileType").value = bot.profile_type || "custom";
    renderFeatureGrid(bot.features || []);
    q("#cancelBotEdit").hidden = false;
    q("#botEditor").scrollIntoView({behavior:"smooth", block:"start"});
  }

  async function toggleBot(key, active) {
    message("");
    await request(`/api/admin/bots/${encodeURIComponent(key)}/${active ? "activate" : "deactivate"}`, {method:"POST", body:"{}"});
    message(active ? "Bot activated." : "Bot deactivated.");
    await loadBots();
  }

  function renderBots(rows) {
    const el = q("#botConfigTable");
    if (!rows.length) {
      el.innerHTML = '<div class="empty">No managed bots configured.</div>';
      return;
    }
    el.innerHTML = `<div class="managed-bot-table-wrap"><table class="managed-bot-table">
      <thead><tr><th>Bot</th><th>Profile</th><th>Status</th><th>Features</th><th>Token</th><th>Updated</th><th>Actions</th></tr></thead>
      <tbody>${rows.map(bot => `<tr>
        <td><strong>${esc2(bot.display_name || bot.bot_key)}</strong><small>${esc2(bot.bot_username ? "@" + bot.bot_username : bot.bot_key)}</small></td>
        <td>${esc2(bot.profile_type || bot.base_profile || "custom")}</td>
        <td><span class="status-pill ${bot.status === "active" ? "ok" : "off"}">${esc2(bot.status)}</span></td>
        <td>${Number(bot.enabled_feature_count || 0)}</td>
        <td><code>${esc2(bot.token_masked || "Not configured")}</code></td>
        <td>${esc2(bot.updated_at || "—")}</td>
        <td class="bot-actions">
          <button data-edit="${esc2(bot.bot_key)}">Edit</button>
          <button data-toggle="${esc2(bot.bot_key)}" data-active="${bot.status === "active" ? "0" : "1"}">${bot.status === "active" ? "Deactivate" : "Activate"}</button>
        </td>
      </tr>`).join("")}</tbody></table></div>`;
    el.querySelectorAll("[data-edit]").forEach(btn => btn.addEventListener("click", () => editBot(btn.dataset.edit).catch(e => message(e.message, true))));
    el.querySelectorAll("[data-toggle]").forEach(btn => btn.addEventListener("click", () => toggleBot(btn.dataset.toggle, btn.dataset.active === "1").catch(e => message(e.message, true))));
  }

  async function loadBots() {
    const data = await request("/api/admin/bots");
    renderBots(data.bots || []);
  }

  async function loadRegistry() {
    const data = await request("/api/admin/bot-features");
    registry = data.features || [];
    templates = Object.fromEntries((data.profiles || []).map(profile => [profile.key, profile]));
    renderFeatureGrid((templates.custom && templates.custom.features) || ["core","tasks"]);
  }

  async function saveBot(event) {
    event.preventDefault();
    message("");
    const payload = {
      bot_key: q("#botKey").value.trim(),
      display_name: q("#botDisplayName").value.trim(),
      bot_username: q("#botUsername").value.trim(),
      bot_token: q("#botToken").value.trim(),
      description: q("#botDescription").value.trim(),
      status: q("#botStatus").value,
      profile_type: q("#botProfileType").value,
      base_profile: q("#botProfileType").value === "custom" ? "" : q("#botProfileType").value,
      features: selectedFeatures()
    };
    if (!payload.bot_token) delete payload.bot_token;
    if (editingKey) {
      delete payload.bot_key;
      await request("/api/admin/bots/" + encodeURIComponent(editingKey), {method:"PATCH", body:JSON.stringify(payload)});
      message("Bot configuration updated.");
    } else {
      await request("/api/admin/bots", {method:"POST", body:JSON.stringify(payload)});
      message("Bot created.");
    }
    await loadBots();
    resetEditor();
  }

  async function validateToken() {
    const token = q("#botToken").value.trim();
    if (!token) return message("Enter a token first.", true);
    try {
      const result = await request("/api/admin/bots/validate-token", {method:"POST", body:JSON.stringify({bot_token:token})});
      message("Token is valid for @" + result.username + ".");
      if (!q("#botUsername").value) q("#botUsername").value = result.username || "";
    } catch (e) {
      message(e.message, true);
    }
  }

  q("#botEditorForm")?.addEventListener("submit", e => saveBot(e).catch(err => message(err.message, true)));
  q("#botProfileType")?.addEventListener("change", e => {
    const template = templates[e.target.value];
    if (template?.features) renderFeatureGrid(template.features);
  });
  q("#validateBotToken")?.addEventListener("click", validateToken);
  q("#cancelBotEdit")?.addEventListener("click", resetEditor);
  q("#newBotButton")?.addEventListener("click", resetEditor);

  Promise.all([loadRegistry(), loadBots()]).catch(e => message(e.message, true));
})();