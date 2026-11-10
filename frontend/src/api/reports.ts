import { http } from './client'

export interface ResumenReportes {
  rotacion: string
  mensualidades: string
  total?: string
  por_metodo: Array<{ etiqueta: string; valor: string; cantidad: number }>
  por_tipo_vehiculo: Array<{ etiqueta: string; valor: string; cantidad: number }>
  por_empleado: Array<{ etiqueta: string; valor: string; cantidad: number }>
  por_tarifa: Array<{ etiqueta: string; valor: string; cantidad: number }>
}

export const reportes = {
  resumen: (desde: string, hasta: string, senal?: AbortSignal) =>
    http.GET<ResumenReportes>(`/api/reports/summary?desde=${desde}&hasta=${hasta}`, senal),
}
