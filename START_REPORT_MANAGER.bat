@echo off
cd /d "%~dp0"
if not exist "report_manager.local.json" (
 echo Copy examples\report_manager.example.json to report_manager.local.json and set source addresses, certificates and token ENV variables.
 pause
 exit /b 1
)
py -3 -m level3_data.report_manager --config report_manager.local.json --output reports
pause
