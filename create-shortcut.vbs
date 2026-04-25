' create-shortcut.vbs — Creates a desktop shortcut for ShadowLink AI
' Run this script once: double-click or execute "cscript create-shortcut.vbs"

Set WshShell = WScript.CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Resolve paths
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
batPath = fso.BuildPath(scriptDir, "start.bat")
iconPath = fso.BuildPath(scriptDir, "assets\icons\app.ico")
desktopPath = WshShell.SpecialFolders("Desktop")
shortcutPath = fso.BuildPath(desktopPath, "ShadowLink AI.lnk")

' Create shortcut
Set shortcut = WshShell.CreateShortcut(shortcutPath)
shortcut.TargetPath = batPath
shortcut.WorkingDirectory = scriptDir
shortcut.Description = "ShadowLink AI Platform - One-Click Launcher"
shortcut.WindowStyle = 1 ' Normal window

' Use custom icon if available, otherwise use system icon
If fso.FileExists(iconPath) Then
    shortcut.IconLocation = iconPath
Else
    shortcut.IconLocation = "%SystemRoot%\System32\shell32.dll,13"
End If

shortcut.Save

WScript.Echo "Desktop shortcut created: " & shortcutPath
WScript.Echo ""
WScript.Echo "You can now double-click 'ShadowLink AI' on your desktop to launch!"
