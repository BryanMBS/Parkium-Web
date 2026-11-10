# 06 — Sistema de diseño y componentes compartidos

Todos los valores están verificados en `app/ui/theme.py` y
`app/ui/branding.py`.

---

## 6.1 Paletas

El tema tiene **dos paletas completas** y una misma estructura de campos, de
modo que ningún componente necesita saber en qué modo está.

### Variables de marca

| Constante | Valor | Uso |
|---|---|---|
| `PURPLE` | `#5B21B6` | Acción principal (modo claro) |
| `LIME` | `#A3E635` | Acento del símbolo |
| `LAVENDER` | `#C4B5FD` | Selección |
| `GREEN` | `#22C55E` | Éxito |
| `ORANGE` | `#F59E0B` | Advertencia |
| `CYAN` | `#06B6D4` | Informativo |
| `RED` | `#EF4444` | Peligro |
| `DARK` | `#1B1F2A` | Encabezado / sidebar |
| `TEXT` | `#111827` | Texto principal |
| `MUTED` | `#64748B` | Texto secundario |
| `WHITE` | `#FFFFFF` | Superficie clara |

### Modo claro

| Rol | Valor |
|---|---|
| `background` | `#F8FAFC` |
| `surface` | `#FFFFFF` |
| `surface_alt` | `#F1F5F9` |
| `sidebar` | `#1B1F2A` |
| `sidebar_text` | `#FFFFFF` |
| `sidebar_muted` | `#94A3B8` |
| `text` | `#111827` |
| `muted` | `#64748B` |
| `border` | `#E2E8F0` |
| `primary` | `#5B21B6` |
| `primary_hover` | `#4C1D95` |
| `on_primary` | `#FFFFFF` |
| `success` / `success_hover` | `#22C55E` / `#16A34A` |
| `warning` | `#F59E0B` |
| `danger` / `danger_hover` | `#EF4444` / `#DC2626` |
| `heading` | `#1B1F2A` |
| `selection` | `#C4B5FD` |
| `field_background` | `#FFFFFF` |
| `field_border` | `#E2E8F0` |

### Modo oscuro

Pensado para turnos de noche con poca luz ambiente.

| Rol | Valor |
|---|---|
| `background` | `#0B1120` |
| `surface` | `#151C2E` |
| `surface_alt` | `#1E293B` |
| `sidebar` | `#020617` |
| `sidebar_text` | `#F1F5F9` |
| `sidebar_muted` | `#94A3B8` |
| `text` | `#E2E8F0` |
| `muted` | `#94A3B8` |
| `border` | `#1E293B` |
| `primary` | `#7C3AED` |
| `primary_hover` | `#6D28D9` |
| `on_primary` | `#FFFFFF` |
| `success` / `success_hover` | `#16A34A` / `#15803D` |
| `warning` | `#FBBF24` |
| `danger` / `danger_hover` | `#F87171` / `#EF4444` |
| `heading` | `#F8FAFC` |
| `selection` | `#312E81` |
| `field_background` | `#151C2E` |
| `field_border` | `#2A3550` |

> **Nota sobre la barra lateral:** es oscura en **ambos** modos. Es una decisión
> de marca, no un descuido.

## 6.2 Implementación en el frontend

```css
/* tokens.css — generado desde las dos paletas */
:root {
  --color-primary: #5B21B6;
  --color-primary-hover: #4C1D95;
  --color-on-primary: #FFFFFF;
  --color-background: #F8FAFC;
  --color-surface: #FFFFFF;
  --color-surface-alt: #F1F5F9;
  --color-sidebar: #1B1F2A;
  --color-text: #111827;
  --color-muted: #64748B;
  --color-border: #E2E8F0;
  --color-success: #22C55E;
  --color-warning: #F59E0B;
  --color-danger: #EF4444;
  --color-heading: #1B1F2A;
  --color-selection: #C4B5FD;
  --color-field-bg: #FFFFFF;
  --color-field-border: #E2E8F0;
}

[data-theme="oscuro"] {
  --color-primary: #7C3AED;
  --color-background: #0B1120;
  /* … el resto de la paleta oscura */
}
```

