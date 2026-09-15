const API_BASE = 'http://127.0.0.1:8000/api/v1';
const page = document.body.dataset.page;

const api = {
  async request(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, options);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body.error?.message || body.detail || 'No se pudo completar la solicitud.');
    }
    return body;
  },
  get(path) { return this.request(path); },
  post(path, data) { return this.request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }); },
  patch(path, data) { return this.request(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }); },
};

const money = (value) => new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(Number(value || 0));
const dateText = (value) => value ? new Date(value).toLocaleDateString('es-CO', { day: '2-digit', month: 'short', year: 'numeric' }) : '—';
const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
const empty = (title, detail = 'Cuando haya datos, aparecerán aquí.') => `<div class="empty-state"><strong>${escapeHtml(title)}</strong>${escapeHtml(detail)}</div>`;

function showNotice(id, message) {
  const element = document.getElementById(id);
  if (!element) return;
  element.hidden = !message;
  element.textContent = message || '';
}

async function loadDashboard() {
  const [catalog, products, pending, inventory] = await Promise.allSettled([
    api.get('/canonical-products?per_page=1'),
    api.get('/products?per_page=100'),
    api.get('/matches/pending?per_page=4'),
    api.get('/reports/inventory'),
  ]);
  const canonicalCount = catalog.status === 'fulfilled' ? catalog.value.meta.total : 0;
  const productItems = products.status === 'fulfilled' ? products.value.data : [];
  const pendingItems = pending.status === 'fulfilled' ? pending.value.data : [];
  const lowStock = inventory.status === 'fulfilled' ? inventory.value.data.low_stock || [] : [];
  document.getElementById('metricCanonical').textContent = canonicalCount;
  document.getElementById('metricUnlinked').textContent = Math.max(productItems.length - canonicalCount, 0);
  document.getElementById('metricPending').textContent = pending.status === 'fulfilled' ? pending.value.meta.total : '—';
  document.getElementById('metricCritical').textContent = lowStock.length;
  const list = document.getElementById('dashboardMatches');
  list.innerHTML = pendingItems.length ? pendingItems.map((item) => `
    <a class="match-row" href="Pages/coincidencias.html">
      <div><div class="match-names"><b>${escapeHtml(item.product.raw_name)}</b><span>↔</span><b>${escapeHtml(item.candidate.raw_name)}</b></div><div class="match-reason">${escapeHtml(item.reasons?.[0] || 'Coincidencia pendiente de revisión.')}</div></div>
      <div><span class="score">${Math.round(item.score * 100)}%</span><span class="status ${item.decision === 'automatic' ? 'status-auto' : 'status-review'}">${item.decision === 'automatic' ? 'Automática' : 'Revisar'}</span></div>
    </a>`).join('') : empty('Sin coincidencias pendientes', 'Importa una lista para activar el análisis.');
}

async function loadInventory() {
  const body = document.getElementById('inventoryBody');
  const search = document.getElementById('inventorySearch').value.trim();
  const category = document.getElementById('inventoryCategory').value;
  const sort = document.getElementById('inventorySort').value;
  body.innerHTML = `<tr><td colspan="6" class="empty-state">Consultando catálogo…</td></tr>`;
  try {
    const query = new URLSearchParams({ per_page: '100', sort });
    if (search) query.set('query', search);
    if (category) query.set('category', category);
    const response = await api.get(`/canonical-products?${query}`);
    const rows = response.data;
    const categorySelect = document.getElementById('inventoryCategory');
    if (categorySelect.options.length === 1) [...new Set(rows.map((row) => row.category))].sort().forEach((value) => categorySelect.add(new Option(value, value)));
    body.innerHTML = rows.length ? rows.flatMap((row) => [`<tr data-canonical="${row.id}"><td><button class="button button-quiet button-small expand-product" aria-label="Mostrar proveedores">＋</button></td><td><b>${escapeHtml(row.name)}</b><div class="muted mono">#${row.id}</div></td><td>${escapeHtml(row.category)}</td><td>${Object.entries(row.attributes || {}).map(([key, value]) => `<span class="supplier-chip">${escapeHtml(key)}: ${escapeHtml(value)}</span>`).join('') || '<span class="muted">Sin atributos</span>'}</td><td class="mono">${row.stock_in_bodega} <span class="muted">/ mín. ${row.minimum_stock}</span></td><td>${row.suppliers?.length || 0}</td></tr>`, `<tr class="expand-row" id="expand-${row.id}"><td></td><td colspan="5"><div class="muted">Proveedores vinculados</div>${(row.suppliers || []).map((supplier) => `<span class="supplier-chip"><b>${escapeHtml(supplier.provider_code)}</b> ${escapeHtml(supplier.name)} · ${money(supplier.unit_price)}</span>`).join('') || '<span class="muted">Todavía no hay vínculos.</span>'}</td></tr>`]).join('') : `<tr><td colspan="6">${empty('Catálogo vacío', 'Importa una lista de proveedor para crear productos.')}</td></tr>`;
  } catch (error) { body.innerHTML = `<tr><td colspan="6">${empty('No se pudo cargar el catálogo', error.message)}</td></tr>`; }
}

