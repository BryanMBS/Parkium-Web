import { http } from './client'

export interface ResultadoHistorico {
  estadia_id: number
  placa: string
  tipo_vehiculo: string
  celda: string | null
  fecha_ingreso: string
  hora_ingreso: string
  fecha_salida: string | null
  hora_salida: string | null
  estado: string
  monto: string | null
  duracion_minutos: number | null
  recibo_ingreso: { id: number; numero: number; puede_reimprimir: boolean } | null
  recibo_salida: { id: number; numero: number; puede_reimprimir: boolean } | null
}

export interface HistoricoRespuesta {
  total: number
  resultados: ResultadoHistorico[]
}

export interface PuntoHourly {
  hora: number
  ocupados: number
  por_tipo: Record<string, number>
}

export interface HourlyRespuesta {
  fecha: string
  capacidad_total: number
  puntos: PuntoHourly[]
  maximo: number
}

export interface DetalleHourly {
  fecha: string
  hora: number
  vehiculos: Array<{
    estadia_id: number
    placa: string
    tipo_vehiculo: string
    celda: string | null
    ingreso_local: string
    horas_dentro: number
    estado: string
  }>
}

export interface VistapreviaRecibo {
  id: number
  numero: number
  tipo: string
  lineas: string[]
  url_qr?: string
  token?: string
}

export const historico = {
  buscar: (
    filtros: {
      placa?: string
      desde?: string
      hasta?: string
      estado?: string
      tipo_vehiculo?: string
      limite?: number
    },
    senal?: AbortSignal,
  ) => {
    const p = new URLSearchParams()
    for (const [k, v] of Object.entries(filtros)) if (v) p.set(k, String(v))
    return http.GET<HistoricoRespuesta>(`/api/history?${p.toString()}`, senal)
  },
  ocupacionPorHora: (fecha: string, senal?: AbortSignal) =>
    http.GET<HourlyRespuesta>(`/api/occupancy/hourly?fecha=${fecha}`, senal),
  ocupacionDetalle: (fecha: string, hora: number, senal?: AbortSignal) =>
    http.GET<DetalleRespuestaHora>(`/api/occupancy/detail?fecha=${fecha}&hora=${hora}`, senal),
}

export type DetalleRespuestaHora = DetalleHourly

export interface PuntoHistorico24 {
  hora: number
  ocupados: number
  por_tipo: Record<string, number>
}

export const comprobantes = {
  vistaPrevia: (id: number) => http.GET<VistapreviaRecibo>(`/api/receipts/${id}/preview`),
  reimprimir: (id: number, tipo: string) =>
    http.POST<{ mensaje?: string; cadena?: string }>(`/api/receipts/${id}/reprint`, { tipo }),
}

export const reloj = {
  estado: (enal?: AbortSignal) => http.GET<EstadoReloj>('/api/clock/status', enal),
  verificar: (usarRed = true) => http.POST<EstadoReloj>('/api/clock/verify', { usar_red: usarRed }),
}

export interface EstadoReloj {
  ok: boolean
  verificada: boolean
  fuente: string
  hora_sistema: string
  hora_referencia: string
  deriva_segundos: number
  deriva_texto: string
  verificaciones_sospechosas: number
  mensaje: string
}