```ts
// ThemeProvider.tsx
const [modo, setModo] = useState<'claro' | 'oscuro'>(() => {
  const guardado = localStorage.getItem('parkium.tema')
  if (guardado === 'claro' || guardado === 'oscuro') return guardado
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'oscuro' : 'claro'
})
useEffect(() => {
  document.documentElement.dataset.theme = modo
  localStorage.setItem('parkium.tema', modo)
}, [modo])
```

> El original persiste el modo en `runtime/tema.json`
> (`theme.THEME_FILE = "tema.json"`). En la web el equivalente es
> `localStorage`; si se quiere conservar entre dispositivos, añadir una
> preferencia en la API.

## 6.3 Tipografía

`theme.font_family()` pide, en este orden:

| Familia | Uso | Respaldo |
|---|---|---|
| `Poppins` | Títulos y cifras grandes (peso `bold`) | `Segoe UI` |
| `Inter` | Texto de la interfaz | `Segoe UI` |
| `JetBrains Mono` | Comprobantes y texto técnico | `Consolas` |

> **Verificado en la máquina de desarrollo:** `Inter`, `Poppins` y
> `JetBrains Mono` **no están instaladas** y el sistema cae a `Segoe UI` y
> `Consolas`. La web **debe** servir las tipografías por `fontsource` o una
> carpeta propia; si las deja sin cargar, verá la misma degradación.

Escala observada en la interfaz:

| Elemento | Familia | Tamaño | Peso |
|---|---|---|---|
| Título de página | Poppins | 22 | bold |
| Cifra de tarjeta | Poppins | 20 | bold |
| Etiqueta de tarjeta | Inter | 8 | bold |
| Texto normal | Inter | 9–11 | normal |
| Encabezado de sección | Inter | 9 | bold |

## 6.4 Espaciado y medidas

| Medida | Valor | Origen |
|---|---|---|
| Ancho de la barra lateral | 235 px | `nav.place(x=0, y=110, width=235, height=420)` |
| Ancho mínimo de ventana | 1080 × 680 | `app.minsize(1080, 680)` |
| Tamaño por defecto | 1320 × 820 | `app.geometry("1320x820")` |
| Relleno de página | `padx=30, pady=24` | `_clear_body` |
| Relleno de pestaña | `padding=18` | `_show_admin` |
| Relleno de tarjeta | `padding=(14, 10)` | `_build_ficha` |
| Rellengo de botón | `(12, 8)` | `theme.button_base` |
| Botón compacto | `(2, 5)` | `theme.compact_base` |
| Radio de esquina de la tarjeta | 26 px | `branding.compose_login_backdrop` |
| Radio de botón | 12 px | `branding._rounded_overlay` |

## 6.5 Catálogos traducidos

La interfaz muestra nombres en español y envía códigos a los servicios.

```ts
export const TIPOS_VEHICULO = [
  { etiqueta: 'Carro', codigo: 'CAR' },
  { etiqueta: 'Moto', codigo: 'MOTORCYCLE' },
  { etiqueta: 'Bicicleta', codigo: 'BICYCLE' },
]

export const METODOS_PAGO = [
  { etiqueta: 'Efectivo', codigo: 'CASH' },
  { etiqueta: 'Tarjeta', codigo: 'CARD' },
  { etiqueta: 'Transferencia', codigo: 'TRANSFER' },
  { etiqueta: 'Billetera digital', codigo: 'DIGITAL_WALLET' },
]

export const ESQUEMAS_COBRO = [
  { etiqueta: 'Por minuto', codigo: 'MINUTE' },
  { etiqueta: 'Por hora', codigo: 'HOUR' },
  { etiqueta: 'Por fracción de hora', codigo: 'HOUR_FRACTION' },
  { etiqueta: 'Valor fijo al ingresar', codigo: 'FLAT_ENTRY' },
  { etiqueta: 'Por bloques', codigo: 'BLOCKS' },
  { etiqueta: 'Por día', codigo: 'DAY' },
  { etiqueta: 'Nocturno', codigo: 'NIGHT' },
]

export const ROLES = [
  { etiqueta: 'Operador', codigo: 'OPERATOR' },
  { etiqueta: 'Administrador', codigo: 'ADMIN' },
  { etiqueta: 'Super administrador', codigo: 'SUPERADMIN' },
]

export const ESTADOS_SUSCRIPCION = {
  ACTIVE: 'VIGENTE',
  EXPIRING: 'POR VENCER',
  EXPIRED: 'VENCIDA',
  CANCELLED: 'CANCELADA',
  NO_PLAN: 'SIN PLAN',
}

export const ETIQUETAS_HORA = ['Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sá', 'Do']
```

