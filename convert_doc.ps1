$word = New-Object -ComObject Word.Application
$word.Visible = $false
$doc = $word.Documents.Open('C:\Users\DayMer\AppData\Local\Temp\thesis_template.doc')
$doc.SaveAs([ref]'F:\bishe\tmp_template_converted.txt', [ref]4)
$doc.Close()
$word.Quit()
Write-Host "Done"
