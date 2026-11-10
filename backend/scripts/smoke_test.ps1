# Prueba de humo end-to-end del backend (docs/11 §11.1). Ejecutar:
#   powershell -ExecutionPolicy Bypass -File backend/scripts/smoke_test.ps1
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$base = if ($env:PARKIUM_BASE_URL) { $env:PARKIUM_BASE_URL } else { 'http://127.0.0.1:8000' }
$enhe = [char]0xF1  # el .ps1 sin BOM se parsea como ANSI en Windows PowerShell 5.1

function PostJSON($url, $json, $sess, $headers = @{}) {
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
  if ($sess) {
    return Invoke-RestMethod -Uri $url -Method Post -Body $bytes -ContentType 'application/json' -WebSession $sess -Headers $headers
  }
  return Invoke-RestMethod -Uri $url -Method Post -Body $bytes -ContentType 'application/json' -Headers $headers
}
function GetJSON($url, $sess) { return Invoke-RestMethod -Uri $url -WebSession $sess }

Write-Host "== health =="
GetJSON "$base/api/health"

Write-Host "== login =="
$body = ('{{"usuario":"admin","contrase{0}a":"Cambiame.123"}}' -f $enhe)
$sess = $null
Invoke-RestMethod -Uri "$base/api/auth/login" -Method Post -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) -ContentType 'application/json; charset=utf-8' -SessionVariable sess | ConvertTo-Json -Depth 5

# placa única por corrida: el duplicado se verifica con la misma placa
$plate = ('T' + (Get-Random -Minimum 10000 -Maximum 99999) + (Get-Random -Minimum 10 -Maximum 99))
$plate = $plate.Substring(0, [Math]::Min(6, $plate.Length))
Write-Host "== placa de prueba: $plate =="

Write-Host "== registrar entrada =="
PostJSON "$base/api/stays" ('{{"placa":"{0}","tipo_vehiculo":"CAR"}}' -f $plate) $sess | ConvertTo-Json -Depth 5

Write-Host "== entrada duplicada (debe dar 409) =="
try { PostJSON "$base/api/stays" ('{{"placa":"{0}"}}' -f $plate) $sess } catch { $_.Exception.Response.StatusCode.value__ }

Write-Host "== cotizar (no cierra la estadía) =="
GetJSON "$base/api/stays/$plate/quote" $sess | ConvertTo-Json -Depth 5

Write-Host "== abrir caja =="
try {
  PostJSON "$base/api/cash/shifts" '{"monto_inicial":"50000.00"}' $sess | ConvertTo-Json -Depth 5
} catch {
  Write-Host "(turno ya abierto, se reutiliza)"
  GetJSON "$base/api/cash/shifts" $sess | ConvertTo-Json -Depth 5
}

Write-Host "== cobrar efectivo con idempotencia =="
$idem = ('smoketest-' + [guid]::NewGuid().ToString('N').Substring(0,8))
$ck = ('{{"placa":"{0}","metodo":"CASH","efectivo_recibido":"10000.00"}}' -f $plate)
PostJSON "$base/api/checkout" $ck $sess @{ 'Idempotency-Key' = $idem } | ConvertTo-Json -Depth 5

Write-Host "== repetir la misma Idempotency-Key (no cobra dos veces) =="
PostJSON "$base/api/checkout" $ck $sess @{ 'Idempotency-Key' = $idem } | ConvertTo-Json -Depth 5

Write-Host "== dashboard =="
GetJSON "$base/api/dashboard" $sess | ConvertTo-Json -Depth 5

Write-Host "== estado del reloj =="
GetJSON "$base/api/clock/status" $sess | ConvertTo-Json -Depth 5

Write-Host "== importe insuficiente (debe 400 con faltante) =="
# Nota PS 5.1: -WebSession pega las cabeceras previas; se envía una clave única
# explícita para no heredar la Idempotency-Key del cobro anterior (defecto del
# cliente, no del servidor: el servidor confirma el conflicto si se reusa).
$xin = ('{{"placa":"XX{0}","metodo":"CASH","efectivo_recibido":"1.00"}}' -f (Get-Random -Maximum 99999))
$kfalt = ('faltante-' + [guid]::NewGuid().ToString('N').Substring(0,8))
try { PostJSON "$base/api/checkout" $xin $sess @{ 'Idempotency-Key' = $kfalt } } catch { $_.ErrorDetails.Message }

