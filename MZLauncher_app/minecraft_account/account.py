import http.server
import socketserver
import threading
import time
import webbrowser
import uuid
from pathlib import Path

import minecraft_launcher_lib.microsoft_account as msa
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QInputDialog, QListWidget, QListWidgetItem, QHBoxLayout, QMessageBox, QLineEdit
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from MZLauncher_app.settings.settings import load_accounts, save_accounts, get_appdata_path


class UserManagerDialog(QDialog):
    def __init__(self, parent=None, tr=None):
        super().__init__(parent)
        self.tr = tr if tr else {}
        self.setWindowTitle(self.tr.get('user_manager_title', 'Add Users | Manager Users'))
        self.setMinimumSize(350, 400)
        self.users = load_accounts()
        self.parent_window = parent
        layout = QVBoxLayout(self)
        self.user_list = QListWidget()
        self.update_list()
        layout.addWidget(self.user_list)
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton('+')
        self.add_btn.clicked.connect(self.add_user)
        self.edit_btn = QPushButton('✎')
        self.edit_btn.clicked.connect(self.edit_user)
        self.delete_btn = QPushButton('-')
        self.delete_btn.clicked.connect(self.delete_user)
        self.select_btn = QPushButton(self.tr.get('select_button', 'Select'))
        self.select_btn.clicked.connect(self.select_user)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.select_btn)
        layout.addLayout(btn_layout)

    def update_list(self):
        self.user_list.clear()
        accounts = load_accounts()
        for acc in accounts:
            if acc.get('type') == 'microsoft':
                display_name = f"(microsoft) {acc.get('name', 'Unknown')}"
            else:
                display_name = f"(offline) {acc.get('name', 'Unknown')}"
            self.user_list.addItem(display_name)

    def add_user(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr.get('add_account_title', 'Add Account'))
        layout = QVBoxLayout(dialog)
        label = QLabel(self.tr.get('choose_account_type', 'Choose account type:'))
        layout.addWidget(label)
        btn_offline = QPushButton(self.tr.get('offline_account', 'Offline'))
        btn_offline.setMinimumHeight(35)
        layout.addWidget(btn_offline)
        btn_microsoft = QPushButton(self.tr.get('microsoft_account', 'Microsoft'))
        btn_microsoft.setMinimumHeight(35)
        btn_microsoft.setVisible(False)
        layout.addWidget(btn_microsoft)
        btn_cancel = QPushButton(self.tr.get('cancel', 'Cancel'))
        btn_cancel.setMinimumHeight(35)
        layout.addWidget(btn_cancel)
        result = None

        def set_result(res):
            nonlocal result
            result = res
            dialog.accept()

        btn_offline.clicked.connect(lambda: set_result('offline'))
        btn_microsoft.clicked.connect(lambda: set_result('microsoft'))
        btn_cancel.clicked.connect(dialog.reject)

        if dialog.exec() == QDialog.Accepted and result == 'offline':
            accounts = load_accounts()
            name, ok = QInputDialog.getText(self, self.tr.get('offline_login_title', 'Offline Login'), self.tr.get('username_prompt', 'Username:'))
            if ok and name:
                accounts.append({'type': 'offline', 'name': name})
                save_accounts(accounts)
                self.update_list()
        elif result == 'microsoft':
            self.start_microsoft_login()

    def start_microsoft_login(self):
        try:
            auth_code = None
            server_started = threading.Event()

            class OAuthHandler(http.server.SimpleHTTPRequestHandler):
                def do_GET(self):
                    nonlocal auth_code
                    if 'code=' in self.path:
                        auth_code = msa.get_auth_code_from_url(self.path)
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        self.wfile.write(b'<html><h2>Login successful! You can close this window now.</h2></html>')
                    else:
                        self.send_response(404)
                        self.end_headers()

            def start_auth_server():
                try:
                    server = socketserver.TCPServer(('localhost', 12782), OAuthHandler)
                    server_started.set()
                    server.handle_request()
                    return server
                except Exception as e:
                    print(f'Server error: {e}')
                    server_started.set()
                    return None

            server_thread = threading.Thread(target=start_auth_server)
            server_thread.daemon = True
            server_thread.start()
            server_started.wait(timeout=5)
            login_url = msa.get_login_url('YOUR_CLIENT_ID_HERE', 'http://localhost:12782/callback')
            webbrowser.open(login_url)
            while auth_code is None and server_thread.is_alive():
                QApplication.processEvents()
                time.sleep(0.1)
            if auth_code:
                try:
                    account = msa.complete_login('YOUR_CLIENT_ID_HERE', None, 'http://localhost:12782/callback', auth_code)
                    self.on_login_success(account)
                except Exception as e:
                    self.on_login_failed(f'Failed to complete login: {e}')
        except Exception as e:
            self.on_login_failed(f'An unexpected error occurred: {e}')

    def on_login_success(self, account):
        accounts = load_accounts()
        new_account = {
            'type': 'microsoft',
            'name': account['name'],
            'uuid': account['id'],
            'token': account['access_token'],
            'refresh_token': account.get('refresh_token')
        }
        accounts.append(new_account)
        save_accounts(accounts)
        self.update_list()

    def on_login_failed(self, error_message):
        QMessageBox.critical(self, 'Login Failed', f'Microsoft login failed:\n{error_message}')

    def edit_user(self):
        selected = self.user_list.currentItem()
        if not selected:
            QMessageBox.warning(self, self.tr.get('no_selection_title', 'No Selection'), self.tr.get('select_user_to_edit_prompt', 'Please select a user to edit.'))
            return
        old_username = selected.text()
        if old_username.startswith('(offline)'):
            current_name = old_username.replace('(offline) ', '')
            text, ok = QInputDialog.getText(self, self.tr.get('edit_user_title', 'Edit User'), self.tr.get('edit_user_prompt', 'Edit username:'), QLineEdit.Normal, current_name)
            if ok and text and text != current_name:
                index = self.user_list.currentRow()
                accounts = load_accounts()
                accounts[index]['name'] = text
                save_accounts(accounts)
                self.update_list()
        else:
            QMessageBox.information(self, self.tr.get('edit_user_title', 'Edit User'), self.tr.get('cannot_edit_ms_account', 'Microsoft account names cannot be edited here.'))

    def delete_user(self):
        selected = self.user_list.currentItem()
        if not selected:
            QMessageBox.warning(self, self.tr.get('no_selection_title', 'No Selection'), self.tr.get('select_user_to_delete_prompt', 'Please select a user to delete.'))
            return
        display_name = selected.text()
        reply = QMessageBox.question(self, self.tr.get('delete_user_title', 'Delete User'), self.tr.get('delete_user_confirm', 'Are you sure you want to delete \"{username}\"?').format(username=display_name), QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            index = self.user_list.currentRow()
            accounts = load_accounts()
            if 0 <= index < len(accounts):
                accounts.pop(index)
                save_accounts(accounts)
            self.update_list()

    def select_user(self):
        selected = self.user_list.currentItem()
        if selected:
            display_text = selected.text()
            self.parent_window.username_combo.setCurrentText(display_text)
            self.accept()
        else:
            QMessageBox.warning(self, self.tr.get('no_selection_title', 'No Selection'), self.tr.get('select_user_prompt', 'Please select a user.'))
