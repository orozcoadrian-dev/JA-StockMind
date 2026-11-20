const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

async function apiRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw new Error('No se pudo conectar con el servidor. Verifica que el backend esté encendido.');
  }

  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error('El servidor respondió con contenido que no es JSON.');
  }

  if (!response.ok || body.error) {
    const message = body.error?.message
      || body.detail
      || `La solicitud falló (HTTP ${response.status}).`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  return { data: body.data, meta: body.meta || {} };
}

function jsonOptions(method, data) {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  };
}

window.StockMindAPI = {
  get(path) {
    return apiRequest(path);
  },
  post(path, data) {
    return apiRequest(path, jsonOptions('POST', data));
  },
  patch(path, data) {
    return apiRequest(path, jsonOptions('PATCH', data));
  },
};
