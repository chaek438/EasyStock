let csrf = ''
export function setCsrf(value) { csrf = value || '' }
export async function api(path, options = {}) {
  const response = await fetch('/api' + path, {
    credentials: 'same-origin', ...options,
    headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...options.headers},
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })
  const result = await response.json().catch(() => ({error: 'Сервер повернув некоректну відповідь.'}))
  if (!response.ok) {
    const error = new Error(result.error || 'Не вдалося виконати дію.')
    error.status = response.status
    if (response.status === 401 && path !== '/auth/login') window.dispatchEvent(new Event('session-expired'))
    throw error
  }
  return result
}
export function query(values) { return '?' + new URLSearchParams(Object.entries(values).filter(([, v]) => v !== '' && v != null)) }
export async function allProducts() {
  let items = [], page = 1, result
  do { result = await api('/products' + query({page, per_page: 100})); items.push(...result.items); page++ } while(items.length < result.total)
  return items
}
