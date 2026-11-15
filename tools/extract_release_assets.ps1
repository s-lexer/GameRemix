param(
    [Parameter(Mandatory=$true)][string]$AssemblyPath,
    [Parameter(Mandatory=$true)][string]$Destination,
    [Parameter(Mandatory=$true)][string]$ReleaseSha256
)
$ErrorActionPreference = 'Stop'
# Reflection-only metadata loading does not execute the target application.
$assembly = [Reflection.Assembly]::ReflectionOnlyLoadFrom($AssemblyPath)
$names = @($assembly.GetManifestResourceNames() | Sort-Object)
$resources = @()
$index = 0
foreach ($name in $names) {
    if ($name -notmatch '^[A-Za-z0-9_.-]+$') {
        throw "Unexpected resource name"
    }
    $stream = $assembly.GetManifestResourceStream($name)
    if ($null -eq $stream) { throw "Resource cannot be read: $name" }
    $buf = New-Object System.IO.MemoryStream
    try {
        $stream.CopyTo($buf)
        $bytes = $buf.ToArray()
        $filename = ('{0:d3}.bin' -f $index)
        [IO.File]::WriteAllBytes((Join-Path $Destination $filename), $bytes)
        $sha = [Security.Cryptography.SHA256]::Create()
        try { $hash = [BitConverter]::ToString($sha.ComputeHash($bytes)).Replace('-', '').ToLowerInvariant() }
        finally { $sha.Dispose() }
        $resources += @{ name = $name; filename = $filename; sha256 = $hash; size = $bytes.Length }
        $index++
    } finally {
        $buf.Dispose()
        $stream.Dispose()
    }
}
$manifest = @{ release_sha256 = $ReleaseSha256; resources = $resources }
$json = ConvertTo-Json -InputObject $manifest -Depth 5
[IO.File]::WriteAllText((Join-Path $Destination 'manifest.json'), $json, (New-Object Text.UTF8Encoding($false)))
Write-Output ("Read-only resource extraction: {0} embedded items" -f $resources.Count)
