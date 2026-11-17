@echo off
rem Run this ONCE (double-click). It makes Windows run run_on_pc.bat every morning at 05:45,
rem or as soon as possible after that if the PC was off or asleep.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$a = New-ScheduledTaskAction -Execute '%~dp0run_on_pc.bat' -WorkingDirectory '%~dp0';" ^
  "$t = New-ScheduledTaskTrigger -Daily -At 05:45;" ^
  "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30);" ^
  "Register-ScheduledTask -TaskName 'Bonusscanner' -Action $a -Trigger $t -Settings $s -Force | Out-Null;" ^
  "Write-Host 'Done: Bonusscanner will run every morning at 05:45.'"
pause
