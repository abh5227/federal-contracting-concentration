# Render a .pptx to PDF with the installed PowerPoint, then to one JPEG per slide with pdftoppm, for visual checks.
#   powershell -File tools\eda_deck\render.ps1 -Deck reports\eda\eda_presentation.pptx -OutDir D:\Temp\deck_render
param([Parameter(Mandatory)] [string] $Deck, [Parameter(Mandatory)] [string] $OutDir)
$deckPath = (Resolve-Path $Deck).Path
New-Item -ItemType Directory -Force $OutDir | Out-Null
$pdf = Join-Path $OutDir "deck.pdf"
$app = New-Object -ComObject PowerPoint.Application
try {
    $pres = $app.Presentations.Open($deckPath, $true, $false, $false)   # read-only, no window
    $pres.SaveAs($pdf, 32)                                               # 32 = ppSaveAsPDF
    $pres.Close()
} finally {
    $app.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
}
Get-ChildItem $OutDir -Filter "slide-*.jpg" | Remove-Item
& pdftoppm -jpeg -r 110 $pdf (Join-Path $OutDir "slide")
Get-ChildItem $OutDir -Filter "slide-*.jpg" | ForEach-Object FullName