> `_method_code()` y `_vehicle_code()` convierten etiqueta → código, y si el
> texto no está en el catálogo devuelven el valor en mayúsculas, de modo que un
> dato técnico siga funcionando. Replicar esa tolerancia.

## 6.6 Componentes reutilizables

Los equivalentes a los estilos de `theme.configure`:

| Componente | Estilos ttk originales | Variantes |
|---|---|---|
| `Button` | `Primary.TButton`, `PrimaryHover.TButton`, `Secondary.TButton`, `Success.TButton`, `Danger.TButton`, `Ghost.TButton`, `BrandGhost.TButton`, `Compact.TButton`, `CompactActive.TButton` | primaria, éxito, peligro, fantasma, compacta |
| `Label` | `TLabel`, `Card.TLabel`, `Muted.TLabel`, `CardMuted.TLabel`, `Error.TLabel`, `Success.TLabel`, `Warning.TLabel`, `Title.TLabel`, `Subtitle.TLabel`, `CardTitle.TLabel`, `CardValue.TLabel` | — |
| `Entry` | `TEntry`, `Brand.TEntry` | normal, del login |
| `Frame` | `TFrame`, `Card.TFrame` | — |
| `Combobox`, `Checkbutton`, `Treeview` | ttk por defecto | — |

### Comportamientos que hay que conservar

- **Hover de botón**: al entrar cambia de estilo; sale, vuelve. En CSS es
  `:hover`, sin trabajo extra.
- **Borde de foco**: el campo del login cambia el borde a `primary` mientras
  tiene el foco.
- **Foco visible siempre**: el original **no** dibuja contorno de foco en los
  botones de la barra lateral. En la web hay que añadirlo: es un requisito de
  accesibilidad y no cuesta nada.
- **Botones deshabilitados**: se deshabilitan por rol **y** por estado de la
  fila seleccionada.

## 6.7 Iconografía

La barra lateral usa caracteres, no imágenes:

| Icono | Vista | Color |
|---|---|---|
| `▦` | Dashboard | `primary` |
| `↦` | Entradas y salidas | `sidebar_muted` → `primary` activo |
| `▤` | Histórico | |
| `◈` | Mensualidades | |
| `⚙` | Configuración | |
| `◫` | Reportes | |
| `▦` | Calendario (emergente) | `primary` sobre `surface_alt` |

> El glifo del calendario debe ser **visible**: con color apagado el operador no
> lo ve y acaba escribiendo la fecha a mano, que es justo lo que el calendario
> evita.

## 6.8 El login con cristal

Es la pieza visual más particular y hay que decidir su equivalente.

### Qué hace el original

1. `compose_login_backdrop` **precompone** con Pillow una imagen: fotografía
   + velo de tema + cristal + sombra + borde.
2. Tk sólo la pinta. Tkinter **no compone transparencia entre widgets**, así
   que precomponer es la única forma de tener un cristal real.
3. Cada etiqueta toma **del cristal el color de su propia franja** con
   `Glass.color_at`, de modo que el texto flota sobre el vidrio sin dejar un
   rectángulo visible.
4. `Glass.logo_photo` pega el símbolo sobre un recorte real del cristal, para
   que no salga la caja blanca que Tk dibuja donde el PNG es transparente.
5. La tarjeta se coloca en el **reparto de dos columnas**: al 55,5 % del ancho,
   de modo que la marca de la imagen de fondo se ve completa a la izquierda.

### Equivalente web

| Técnica | Descripción |
|---|---|
| **Opción A — Cristal CSS** | `backdrop-filter: blur(20px)` con fondo semitransparente. Nativa, sin imágenes. **No funciona en Firefox sin bandera** y rinde peor en móviles de gama baja. |
| **Opción B — Imagen precompuesta** | Igual que el original: el backend genera el PNG y el frontend lo pinta como fondo. Idéntico, pero obliga a un endpoint. |
| **Opción C — Híbrida** | Cristal CSS donde se pueda y degradado plano como respaldo. |

**Recomendación: opción C.** El fondo se sirve como imagen estática
(`login_bg.jpg`), el cristal se hace con `backdrop-filter` y un `@supports not
(backdrop-filter: blur(1px))` que degrada a un fondo translúcido plano.

