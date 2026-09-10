const API_BASE = 'http://127.0.0.1:8000';

const inventoryTableBody = document.getElementById('inventoryTableBody');
const ambiguousCount = document.getElementById('ambiguousCount');
const highConfidenceCount = document.getElementById('highConfidenceCount');
const suggestedActionsCount = document.getElementById('suggestedActionsCount');

const loadSkusButton = document.getElementById('loadSkusButton');
const runAgentButton = document.getElementById('runAgentButton');

let cachedItems = [];

function renderEmptyState(message = 'No hay datos disponibles.') {
  inventoryTableBody.innerHTML = `
    <tr>
      <td colspan="8" class="empty-state">${message}</td>
    </tr>
  `;
}

function updateMetrics(items) {
  ambiguousCount.textContent = String(items.length);
  const highConfidence = items.filter((item) => item.result && item.result.recommendation === 'Fusionar').length;
  const suggested = items.filter((item) => item.result && item.result.recommendation).length;

  highConfidenceCount.textContent = String(highConfidence);
  suggestedActionsCount.textContent = String(suggested);
}

function renderInventory(items) {
  if (!items.length) {
    renderEmptyState('Todavía no hay registros ambiguos en el inventario.');
    updateMetrics([]);
    return;
  }

  inventoryTableBody.innerHTML = items
    .map(
      (item) => `
        <tr>
          <td>${item.id}</td>
          <td>${item.provider_a}</td>
          <td>${item.sku_a}</td>
          <td>${item.provider_b}</td>
          <td>${item.sku_b}</td>
          <td>${item.reason}</td>
          <td>
            ${item.result
              ? `<span class="action-result ${item.result.recommendation.toLowerCase()}">${item.result.recommendation}</span><br><small>${item.result.similarity}% similitud</small>`
              : '<span class="action-result revisar">Pendiente</span>'}
          </td>
          <td>
            ${item.result
              ? `<button class="btn btn-secondary" data-id="${item.id}">Confirmar</button>`
              : '<button class="btn btn-primary" data-id="${item.id}">Ejecutar</button>'}
          </td>
        </tr>
      `,
    )
    .join('');

  updateMetrics(items);
}

async function fetchAmbiguousSkus() {
  try {
    const response = await fetch(`${API_BASE}/api/ambiguous-skus`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || 'No se pudo cargar la información');
    }

    cachedItems = data.items.map((item) => ({ ...item, result: null }));
    renderInventory(cachedItems);
  } catch (error) {
    renderEmptyState(`Error al cargar inventario: ${error.message}`);
  }
}

async function runAgentForItem(itemId) {
  const item = cachedItems.find((entry) => entry.id === itemId);

  if (!item) {
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/api/compare-skus`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        sku_a: item.sku_a,
        sku_b: item.sku_b,
      }),
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || 'No se pudo ejecutar el agente');
    }

    item.result = result.analysis;
    renderInventory(cachedItems);
  } catch (error) {
    console.error(error);
    alert(`No se pudo ejecutar el agente para el SKU ${itemId}: ${error.message}`);
  }
}

function bindEventHandlers() {
  loadSkusButton.addEventListener('click', fetchAmbiguousSkus);
  runAgentButton.addEventListener('click', fetchAmbiguousSkus);

  inventoryTableBody.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-id]');

    if (!button) {
      return;
    }

    const itemId = Number(button.dataset.id);
    runAgentForItem(itemId);
  });
}

bindEventHandlers();
fetchAmbiguousSkus();
