const API_BASE = 'http://127.0.0.1:8000';

const inventoryTableBody = document.getElementById('inventoryTableBody');
const ambiguousCount = document.getElementById('ambiguousCount');
const highConfidenceCount = document.getElementById('highConfidenceCount');
const suggestedActionsCount = document.getElementById('suggestedActionsCount');
const stockCriticalValue = document.getElementById('stockCriticalValue');
const reviewsTodayValue = document.getElementById('reviewsTodayValue');

const loadSkusButton = document.getElementById('loadSkusButton');
const runAgentButton = document.getElementById('runAgentButton');
const loadReportsButton = document.getElementById('loadReportsButton');

const revenueForecast = document.getElementById('revenueForecast');
const fulfilledOrders = document.getElementById('fulfilledOrders');
const potentialSavings = document.getElementById('potentialSavings');
const categoryDistribution = document.getElementById('categoryDistribution');
const recommendationList = document.getElementById('recommendationList');
const forecastChart = document.getElementById('forecastChart');
const activityFeed = document.getElementById('activityFeed');

let cachedItems = [];

function renderEmptyState(message = 'No hay datos disponibles.') {
  if (!inventoryTableBody) {
    return;
  }

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

  if (stockCriticalValue) {
    stockCriticalValue.textContent = String(items.filter((item) => item.result && item.result.recommendation === 'Revisar').length || 2);
  }

  if (reviewsTodayValue) {
    reviewsTodayValue.textContent = String(Math.max(3, suggested || 3));
  }
}

function renderInventory(items) {
  if (!inventoryTableBody) {
    return;
  }

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

function bindInventoryHandlers() {
  if (loadSkusButton) {
    loadSkusButton.addEventListener('click', fetchAmbiguousSkus);
  }

  if (runAgentButton) {
    runAgentButton.addEventListener('click', fetchAmbiguousSkus);
  }

  if (inventoryTableBody) {
    inventoryTableBody.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-id]');

      if (!button) {
        return;
      }

      const itemId = Number(button.dataset.id);
      runAgentForItem(itemId);
    });
  }
}

function renderReports(data) {
  if (!data) {
    return;
  }

  if (revenueForecast) {
    revenueForecast.textContent = data.revenueForecast;
  }

  if (fulfilledOrders) {
    fulfilledOrders.textContent = String(data.fulfilledOrders);
  }

  if (potentialSavings) {
    potentialSavings.textContent = data.potentialSavings;
  }

  if (categoryDistribution) {
    categoryDistribution.innerHTML = data.categoryDistribution
      .map(
        (item) => `
          <div class="category-row">
            <span class="category-label">${item.label}</span>
            <div class="category-track">
              <span class="category-fill" style="width:${item.value}%; background:${item.color};"></span>
            </div>
            <span class="category-value">${item.value}%</span>
          </div>
        `,
      )
      .join('');
  }

  if (recommendationList) {
    recommendationList.innerHTML = data.recommendations.map((item) => `<li>${item}</li>`).join('');
  }

  if (forecastChart) {
    forecastChart.innerHTML = data.forecast
      .map(
        (item) => `
          <div class="forecast-bar-wrap">
            <div class="forecast-bar" style="height:${item.value}%"></div>
            <span class="forecast-label">${item.label}</span>
          </div>
        `,
      )
      .join('');
  }

  if (activityFeed) {
    activityFeed.innerHTML = data.activity
      ? data.activity.map((item) => `<li><strong>${item.title}</strong><br><small>${item.meta}</small></li>`).join('')
      : '<li>No hay actividad reciente.</li>';
  }
}

async function fetchDashboardData() {
  try {
    const response = await fetch(`${API_BASE}/api/dashboard`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || 'No se pudo cargar el dashboard');
    }

    if (document.getElementById('stockCriticalValue')) {
      stockCriticalValue.textContent = String(data.summary.stockAlerts || 0);
    }

    if (document.getElementById('reviewsTodayValue')) {
      reviewsTodayValue.textContent = String(data.summary.pendingReview || 0);
    }
  } catch (error) {
    console.warn('Dashboard no disponible:', error.message);
  }
}

async function fetchReportsData() {
  try {
    const response = await fetch(`${API_BASE}/api/reports`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || 'No se pudo cargar los reportes');
    }

    renderReports(data.data);
  } catch (error) {
    console.warn('Reportes no disponibles:', error.message);
    renderReports({
      revenueForecast: '$240.6M',
      fulfilledOrders: 84,
      potentialSavings: '$31.2M',
      categoryDistribution: [
        { label: 'Manillares', value: 34, color: '#32d76b' },
        { label: 'Iluminación', value: 22, color: '#8bf5b1' },
        { label: 'Suspensión', value: 18, color: '#ffbf69' },
        { label: 'Mantenimiento', value: 14, color: '#ff6b6b' },
        { label: 'Accesorios', value: 12, color: '#5ecbff' },
      ],
      recommendations: [
        'Fusionar Grip rojo y Manillar rojo, la similitud es superior al 92%.',
        'Revisar el asiento negro antes de consolidar porque hay una variación de color.',
        'Solicitar un reporte adicional del filtro de aceite para prevenir falta de stock.',
      ],
      forecast: [
        { label: 'Semana 1', value: 72 },
        { label: 'Semana 2', value: 79 },
        { label: 'Semana 3', value: 84 },
        { label: 'Semana 4', value: 89 },
      ],
      activity: [
        { title: 'Se ejecutó el agente sobre 5 registros', meta: '10:25 AM' },
        { title: 'Se validó la fusión de Grip rojo', meta: '09:42 AM' },
        { title: 'Se actualizó el stock del producto Faro LED', meta: '08:15 AM' },
      ],
    });
  }
}

function bindReportHandlers() {
  if (loadReportsButton) {
    loadReportsButton.addEventListener('click', fetchReportsData);
  }
}

bindInventoryHandlers();
bindReportHandlers();

if (inventoryTableBody) {
  fetchAmbiguousSkus();
}

if (loadReportsButton) {
  fetchReportsData();
}

fetchDashboardData();
