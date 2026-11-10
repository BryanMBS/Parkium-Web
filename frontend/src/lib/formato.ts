/* Los importes viajan como cadena decimal (docs/06 §6.12) y se formatean
 * en el cliente con es-CO; jamás se redondea en el servidor. */

const fmt = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 2,
})

export function dinero(cadena: string | number | null | undefined): string {
  if (cadena === null || cadena === undefined || cadena === '') return '—'
  // La cadena es exacta; Number sólo para el formateador (pantalla).
  return fmt.format(typeof cadena === 'string' ? Number(cadena) : cadena)
}

/** Normaliza un pedido del operador a cadena decimal: "10" -> "10.00",
 * "10,5" -> "10.50". Devuelve null si no es parseable. */
export function aImporte(texto: string | number | null | undefined): string | null {
  if (textonulo(texto)) return null
  let s = String(texto).trim().replace(/\s/g, '')
  // formato colombiano tecleado: puntos de miles y coma decimal
  if (/^-?\d{1,3}(\.\d{3})+(,\d+)?$/.test(s)) s = s.replace(/\./g, '').replace(',', '.')
  else s = s.replace(',', '.')
  if (!/^-?\d+(\.\d+)?$/.test(s)) return null
  const [ent, dec] = s.split('.')
  return `${ent}.${(dec ?? '').padEnd(2, '0').slice(0, 2) || '00'}`
}

function textonulo(v: string | number | null | undefined): boolean {
  return v === null || v === undefined || String(v).trim() === ''
}
