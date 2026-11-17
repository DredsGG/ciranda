param([string]$Caminho)
Add-Type -AssemblyName System.Windows.Forms
$f = New-Object System.Windows.Forms.Form
$f.Text = "Fonte de arrasto (teste)"
$f.StartPosition = "Manual"
$f.Location = New-Object System.Drawing.Point(200, 300)
$f.Size = New-Object System.Drawing.Size(320, 220)
$f.TopMost = $true
$f.Add_MouseDown({
    $lista = New-Object System.Collections.Specialized.StringCollection
    [void]$lista.Add($Caminho)
    $d = New-Object System.Windows.Forms.DataObject
    $d.SetFileDropList($lista)
    $r = $f.DoDragDrop($d, [System.Windows.Forms.DragDropEffects]::Copy)
    [Console]::Out.WriteLine("efeito: $r")
    $f.Close()
})
$t = New-Object System.Windows.Forms.Timer
$t.Interval = 30000
$t.Add_Tick({ $f.Close() })
$t.Start()
[void]$f.ShowDialog()
