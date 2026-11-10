import { http, nuevaClaveIdempotencia } from './client'

export interface Cotizacion {
  estadia_id: number
  placa: string
  entrada_local: string
  salida_local: string
  minutos: number
  esquema: string
  monto: string
  descuento: string
  monto_a_cobrar: string
  mensualidad_vigente?: boolean
}

export interface ReciboRef {
  id: number
  numero?: number
  receipt_number?: number
  tipo?: string
  token?: string
}

export interface EntradaResult {
  estadia_id: number
  placa: string
  ingreso: string
  ingreso_local: string
  recibo: ReciboRef
}

export interface CobroResult {
  pago_id: number
  estadia_id: number
  estado: string
  monto: string
  efectivo_recibido: string | null
  cambio: string | null
  recibo: ReciboRef
  idempotente?: boolean
}

export interface Ocupacion {
  capacidad_total: number
  ocupados: number
  disponibles: number
  por_tipo: Record<string, number>
}

export interface Dashboard {
  ocupacion: Ocupacion
  hoy: { ingresos: string; salidas_cobradas: number; mensualidades: string }
  generado_en: string
}

export interface EstadiaActiva {
  estadia_id: number
  placa: string | null
  ingreso_local: string
  estado: string
}

export const parking = {
  /** Registro de entrada; normaliza placa y crea el vehículo si no existe. */
  entrada: (placa: string, tipoVehiculo: string) =>
    http.POST<EntradaResult>('/api/stays', { placa, tipo_vehiculo: tipoVehiculo }),

  /** 404 si no hay estadía activa. */
  estadíaActiva: (placa: string) =>
    http.GET<EstadiaActiva>(`/api/stays/active?placa=${encodeURIComponent(placa)}`),

  /** Cotiza la salida; NO cierra la estadía. */
  cotizar: (placa: string) => http.GET<Cotizacion>(`/api/stays/${encodeURIComponent(placa)}/quote`),

  /** Cobro transaccional; la cabecera Idempotency-Key respeta docs/04 §4.3:
   * la misma clave devuelve el pago existente en vez de duplicar. */
  cobrar: (
    placa: string,
    metodo: string,
    monto: string | null,
    efectivoRecibido: string | null,
    referencia: string | null = null,
    clave: string = nuevaClaveIdempotencia(),
  ) =>
    http.POST<CobroResult>(
      '/api/checkout',
      {
        placa,
        metodo,
        monto: monto ?? undefined,
        efectivo_recibido: efectivoRecibido,
        referencia,
      },
      { 'Idempotency-Key': clave },
    ),

  anular: (pagoId: number, motivo: string) =>
    http.POST<unknown>(`/api/payments/${pagoId}/void`, { motivo }),

  ocupacion: () => http.GET<Ocupacion>('/api/occupancy'),
  dashboard: () => http.GET<Dashboard>('/api/dashboard'),
}