### Material del cristal

Leído de `_glass_surface`, cuatro capas:

1. Tinte en degradado, más claro arriba.
2. Reflejo especular en diagonal, muy tenue.
3. Grano fino con alfa variable (gris neutro: aclara y oscurece a la vez).
4. Canto interior más intenso arriba que abajo.

> **Por qué no basta con desenfocar la foto.** La zona de la imagen bajo la
> tarjeta tiene una desviación de color de **menos de 2 niveles**: es un
> degradado plano y casi negro. Desenfocarla no produce ninguna textura por mucho
> que se ajuste el relleno. El material tiene que construirse.

### Reglas de layout

| Medida | Valor |
|---|---|
| Ancho de la tarjeta | 440 px |
| Alto mínimo | 520 px |
| Margen a los bordes | 48 px |
| Centro de la columna | 55,5 % del ancho |
| Ancho mínimo para el reparto | 1040 px (por debajo, se centra) |
| Radio de esquina | 26 px |

## 6.9 Gráfico de ocupación

```tsx
// Reglas verificadas en app/ui/occupancy_chart.py
const ALTO_GRAFICO = 190          // área de dibujo, sin ejes
const ETIQUETAS_HORA = ['00','03','06','09','12','15','18','21']  // de tres en tres
```

- Escala vertical = `_escala(máximo)`: 1-2-3-5 por potencia de diez.
- Número de líneas de rejilla = el mayor divisor de `(5,4,3,2)` que divida el
  tope, para que las etiquetas salgan redondas.
- El tope **no** es la capacidad total: con 30 cupos y 4 vehículos la curva se
  aplasta. La capacidad se dibuja como línea de referencia si cabe, y siempre en
  el rótulo superior.
- El ratón sigue con una línea vertical; al salir desaparece.

## 6.10 Calendario emergente

Reglas de `app/ui/calendar_popup.py` que hay que conservar:

| Regla | Detalle |
|---|---|
| Formato de salida | `YYYY-MM-DD` |
| Semana | Empieza en **lunes** |
| Días atenuados | Fuera del mes, fines de semana y fuera del rango permitido |
| Botones | «Hoy» y «Cancelar» |
| Escritura manual | El campo **sigue** aceptando texto; el calendario abre en lo escrito |
| Formatos leídos | `2026-10-06`, `06/10/2026`, `06.10.2026`, `6-10-26` |
| Clic en campo vacío | Abre el calendario; con texto, coloca el cursor |

> La lectura por posición del año, no por máscara a ciegas: `6-10-26` es 6 de
> octubre, no 26 de octubre del 2006.

## 6.11 Accesibilidad

El original **no** la implementa (es Tkinter). La web debe añadirla:

| Requisito | Aplicación |
|---|---|
| Contraste | Mínimo 4,5:1 en texto normal y 3:1 en grande. Revisar `muted` sobre `surface`. |
| Foco visible | Nunca `outline: none` sin sustituto. |
| Navegación por teclado | Toda la aplicación debe ser operable sin ratón, incluidos los diálogos. |
| Etiquetas de formulario | `<label>` real, no `placeholder` como sustituto. |
| Anuncios | El cambio de la cotización y el resultado del cobro deben anunciarse a lectores de pantalla (`aria-live`). |
| Errores | Además del color, un texto y un icono; el color solo no basta. |
| Objetivos táctiles | Mínimo 44 × 44 px en móvil. |
| Respeta `prefers-reduced-motion` | Sin transiciones cuando se pide. |

## 6.12 Formato numérico

**Los importes viajan como cadena y se formatean en el cliente** con
`Intl.NumberFormat('es-CO')`.

```ts
const fmt = new Intl.NumberFormat('es-CO', {
  style: 'currency', currency: 'COP', minimumFractionDigits: 2,
})
fmt.format(45000)   // $45.000,00
```

> El original imprime `$45,000.00` (formato inglés) porque usa
> `f"{valor:,.2f}"`. **La web debe usar el formato colombiano**, que es lo que el
> operador espera ver. Es una diferencia deliberada y deseable: es una mejora,
> no un desvío.

Lo que **no** se puede cambiar: los importes viajan como **cadena decimal** en
JSON. Un número de JavaScript no representa `$45,000.00` de forma exacta y el
redondeo en los cobros no es aceptable.