; --- MaZult Launcher Inno Setup Script (64-bit only) ---
[Setup]
AppName=MaZult Launcher
AppVersion=1.8.5.2026
AppPublisher=LunarMoonDLCT
AppCopyright=© 2026 LunarMoonDLCT

DefaultDirName={autopf}\MaZult Launcher
DefaultGroupName=MaZult Launcher
OutputBaseFilename=MaZultLauncher_Setup_v1.8.5
OutputDir=dist

Compression=lzma2/ultra64
SolidCompression=yes

SetupIconFile=icon.ico
DisableWelcomePage=no

UninstallDisplayIcon={app}\Launcher.exe
UninstallDisplayName=MaZult Launcher
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel1=Welcome to the MaZult Launcher Setup Wizard
WelcomeLabel2=This is a launcher for Minecraft.

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional options:"
Name: "launchafterinstall"; Description: "Launch MaZult Launcher after installation"; GroupDescription: "Final options:"

[Files]
Source: "dist\app_debug\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MaZult Launcher"; Filename: "{app}\Launcher.exe"; IconFilename: "{app}\icon.ico"
Name: "{commondesktop}\MaZult Launcher"; Filename: "{app}\Launcher.exe"; Tasks: desktopicon; IconFilename: "{app}\icon.ico"

[Run]
Filename: "{app}\Launcher.exe"; Description: "Launch MaZult Launcher"; Flags: nowait postinstall skipifsilent; Tasks: launchafterinstall

