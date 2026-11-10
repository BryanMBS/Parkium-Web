import { http, nuevaClaveIdempotencia } from './client'

export interface ReciboRef {
  id?: number
  numero?: number
  receipt_number?: number
  tipo?: string
  token?: string
}

export interface PagoMensualidad {
  pago_id: number
  recibo?: ReciboRef
}

const conClave = () => ({ 'Idempotency-Key': nuevaClaveIdempotencia() })

export const clients = {
  listar: (filtros: { q?: string; estado?: string; soloSaldo?: boolean }, senal?: AbortSignal) => {
    const p = new URLSearchParams()
    if (filtros.q) p.set('q', filtros.q)
    if (filtros.estado) p.set('estado', filtros.estado)
    if (filtros.soloSaldo) p.set('solo_saldo', 'true')
    const cadena = p.toString()
    return http.GET<ClientesPlanes>(`/api/customers/plans${cadena ? `?${cadena}` : ''}`, senal)
  },
  crear: (cliente: ClienteNuevo) => http.POST<{ cliente_id: number }>('/api/customers', cliente),
  ficha: (id: number) => http.GET<ClienteFicha>(`/api/customers/${id}`),
  vehiculos: (id: number) => http.GET<{ placas: Array<{ placa: string; tipo_vehiculo: string }>; nombre: string }>(
    `/api/customers/${id}/vehicles`,
  ),
  agregarPlaca: (id: number, placa: string, tipoVehiculo: string) =>
    http.POST<unknown>(`/api/customers/${id}/vehicles`, { placa, tipo_vehiculo: tipoVehiculo }),
}

export interface ClienteNuevo {
  nombre: string
  documento: { tipo: string; numero: string }
  telefono?: string | null
  correo?: string | null
  direccion?: string | null
  placas?: string[]
}

export interface ClienteFicha {
  cliente_id: number
  nombre: string
  documento: { tipo: string; numero: string } | null
  telefono: string | null
  correo: string | null
}

export interface ClientePlan {
  cliente_id: number
  nombre: string
  documento: { tipo: string; numero: string } | null
  telefono: string | null
  suscripcion_id: number | null
  plan: string | null
  placas: string[]
  inicio: string | null
  vence: string | null
  estado: string
  estado_texto: string
  dias_restantes: number | null
  valor: string | null
  pagado: string
  saldo: string
}

export interface ClientesPlanes {
  total: number
  clientes: ClientePlan[]
}

export const mensualidades = {
  crear: (cuerpo: {
    cliente_id: number
    plan: string
    placas: string[]
    inicio: string
    meses: number
    valor: string
    horario?: { desde: string; hasta: string } | null
  }) => http.POST<{ suscripcion_id: number }>('/api/subscriptions', cuerpo),

  detalle: (id: number) => http.GET<{
    suscripcion_id: number
    cliente_id: number
    plan: string
    placas: string[]
    inicio: string
    vence: string
    valor: string
    pagado: string
    saldo: string
    estado: string
  }>(`/api/subscriptions/${id}`),

  pagar: (id: number, metodo: string, monto: string, efectivoRecibido: string | null, referencia: string | null = null) =>
    http.POST<PagoMensualidad>(`/api/subscriptions/${id}/pay`, {
      metodo, monto, efectivo_recibido: efectivoRecibido, referencia,
    }, conClave()),

  /** Una sola transacción: crea el período y cobra. */
  renovar: (
    id: number,
    metodo: string,
    monto: string,
    efectivoRecibido: string | null,
    meses: number,
    referencia: string | null = null,
  ) =>
    http.POST<{
      suscripcion_anterior: number
      suscripcion_nueva: number
      pago_id: number
      inicio: string
      vence: string
    }>(`/api/subscriptions/${id}/renew`, {
      metodo, monto, efectivo_recibido: efectivoRecibido, meses, referencia,
    }, conClave()),

  cancelar: (id: number, motivo: string) =>
    http.POST<unknown>(`/api/subscriptions/${id}/cancel`, { motivo }),

  alertas: (diasAviso = 7, senal?: AbortSignal) =>
    http.GET<{ total: number; alertas: Array<{ suscripcion_id: number; cliente: string; plan: string; vence: string; saldo: string; status: string }> }>(
      `/api/subscriptions/alerts?dias_aviso=${diasAviso}`,
      senal,
    ),
}

export const convenios = {
  crear: (cuerpo: {
    cliente_id: number
    nombre: string
    tipo_descuento: string
    valor: string
    valido_desde: string
    valido_hasta: string | null
  }) => http.POST<{ id?: number }>('/api/agreements', cuerpo),
}
