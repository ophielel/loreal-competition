$ErrorActionPreference = 'Stop'
$ppt = New-Object -ComObject PowerPoint.Application
try {
  $deck = Get-ChildItem "$PSScriptRoot\..\deliverables" -Filter '*.pptx' | Select-Object -First 1
  if (-not $deck) { throw 'No generated PPTX found' }
  $path = $deck.FullName
  $pdf = [System.IO.Path]::ChangeExtension($path, '.pdf')
  $presentation = $ppt.Presentations.Open($path, $true, $false, $false)
  $presentation.SaveAs($pdf, 32)
  $presentation.Close()
} finally {
  $ppt.Quit()
}
