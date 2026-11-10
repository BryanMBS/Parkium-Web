import { http } from './client'

export interface Tarifa {
  id?: number
  tariff_plan_id?: number
  tipo_vehiculo: string
  nombre: string
  esquema: string
  monto: string
  gracia_minutos?: number
  fraccion_minutos?: number
}

export interface UsuarioLista {
  id: number
  usuario: string
  nombre_completo: string
  rol: string
  is_active: boolean
}

export interface DatosSitio {
  nombre: string
  nit: string
  direccion: string
  telefono: string
  capacidad_total: number
}

export interface PlantillaRecibo {
  nombre_plantilla: string
  nombre_parqueadero: string
  nit: string
  direccion: string
  encabezado: string | null
  terminos: string | null
  pie: string | null
  mostrar_codigo_barras: boolean
  mostrar_qr: boolean
}

export const admin = {
  tarifas: (senal?: AbortSignal) => http.GET<{ tarifas: Tarifa[] } | Tarifa[]>('/api/tariffs', senal),
  crearTarifa: (t: {
    tipo_vehiculo: string
    nombre: string
    esquema: string
    monto: string
    gracia_minutos?: number
    fraccion_minutos?: number
  }) => http.POST<{ id?: number }>('/api/tariffs', t),

  usuarios: (senal?: AbortSignal) =>
    http.GET<{ usuarios?: UsuarioLista[] } | UsuarioLista[]>('/api/users', senal),
  crearUsuario: (cuerpo: {
    usuario: string
    nombre_completo: string
    rol: string
    /** Pydantic espera la clave «contraseña» con ñ (docs/04 §4.8). */
    clave: string
  }) =>
    http.POST<{ id?: number }>('/api/users', {
      usuario: cuerpo.usuario,
      nombre_completo: cuerpo.nombre_completo,
      rol: cuerpo.rol,
      ['contrase\u00f1a']: cuerpo.clave,
    }),
  cambiarActivo: (id: number, activo: boolean) =>
    http.PATCH<unknown>(`/api/users/${id}/active`, { activo }),
  /** Reseteo por admin: sólo la nueva, sin pedir la actual. */
  fijarContrasena: (id: number, nueva: string) =>
    http.PATCH<unknown>(`/api/users/${id}/password`, { nueva }),

  sitio: () => http.GET<DatosSitio>('/api/site'),
  guardarSitio: (datos: Partial<DatosSitio>) => http.PATCH<unknown>('/api/site', datos),

  plantilla: () => http.GET<PlantillaRecibo>('/api/receipt-template'),
  guardarPlantilla: (datos: Partial<PlantillaRecibo>) => http.PATCH<unknown>('/api/receipt-template', datos),
}
