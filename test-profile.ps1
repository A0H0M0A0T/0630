. 'D:\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1'
node -e "console.log('MODEL:', process.env.ANTHROPIC_MODEL); console.log('URL:', process.env.ANTHROPIC_BASE_URL); console.log('TOKEN:', process.env.ANTHROPIC_AUTH_TOKEN ? 'OK' : 'MISSING')"
Write-Host "Profile 配置已生效！现在直接输入 claude 即可启动" -ForegroundColor Green
