param([Parameter(Mandatory=$true)][string]$Deck, [Parameter(Mandatory=$true)][string]$RenderDir)
$ErrorActionPreference = 'Stop'
$deckPath = (Resolve-Path -LiteralPath $Deck).Path
[void][System.IO.Directory]::CreateDirectory($RenderDir)
$renderPath = (Resolve-Path -LiteralPath $RenderDir).Path
$app = $null
$presentation = $null
try {
    $app = New-Object -ComObject PowerPoint.Application
    # Open read-only, without a visible presentation window. Never alter a source deck.
    $presentation = $app.Presentations.Open($deckPath, -1, 0, 0)
    $errors = @()
    foreach ($slide in $presentation.Slides) {
        foreach ($shape in $slide.Shapes) {
            if ($shape.HasTable) {
                for ($row = 1; $row -le $shape.Table.Rows.Count; $row++) {
                    for ($column = 1; $column -le $shape.Table.Columns.Count; $column++) {
                        $cell = $shape.Table.Cell($row, $column).Shape
                        $cellText = $cell.TextFrame.TextRange
                        if ($cellText.BoundHeight -gt ($cell.Height + 2) -or $cellText.BoundWidth -gt ($cell.Width + 2)) {
                            $errors += "Slide $($slide.SlideIndex): table cell $row,$column overflows"
                        }
                    }
                }
            }
            if ($shape.HasTextFrame -and $shape.TextFrame.HasText) {
                $range = $shape.TextFrame.TextRange
                if ($range.BoundHeight -gt ($shape.Height + 2) -or $range.BoundWidth -gt ($shape.Width + 2)) {
                    $errors += "Slide $($slide.SlideIndex): text exceeds shape $($shape.Name)"
                }
            }
        }
        $slide.Export((Join-Path $renderPath ('slide-{0:D3}.png' -f $slide.SlideIndex)), 'PNG', 1600, 900)
    }
    if ($errors.Count) { throw ($errors -join "`n") }
    $presentation.SaveAs((Join-Path $renderPath 'slides.pdf'), 32)
    @{renderer='Microsoft PowerPoint'; slides=$presentation.Slides.Count; overflow_errors=$errors} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $renderPath 'renderer.json') -Encoding utf8
} finally {
    if ($presentation) { $presentation.Close(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($presentation) }
    if ($app) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($app) }
    # Do not Quit: another user presentation may share the COM application.
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
