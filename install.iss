; --- MaZult Launcher Inno Setup Script (64-bit only) ---
[Setup]
AppName=MaZult Launcher
AppVersion=1.829.921.3
AppPublisher=LunarMoonDLCT
AppCopyright=© 2025 LunarMoonDLCT
DefaultDirName={pf}\MaZult Launcher
DefaultGroupName=MaZult Launcher
OutputBaseFilename=MaZultLauncher_Setup
Compression=lzma
SolidCompression=yes

; Icon cho setup và app
SetupIconFile=app\icon.ico

DisableWelcomePage=no

UninstallDisplayIcon={app}\MaZult Launcher.exe
UninstallDisplayName=MaZult Launcher
ArchitecturesInstallIn64BitMode=x64
DisableDirPage=no

; ✅ Dùng cái này thay vì UninstallConfirm=no
Uninstallable=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel1=Welcome to the MaZult Launcher Setup Wizard
WelcomeLabel2=This is a launcher for Minecraft.

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional options:"
Name: "launchafterinstall"; Description: "Launch MaZult Launcher after installation"; GroupDescription: "Final options:"

[Files]

Source: "app\*"; DestDir: "{app}"; Flags: ignoreversion
Source: "app\lib\*"; DestDir: "{app}\lib"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MaZult Launcher"; Filename: "{app}\MaZult Launcher.exe"; IconFilename: "{app}\icon.ico"
Name: "{commondesktop}\MaZult Launcher"; Filename: "{app}\MaZult Launcher.exe"; Tasks: desktopicon; IconFilename: "{app}\icon.ico"

[Run]
Filename: "{app}\MaZult Launcher.exe"; Description: "Launch MaZult Launcher"; Flags: nowait postinstall skipifsilent; Tasks: launchafterinstall

[Code]
var
  RemoveDataCheckBox: TNewCheckBox;
  DoUninstall, RemoveData: Boolean;

function InitializeUninstall(): Boolean;
var
  Form: TSetupForm;
  BtnYes, BtnNo: TNewButton;
  ResultCode: Integer;
begin
  DoUninstall := False;
  RemoveData := False;

  Form := CreateCustomForm;
  try
    Form.Caption := 'Uninstall MaZult Launcher';
    Form.ClientWidth := ScaleX(420);
    Form.ClientHeight := ScaleY(160);
    Form.Position := poScreenCenter;
    Form.BorderStyle := bsDialog;

    with TNewStaticText.Create(Form) do
    begin
      Parent := Form;
      Caption := 'Do you really want to completely remove MaZult Launcher from your system?';
      Left := ScaleX(20);
      Top := ScaleY(20);
      Width := Form.ClientWidth - ScaleX(40);
      WordWrap := True;
    end;

    RemoveDataCheckBox := TNewCheckBox.Create(Form);
    RemoveDataCheckBox.Parent := Form;
    RemoveDataCheckBox.Caption := 'Also remove user data and configuration files';
    RemoveDataCheckBox.Left := ScaleX(20);
    RemoveDataCheckBox.Top := ScaleY(70);
    RemoveDataCheckBox.Width := Form.ClientWidth - ScaleX(40);

    BtnYes := TNewButton.Create(Form);
    BtnYes.Parent := Form;
    BtnYes.Caption := 'Yes';
    BtnYes.ModalResult := mrYes;
    BtnYes.Left := Form.ClientWidth div 2 - ScaleX(100);
    BtnYes.Top := ScaleY(110);

    BtnNo := TNewButton.Create(Form);
    BtnNo.Parent := Form;
    BtnNo.Caption := 'No';
    BtnNo.ModalResult := mrNo;
    BtnNo.Left := Form.ClientWidth div 2 + ScaleX(10);
    BtnNo.Top := ScaleY(110);

    ResultCode := Form.ShowModal;
    if ResultCode = mrYes then
    begin
      DoUninstall := True;
      RemoveData := RemoveDataCheckBox.Checked;
      Result := True;  // tiếp tục uninstall
    end
    else
      Result := False; // hủy bỏ uninstall
  finally
    Form.Free;
  end;
end;

procedure DeinitializeUninstall();
begin
  if not DoUninstall then
    exit;

  { Xoá thư mục cài đặt }
  DelTree(ExpandConstant('{app}'), True, True, True);

  { Nếu người dùng chọn thì xoá thêm dữ liệu trong AppData }
  if RemoveData then
  begin
    DelTree(ExpandConstant('{userappdata}\.mazultlauncher'), True, True, True);
  end;

  { Nếu thư mục app rỗng thì xoá luôn }
  RemoveDir(ExpandConstant('{app}'));

  MsgBox('MaZult Launcher has been successfully removed.'#13#10#13#10 +
         'Thank you for using it, see you again soon!', mbInformation, MB_OK);
end;

function NeedRestart(): Boolean;
begin
  { Không cho cancel hoặc yêu cầu restart sau khi Yes }
  Result := False;
end;
