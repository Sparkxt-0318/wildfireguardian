# WildfireGuardian offline: serves this folder at http://localhost:8840 (Windows, no install) and opens the browser.
# With a hotspot, the 3D satellite view in navigation works too.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$port = 8840
$types = @{ '.html'='text/html; charset=utf-8'; '.js'='text/javascript; charset=utf-8'; '.css'='text/css; charset=utf-8'; '.json'='application/json';
  '.png'='image/png'; '.jpg'='image/jpeg'; '.webp'='image/webp'; '.svg'='image/svg+xml'; '.txt'='text/plain; charset=utf-8'; '.woff2'='font/woff2' }
$l = New-Object System.Net.HttpListener
$l.Prefixes.Add("http://localhost:$port/")
try { $l.Start() } catch { Write-Host "Port $port is busy: is the demo already open? Opening the browser."; try { Start-Process "http://localhost:$port/" } catch { }; Read-Host "Press Enter to close"; exit }
Write-Host "WildfireGuardian: http://localhost:$port/  (close this window to stop)"
try { Start-Process "http://localhost:$port/" } catch { Write-Host "Open http://localhost:$port/ in Chrome or Edge." }
while ($l.IsListening) {
  try {
  $c = $l.GetContext(); $p = [Uri]::UnescapeDataString($c.Request.Url.AbsolutePath.TrimStart('/'))
  if ($p -eq '') { $p = 'index.html' }
  $f = [IO.Path]::GetFullPath((Join-Path $root $p))
  if ($f.StartsWith($root) -and (Test-Path $f -PathType Leaf)) {
    $b = [IO.File]::ReadAllBytes($f); $e = [IO.Path]::GetExtension($f).ToLower()
    $c.Response.ContentType = $(if ($types.ContainsKey($e)) { $types[$e] } else { 'application/octet-stream' })
    $c.Response.ContentLength64 = $b.Length; $c.Response.OutputStream.Write($b, 0, $b.Length)
  } else { $c.Response.StatusCode = 404 }
  $c.Response.Close()
  } catch { Write-Host "request failed: $($_.Exception.Message)" }
}
