/* Cliente HTTP base: cookie de sesión (HttpOnly) + manejo del error
 * { codigo, mensaje, detalle } de docs/04 §4.1. */

export interface ApiErrorBody {
  codigo: string
  mensaje: string
  detalle?: Record<string, unknown>
}

export class ApiError extends Error {
  readonly codigo: string
  readonly estado: number
  readonly detalle: Record<string, unknown>

  constructor(estado: number, cuerpo: ApiErrorBody) {
    super(cuerpo.mensaje)
    this.estado = estado
    this.codigo = cuerpo.codigo
    this.detalle = cuerpo.detalle ?? {}
  }
}

export type Opciones = { metodo?: string; cuerpo?: unknown; senal?: AbortSignal; cabeceras?: Record<string, string> }

/** Convierte los errores de Pydantic (422 campos) al mismo cuerpo. */
function cuerpo422(datos: unknown): ApiErrorBody {
  const d = datos as { detail?: Array<{ msg?: string; loc?: unknown[] }> }
  const campo = d?.detail?.[0]?.loc?.slice(-1)[0]
  return {
    codigo: 'campos',
    mensaje:
      d?.detail?.[0]?.msg
        ? `${d.detail[0].msg}${typeof campo === 'string' ? ` (campo: ${campo})` : ''}`
        : 'Datos inválidos.',
    detalle: {},
  }
}

async function peticion<T>(url: string, opciones: Opciones = {}): Promise<T> {
  const init: RequestInit = {
    method: opciones.metodo ?? 'GET',
    credentials: 'include',
    signal: opciones.senal,
    headers: { ...(opciones.cabeceras ?? {}) },
  }
  if (opciones.cuerpo !== undefined) {
    init.headers = { ...(opciones.cabeceras ?? {}), 'Content-Type': 'application/json' }
    init.body = JSON.stringify(opciones.cuerpo)
  }
  const respuesta = await fetch(url, init)

  if (!respuesta.ok) {
    const texto = await respuesta.text()
    let cuerpo: ApiErrorBody
    try {
      const datos = JSON.parse(texto)
      cuerpo = datos.codigo
        ? { codigo: datos.codigo, mensaje: datos.mensaje, detalle: datos.detalle }
        : cuerpo422(datos)
    } catch {
      cuerpo = { codigo: 'interno', mensaje: `Error ${respuesta.status}`, detalle: {} }
    }
    if (respuesta.status === 401 && window.location.pathname !== '/login') {
      // sesión perdida: volver a autenticar
      window.location.assign('/login')
    }
    throw new ApiError(respuesta.status, cuerpo)
  }

  if (respuesta.status === 204) return undefined as T
  return (await respuesta.json()) as T
}

export const http = {
  GET: <T>(url: string, senal?: AbortSignal) => peticion<T>(url, { senal }),
  POST: <T>(url: string, cuerpo?: unknown, cabeceras?: Record<string, string>) =>
    peticion<T>(url, { metodo: 'POST', cuerpo, cabeceras }),
  PATCH: <T>(url: string, cuerpo: unknown) => peticion<T>(url, { metodo: 'PATCH', cuerpo }),
  DELETE: <T>(url: string, cuerpo?: unknown) => peticion<T>(url, { metodo: 'DELETE', cuerpo }),
}

/** Clave de idempotencia para cobros (docs/04 §4.2 convención). */
export function nuevaClaveIdempotencia(): string {
  return crypto.randomUUID()
}
