import { http } from './client'

export interface TurnoCaja {
  id: number
  site_id: number
  user_id: number
  opened_at: string
  closed_at: string | null
  opening_amount: number
  expected_amount: string | null
  counted_amount: string | null
  difference_amount: string | null
  status: 'OPEN' | 'CLOSED'
  username?: string
}

export interface CajaEsperado {
  turno_id: number
  esperado: string
  apertura: string
  cobros_efectivo: number
}

export const caja = {
  abrir: (montoInicial: string) =>
    http.POST<TurnoCaja>('/api/cash/shifts', { monto_inicial: montoInicial }),
  listar: (soloAbiertos = true, senal?: AbortSignal) =>
    http.GET<{ total?: number } | TurnoCaja[]>(
      `/api/cash/shifts${soloAbiertos ? '?abiertos=true' : ''}`,
      senal,
    ) as Promise<TurnoCaja[]>,
  esperado: (turnoId: number) => http.GET<CajaEsperado>(`/api/cash/shifts/${turnoId}/expected`),
  cerrar: (turnoId: number, montoContado: string) =>
    http.POST<{ esperado: string; contado: string; diferencia: string; estado: string }>(
      `/api/cash/shifts/${turnoId}/close`,
      { monto_contado: montoContado },
    ),
}
