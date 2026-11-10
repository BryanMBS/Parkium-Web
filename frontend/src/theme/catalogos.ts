/** Catálogos traducidos (docs/06 §6.5).
 * La interfaz muestra nombres en español y envía códigos a los servicios.
 * Si el texto no está en el catálogo se devuelve el valor en MAYÚSCULAS,
 * tolerancia replicada del original. */

export interface OpcionCatalogo {
  etiqueta: string
  codigo: string
}

export const TIPOS_VEHICULO: OpcionCatalogo[] = [
  { etiqueta: 'Carro', codigo: 'CAR' },
  { etiqueta: 'Moto', codigo: 'MOTORCYCLE' },
  { etiqueta: 'Bicicleta', codigo: 'BICYCLE' },
]

export const METODOS_PAGO: OpcionCatalogo[] = [
  { etiqueta: 'Efectivo', codigo: 'CASH' },
  { etiqueta: 'Tarjeta', codigo: 'CARD' },
  { etiqueta: 'Transferencia', codigo: 'TRANSFER' },
  { etiqueta: 'Billetera digital', codigo: 'DIGITAL_WALLET' },
]

export const ESQUEMAS_COBRO: OpcionCatalogo[] = [
  { etiqueta: 'Por minuto', codigo: 'MINUTE' },
  { etiqueta: 'Por hora', codigo: 'HOUR' },
  { etiqueta: 'Por fracción de hora', codigo: 'HOUR_FRACTION' },
  { etiqueta: 'Valor fijo al ingresar', codigo: 'FLAT_ENTRY' },
  { etiqueta: 'Por bloques', codigo: 'BLOCKS' },
  { etiqueta: 'Por día', codigo: 'DAY' },
  { etiqueta: 'Nocturno', codigo: 'NIGHT' },
]

export const ROLES: OpcionCatalogo[] = [
  { etiqueta: 'Operador', codigo: 'OPERATOR' },
  { etiqueta: 'Administrador', codigo: 'ADMIN' },
  { etiqueta: 'Super administrador', codigo: 'SUPERADMIN' },
]

export const ESTADOS_SUSCRIPCION: Record<string, string> = {
  ACTIVE: 'VIGENTE',
  EXPIRING: 'POR VENCER',
  EXPIRED: 'VENCIDA',
  CANCELLED: 'CANCELADA',
  NO_PLAN: 'SIN PLAN',
}

/** fix UX-S023: estados internos de las estadías traducidos en la UI. */
export const ESTADOS_ESTADIA: Record<string, string> = {
  ACTIVE: 'ACTIVA',
  PENDING_PAYMENT: 'PENDIENTE DE PAGO',
  PAID: 'COBRADA',
  CANCELLED: 'ANULADA',
  ANULADA: 'ANULADA',
  VOID: 'ANULADA',
}

export const ETIQUETAS_HORA = ['Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sá', 'Do']

/** etiqueta → código, con la tolerancia del original (no está: en MAYÚSCULAS) */
export function aCodigo(lista: OpcionCatalogo[], texto: string | undefined): string {
  if (!texto) return ''
  const hallado = lista.find((o) => o.etiqueta === texto || o.codigo === texto)
  return hallado ? hallado.codigo : texto.toUpperCase()
}

export function etiquetaDe(lista: OpcionCatalogo[], codigo: string | undefined): string {
  if (!codigo) return ''
  const hallado = lista.find((o) => o.codigo === codigo)
  return hallado ? hallado.etiqueta : codigo
}
