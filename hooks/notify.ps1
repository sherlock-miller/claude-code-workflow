# notify.ps1 -- Claude Code Stop Hook
# Toast notification + sound alert

# Layer 1: Windows Toast notification (native, auto-dismiss)
try {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

    $AppId = "Claude Code"
    $regPath = "HKCU:\Software\Classes\AppUserModelId\$AppId"
    if (!(Test-Path $regPath)) {
        New-Item -Path $regPath -Force | Out-Null
        New-ItemProperty -Path $regPath -Name DisplayName -Value "Claude Code" -PropertyType String -Force | Out-Null
        New-ItemProperty -Path $regPath -Name ShowInSettings -Value 0 -PropertyType DWORD -Force | Out-Null
    }

    $toastXml = [Windows.Data.Xml.Dom.XmlDocument]::New()
    $toastXml.LoadXml(@"
<toast duration="short" scenario="default">
    <visual>
        <binding template="ToastGeneric">
            <text>Claude Code</text>
            <text>Task completed - needs your input</text>
        </binding>
    </visual>
    <audio src="ms-winsoundevent:Notification.Default" loop="false" />
</toast>
"@)

    $toast = [Windows.UI.Notifications.ToastNotification]::New($toastXml)
    $toast.Tag = [Guid]::NewGuid().ToString()
    $toast.Group = "ClaudeCode"
    $toast.ExpirationTime = [DateTimeOffset]::Now.AddSeconds(15)

    $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($AppId)
    $notifier.Show($toast)
} catch { }

# Layer 2: BEL beep - audible fallback via Windows Terminal bellStyle
try {
    Write-Host "`a" -NoNewline
} catch { }

# Layer 3: System sound - additional audible alert
try {
    [System.Media.SystemSounds]::Exclamation.Play()
} catch { }
