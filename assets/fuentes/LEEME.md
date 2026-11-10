# Tipografías de marca

Esta carpeta es **opcional** y está vacía a propósito: las tipografías de la
marca (Poppins, Inter y JetBrains Mono) son de licencia abierta —SIL Open Font
License— pero no se redistribute dentro del repositorio para no mezclarlas con
el código.

## Qué hace la aplicación

Al arrancar, `app/ui/theme.py` mira esta carpeta y registra en Tk las familias
que encuentre:

| Familia | Archivo esperado | Uso en la interfaz |
|---|---|---|
| Poppins | `Poppins-Regular.ttf`, `Poppins-SemiBold.ttf`, `Poppins-Bold.ttf` | Títulos y encabezados |
| Inter | `Inter-Regular.ttf`, `Inter-SemiBold.ttf`, `Inter-Bold.ttf` | Texto de la interfaz |
| JetBrains Mono | `JetBrainsMono-Regular.ttf`, `JetBrainsMono-Bold.ttf` | Placas e importes |

Basta con **copiar aquí los archivos `.ttf`** de las tres familias: no hay que
tocar el código ni la configuración. Si un archivo falta, se usa el siguiente de
la lista; si no hay ninguno, la aplicación cae en el respaldo del sistema
(Segoe UI y Consolas) y sigue funcionando.

## Cómo CONSEGUIRLAS

- Poppins: <https://fonts.google.com/specimen/Poppins>
- Inter: <https://rsms.me/inter/>
- JetBrains Mono: <https://www.jetbrains.com/lp/mono/>

Cada familia se distribuye con su licencia dentro del archivo; conviene copied
también el `OFL.txt` de cada una.

## Empaquetado

`parkium.spec` tiene que incluir la carpeta para que el ejecutable la lleve.
La sección `datas` ya recoge `assets`; si algún día se decide no empaquetar los
archivos, basta con quitar esta carpeta de la lista.
