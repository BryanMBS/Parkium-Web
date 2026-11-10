/* SDK del módulo de plataforma (/api/platform/*, Fase 3).
 * Los errores llegan en el contrato { codigo, mensaje, detalle } (docs/04 §4.1). */

import { http } from './client'

export interface Tenant {
  id: number
  name: string
  nit: string
  status: 'ACTIVE' | 'SUSPENDED'
  plan: 'BASIC' | 'PRO' | 'ENTERPRISE'
  max_sites: number
  max_users: number
  billing_cutoff_day: number
  created_at: string
  updated_at: string
  sedes?: number
  usuarios?: number
}

export interface TenantDetalle {
  tenant: Tenant
  sede_id: number | null
  admin: { id: number; username: string; full_name: string } | null
  /** Contraseña temporal: se muestra UNA vez en la creación. */
  contrasena_temporal?: string
}

export interface Sede {
  id: number
  tenant_id: number
  name: string
  tax_id: string | null
  address: string | null
  phone: string | null
  total_capacity: number
  timezone: string
  is_active: number
  created_at: string
}

export interface AdminTenant {
  id: number
  username: string
  full_name: string
  is_active: number
  last_login_at: string | null
  must_change_password: number
  rol: string
}

export interface Resumen {
  clientes: number
  activos: number
  suspendidos: number
  sedes: number
  usuarios: number
}

export interface EventoAuditoria {
  id: number
  action: string
  entity_type: string | null
  entity_id: number | null
  tenant_id: number | null
  tenant: string | null
  occurred_at: string
  ip_address: string | null
  actor: string | null
  before_data: string | null
  after_data: string | null
}

export interface CrearTenantDatos {
  name: string
  nit: string
  plan: Tenant['plan']
  max_sites: number
  max_users: number
  billing_cutoff_day: number
  sede_nombre?: string | null
  sede_cupos?: number | null
  admin_username?: string | null
  admin_nombre?: string | null
}

export const plataforma = {
  resumen: () => http.GET<Resumen>('/api/platform/summary'),

  listarTenants: (q?: string, estado?: string) => {
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (estado) params.set('estado', estado)
    const qs = params.toString()
    return http.GET<Tenant[]>(`/api/platform/tenants${qs ? `?${qs}` : ''}`)
  },

  detalleTenant: (id: number) => http.GET<Tenant>(`/api/platform/tenants/${id}`),

  crearTenant: (datos: CrearTenantDatos) => http.POST<TenantDetalle>('/api/platform/tenants', datos),

  parcharTenant: (id: number, campos: Partial<{ name: string; plan: string; max_sites: number; max_users: number; billing_cutoff_day: number }>) =>
    http.PATCH<Tenant>(`/api/platform/tenants/${id}`, campos),

  suspenderTenant: (id: number, motivo: string) =>
    http.POST<{ estado: string }>(`/api/platform/tenants/${id}/suspend`, { motivo }),

  reactivarTenant: (id: number, motivo: string) =>
    http.POST<{ estado: string }>(`/api/platform/tenants/${id}/reactivate`, { motivo }),

  listarSedes: (id: number) => http.GET<Sede[]>(`/api/platform/tenants/${id}/sites`),

  crearSede: (id: number, name: string, total_capacity: number) =>
    http.POST<Sede>(`/api/platform/tenants/${id}/sites`, { name, total_capacity }),

  parcharSede: (id: number, sede_id: number, campos: Partial<{ name: string; total_capacity: number; tax_id: string; address: string; phone: string }>) =>
    http.PATCH<Sede>(`/api/platform/tenants/${id}/sites/${sede_id}`, campos),

  listarAdmins: (id: number) => http.GET<AdminTenant[]>(`/api/platform/tenants/${id}/admins`),

  crearAdmin: (id: number, username: string, nombre: string, rol: 'ADMIN' | 'SUPERADMIN') =>
    http.POST<{ usuario: AdminTenant; contrasena_temporal: string }>(
      `/api/platform/tenants/${id}/admins`, { username, nombre, rol },
    ),

  fijarContrasenaAdmin: (id: number, user_id: number, nueva: string) =>
    http.POST<{ estado: string }>(`/api/platform/tenants/${id}/admins/${user_id}/password`, { nueva }),

  /** `desde`/`hasta` en YYYY-MM-DD (docs/04 convenciones). */
  auditar: (filtros: { pagina?: number; por_pagina?: number; desde?: string; hasta?: string; accion?: string; tenant_id?: number }) => {
    const params = new URLSearchParams()
    for (const [k, v] of Object.entries(filtros)) {
      if (v !== undefined && v !== null && v !== '') params.set(k, String(v))
    }
    const qs = params.toString()
    return http.GET<{ pagina: number; por_pagina: number; eventos: EventoAuditoria[] }>(
      `/api/platform/audit${qs ? `?${qs}` : ''}`,
    )
  },
}
