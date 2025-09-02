; --- MaZult Launcher Inno Setup Script (64-bit only) ---
[Setup]
AppName=MaZult Launcher
AppVersion=1.104.98.1
AppPublisher=LunarMoonDLCT
AppCopyright=© 2025 LunarMoonDLCT
DefaultDirName={pf}\MaZult Launcher
DefaultGroupName=MaZult Launcher
OutputBaseFilename=MaZultLauncher_Setup
Compression=lzma
SolidCompression=yes

; Icon chính cho file setup và app
SetupIconFile=app\icon.ico

DisableWelcomePage=no
; Nếu muốn thay banner/logo thì cần BMP (không bắt buộc)
; WizardImageFile=app\logo.bmp
; WizardSmallImageFile=app\logo_small.bmp

UninstallDisplayIcon={app}\MaZult Launcher.exe
UninstallDisplayName=MaZult Launcher

; Force installer to use 64-bit mode
ArchitecturesInstallIn64BitMode=x64

; Hiển thị màn hình chọn thư mục cài đặt
DisableDirPage=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel1=Welcome to the MaZult Launcher Setup Wizard
WelcomeLabel2=This is a launcher for minecraft.

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional options:"
Name: "launchafterinstall"; Description: "Launch MaZult Launcher after installation"; GroupDescription: "Final options:"

[Files]
Source: "app\MaZult Launcher.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "app\icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "app\python3.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "app\python313.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "app\lib\*"; DestDir: "{app}\lib"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MaZult Launcher"; Filename: "{app}\MaZult Launcher.exe"; IconFilename: "{app}\icon.ico"
Name: "{commondesktop}\MaZult Launcher"; Filename: "{app}\MaZult Launcher.exe"; Tasks: desktopicon; IconFilename: "{app}\icon.ico"

[Run]
Filename: "{app}\MaZult Launcher.exe"; Description: "Launch MaZult Launcher"; Flags: nowait postinstall skipifsilent; Tasks: launchafterinstall

[Code]
var
  RemoveDataCheckBox: TNewCheckBox;

function InitializeUninstall(): Boolean;
var
  Form: TSetupForm;
  BtnUninstall, BtnCancel: TNewButton;
  ResultCode: Integer;
begin
  Result := False;

  Form := CreateCustomForm;
  try
    Form.Caption := 'Uninstall MaZult Launcher';
    Form.ClientWidth := ScaleX(420);
    Form.ClientHeight := ScaleY(150);
    Form.Position := poScreenCenter;

    with TNewStaticText.Create(Form) do
    begin
      Parent := Form;
      Caption := 'Are you sure you want to completely remove MaZult Launcher from your system?';
      Left := ScaleX(20);
      Top := ScaleY(20);
      Width := Form.ClientWidth - ScaleX(40);
      WordWrap := True;
    end;

    RemoveDataCheckBox := TNewCheckBox.Create(Form);
    RemoveDataCheckBox.Parent := Form;
    RemoveDataCheckBox.Caption := 'Also remove user data and configuration files';
    RemoveDataCheckBox.Left := ScaleX(20);
    RemoveDataCheckBox.Top := ScaleY(60);
    RemoveDataCheckBox.Width := Form.ClientWidth - ScaleX(40);

    BtnUninstall := TNewButton.Create(Form);
    BtnUninstall.Parent := Form;
    BtnUninstall.Caption := 'Uninstall';
    BtnUninstall.ModalResult := mrOK;
    BtnUninstall.Left := Form.ClientWidth div 2 - ScaleX(100);
    BtnUninstall.Top := ScaleY(100);

    BtnCancel := TNewButton.Create(Form);
    BtnCancel.Parent := Form;
    BtnCancel.Caption := 'Cancel';
    BtnCancel.ModalResult := mrCancel;
    BtnCancel.Left := Form.ClientWidth div 2 + ScaleX(10);
    BtnCancel.Top := ScaleY(100);

    ResultCode := Form.ShowModal;
    if ResultCode = mrOK then
      Result := True
    else
      Result := False;
  finally
    Form.Free;
  end;
end;

procedure DeinitializeUninstall();
begin
  { Luôn xoá thư mục bin vì nó được tạo sau khi app chạy }
  DelTree(ExpandConstant('{app}'), True, True, True);

  { Nếu người dùng chọn thì xoá thêm dữ liệu trong AppData }
  if Assigned(RemoveDataCheckBox) and RemoveDataCheckBox.Checked then
  begin
    DelTree(ExpandConstant('{userappdata}\.mazultlauncher'), True, True, True);
  end;

  { Nếu thư mục app rỗng thì xoá luôn }
  RemoveDir(ExpandConstant('{app}'));

  MsgBox('MaZult Launcher has been successfully removed.'#13#10#13#10 +
         'Thank you for using it, see you again soon!', mbInformation, MB_OK);
end;
