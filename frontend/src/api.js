export async function api(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    throw new Error('Нет связи с локальным сервером. Проверьте, что приложение запущено.');
  }

  if (!response.ok) {
    let body;
    try {
      body = await response.json();
    } catch {
      body = {detail: response.statusText};
    }
    throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail));
  }

  return response.json();
}

export const jsonRequest = (method, body) => ({
  method,
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(body),
});
