const BASE_URL = 'http://localhost:8000/api/v1';

function showBackendNotice(message) {
  const main = document.querySelector('.main-content');
  if (!main) return;
  let notice = document.getElementById('apiConnectionNotice');
  if (!notice) {
    notice = document.createElement('div');
    notice.id = 'apiConnectionNotice';
    notice.className = 'notice';
    notice.setAttribute('role', 'alert');
    main.querySelector('.topbar')?.after(notice);
  }
  notice.textContent = message;
  notice.hidden = false;
}

function errorDetails(details) {
  if (details === undefined || details === null || details === '') return '';
  return typeof details === 'string' ? details : JSON.stringify(details);
}

function networkError() {
  const message = 'No se pudo conectar con el servidor. ¿Está encendido el backend?';
  showBackendNotice(message);
  return new Error(message);
}

async function request(path, options = {}) {
  const { stream = false, ...fetchOptions } = options;
  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, fetchOptions);
  } catch {
    throw networkError();
  }

  if (stream && response.ok && response.headers.get('content-type')?.includes('text/event-stream')) {
    return { stream: response.body };
  }

  let text;
  try {
    text = await response.text();
  } catch {
    throw networkError();
  }

  let body;
  try {
    body = text ? JSON.parse(text) : {};
  } catch {
    const message = 'El servidor respondió con contenido que no es JSON.';
    showBackendNotice(message);
    throw new Error(message);
  }

  if (!response.ok || body.error) {
    if (body.error) {
      const message = body.error.message || 'La solicitud no pudo completarse.';
      const details = errorDetails(body.error.details);
      const fullMessage = details ? `${message}\n${details}` : message;
      showBackendNotice(fullMessage);
      throw new Error(fullMessage);
    }
    const message = body.detail || `La solicitud falló (HTTP ${response.status}).`;
    showBackendNotice(message);
    throw new Error(message);
  }

  return { data: body.data, meta: body.meta || {} };
}

const api = {
  request,
  get(path) { return request(path); },
  post(path, data) {
    return request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  },
  patch(path, data) {
    return request(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  },
};

window.StockMindAPI = { BASE_URL, request, api };