function initInventory() {
  ['inventorySearch', 'inventoryCategory', 'inventorySort'].forEach((id) => document.getElementById(id).addEventListener('input', loadInventory));
  document.getElementById('inventoryRefresh').addEventListener('click', loadInventory);
  document.getElementById('inventoryBody').addEventListener('click', (event) => {
    const button = event.target.closest('.expand-product');
    if (!button) return;
    const row = button.closest('tr');
    const expand = document.getElementById(`expand-${row.dataset.canonical}`);
    expand.classList.toggle('open');
    button.textContent = expand.classList.contains('open') ? '−' : '＋';
  });
  loadInventory();
}

async function loadSuppliers() {
  const response = await api.get('/suppliers?per_page=100');
  const select = document.getElementById('supplierSelect');
  select.innerHTML = '<option value="">Selecciona un proveedor</option>';
  response.data.forEach((supplier) => select.add(new Option(supplier.name, supplier.id)));
}

function initImport() {
  const form = document.getElementById('importForm');
  const input = document.getElementById('fileInput');
  const zone = document.getElementById('dropZone');
  const progress = document.getElementById('uploadProgress');
  const fileMeta = document.getElementById('fileMeta');
  const fileName = document.getElementById('fileName');
  const fileSize = document.getElementById('fileSize');
  const setFile = (file) => { if (!file) return; input.files = new DataTransfer().files; const transfer = new DataTransfer(); transfer.items.add(file); input.files = transfer.files; fileName.textContent = file.name; fileSize.textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB`; fileMeta.hidden = false; };
  input.addEventListener('change', () => setFile(input.files[0]));
  ['dragenter', 'dragover'].forEach((eventName) => zone.addEventListener(eventName, (event) => { event.preventDefault(); zone.classList.add('dragover'); }));
  ['dragleave', 'drop'].forEach((eventName) => zone.addEventListener(eventName, (event) => { event.preventDefault(); zone.classList.remove('dragover'); }));
  zone.addEventListener('drop', (event) => setFile(event.dataTransfer.files[0]));
  form.addEventListener('submit', (event) => { event.preventDefault(); const file = input.files[0]; const supplier = document.getElementById('supplierSelect').value; if (!file || !supplier) { showNotice('importResult', 'Selecciona proveedor y archivo antes de continuar.'); return; } const data = new FormData(); data.append('file', file); data.append('supplier_id', supplier); const xhr = new XMLHttpRequest(); xhr.open('POST', `${API_BASE}/imports`); xhr.upload.onprogress = (progressEvent) => { if (progressEvent.lengthComputable) progress.style.width = `${(progressEvent.loaded / progressEvent.total) * 100}%`; }; xhr.onload = () => { const result = JSON.parse(xhr.responseText || '{}'); if (xhr.status >= 200 && xhr.status < 300) { progress.style.width = '100%'; showNotice('importResult', `Importación completada: ${result.data.summary.imported_rows} filas importadas, ${result.data.summary.rejected_rows.length} rechazadas.`); loadImports(); } else showNotice('importResult', result.error?.message || 'No se pudo importar el archivo.'); }; xhr.onerror = () => showNotice('importResult', 'No se pudo conectar con la API.'); xhr.send(data); });
  Promise.all([loadSuppliers(), loadImports()]).catch((error) => showNotice('importResult', error.message));
}

async function loadImports() {
  const body = document.getElementById('importsBody');
  if (!body) return;
  try { const response = await api.get('/imports?per_page=10'); body.innerHTML = response.data.length ? response.data.map((item) => `<tr><td class="mono">${escapeHtml(item.filename)}</td><td>${item.supplier_id}</td><td>${item.summary.imported_rows ?? 0}</td><td>${dateText(item.created_at)}</td></tr>`).join('') : `<tr><td colspan="4">${empty('Sin importaciones', 'La primera lista aparecerá aquí.')}</td></tr>`; } catch (error) { body.innerHTML = `<tr><td colspan="4">${empty('Historial no disponible', error.message)}</td></tr>`; }
}

async function loadMatches() {
  const list = document.getElementById('matchesList');
  try { const response = await api.get('/matches/pending?per_page=100'); const items = response.data; list.innerHTML = items.length ? items.map((item) => `<article class="review-card" data-match="${item.id}"><span class="status ${item.decision === 'automatic' ? 'status-auto' : 'status-review'}">${Math.round(item.score * 100)}% · ${item.decision === 'automatic' ? 'automática' : 'revisión'}</span><h3>${escapeHtml(item.product.raw_name)} <span class="muted">↔</span> ${escapeHtml(item.candidate.raw_name)}</h3><p>${escapeHtml((item.reasons || []).join(' '))}</p><div class="review-actions"><button class="button button-primary match-confirm" data-id="${item.id}">Confirmar vínculo</button><button class="button button-danger match-reject" data-id="${item.id}">Rechazar</button></div></article>`).join('') : empty('No hay revisiones pendientes', 'El motor no tiene coincidencias esperando decisión.'); } catch (error) { list.innerHTML = empty('No se pudieron cargar coincidencias', error.message); }
}
function initMatches() { document.getElementById('refreshMatches').addEventListener('click', async () => { try { await api.post('/matches/suggest', {}); await loadMatches(); } catch (error) { showNotice('matchesNotice', error.message); } }); document.getElementById('matchesList').addEventListener('click', async (event) => { const button = event.target.closest('button[data-id]'); if (!button) return; try { if (button.classList.contains('match-confirm')) await api.post(`/matches/${button.dataset.id}/confirm`, {}); else await api.post(`/matches/${button.dataset.id}/reject`, { create_exclusion_rule: false }); await loadMatches(); } catch (error) { showNotice('matchesNotice', error.message); } }); loadMatches(); }

function addChatMessage(role, text) { const log = document.getElementById('chatLog'); const item = document.createElement('div'); item.className = `chat-message ${role}`; item.textContent = text; log.appendChild(item); log.scrollTop = log.scrollHeight; }
async function loadAgentActions() { const list = document.getElementById('agentActions'); try { const response = await api.get('/agent/actions?per_page=8'); list.innerHTML = response.data.length ? response.data.map((item) => `<div class="activity-item"><b>${escapeHtml(item.tool_name)}</b><small>${dateText(item.timestamp)} · ${item.required_confirmation ? (item.approved === null ? 'pendiente' : 'resuelta') : 'ejecutada'}</small></div>`).join('') : empty('Sin acciones', 'El agente todavía no ha ejecutado herramientas.'); } catch (error) { list.innerHTML = empty('Auditoría no disponible', error.message); } }
function initAgent() { document.getElementById('chatForm').addEventListener('submit', async (event) => { event.preventDefault(); const input = document.getElementById('chatInput'); const text = input.value.trim(); if (!text) return; addChatMessage('user', text); input.value = ''; try { const response = await api.post('/agent/chat', { message: text, session_id: 'frontend-demo' }); addChatMessage('assistant', response.data.response); (response.data.pending_confirmations || []).forEach((item) => addChatMessage('assistant', `Acción pendiente de confirmación: ${item.tool_name} (#${item.action_id}). Confírmala desde el flujo de revisión.`)); loadAgentActions(); } catch (error) { addChatMessage('assistant', `No pude completar la consulta: ${error.message}`); } }); loadAgentActions(); }

async function initReports() { const [inventory, purchases] = await Promise.allSettled([api.get('/reports/inventory'), api.get('/reports/purchase-suggestions')]); const report = inventory.status === 'fulfilled' ? inventory.value.data : { total_canonical: 0, low_stock: [] }; const suggestions = purchases.status === 'fulfilled' ? purchases.value.data : []; document.getElementById('reportTotal').textContent = report.total_canonical ?? 0; document.getElementById('reportLow').textContent = report.low_stock?.length ?? 0; document.getElementById('reportSuggestions').textContent = suggestions.length; document.getElementById('lowStockList').innerHTML = report.low_stock?.length ? report.low_stock.map((item) => `<li class="critical"><b>${escapeHtml(item.name)}</b><br><span class="muted">${item.stock_in_bodega} unidades · mínimo ${item.minimum_stock}</span></li>`).join('') : `<li>${empty('Sin alertas de stock', 'No hay productos bajo su mínimo.')}</li>`; document.getElementById('purchaseList').innerHTML = suggestions.length ? suggestions.map((item) => `<li><b>${escapeHtml(item.name)}</b><br><span class="muted">Comprar ${item.units_to_buy} unidades · ${escapeHtml(item.category)}</span></li>`).join('') : `<li>${empty('Sin sugerencias', 'No hay compras pendientes con los filtros actuales.')}</li>`; }

if (page === 'dashboard') loadDashboard();
if (page === 'inventory') initInventory();
if (page === 'import') initImport();
if (page === 'matches') initMatches();
if (page === 'agent') initAgent();
if (page === 'reports') { document.getElementById('refreshReports').addEventListener('click', initReports); initReports(); }
