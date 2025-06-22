import sys, json, os, csv, xlwt
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes          
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QComboBox,
    QMessageBox, QTabWidget, QGroupBox, QRadioButton, QFileDialog,
    QDialog, QDialogButtonBox, QDateTimeEdit, QFormLayout,
    QHeaderView, QMenu, QAction, QInputDialog, QCheckBox, QFrame,
    QButtonGroup, QStackedWidget, QStyle
)
from PyQt5.QtCore import Qt, QDateTime, QDate, QTime, QTimer
from PyQt5.QtGui import QFont, QIcon, QIntValidator

# 工具函数：时间格式转换
def to_datetime(s):
    """将字符串转换为datetime对象"""
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S") if s else None

def to_str(dt):
    """将datetime对象转换为字符串"""
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None

# 车辆类
class Car:
    def __init__(self, number, model, enter_time=None, quit_time=None, price=0, cost=0):
        self.number = number
        self.model = model
        self.enter_time = enter_time
        self.quit_time = quit_time
        self.price = price
        self.cost = cost
        
    def calculate_cost(self, current_time=None):
        if not self.enter_time:
            return 0
            
        if not self.quit_time and current_time:
            self.quit_time = current_time if isinstance(current_time, str) else to_str(current_time)
        
        enter_dt = to_datetime(self.enter_time)
        quit_dt = to_datetime(self.quit_time)
        
        if not enter_dt or not quit_dt:
            return 0
            
        # 计算总小时数（向上取整）
        hours = (quit_dt - enter_dt).total_seconds() / 3600
        hours = int(hours) if hours.is_integer() else int(hours) + 1
        
        self.cost = hours * self.price
        return self.cost

# 管理员类
class CarManager:
    def __init__(self, manager_id, key=""):
        self.id = manager_id
        self.key = key
        self.total_income = 0

    def add_income(self, amount):
        self.total_income += amount
        
    def verify_password(self, password):
        return self.key == password

# 停车场管理系统
class ParkingSystem:
    MODEL_PRICES = {"小型车": 5, "中型车": 10, "大型车": 15}
    
    def __init__(self, max_spaces=20, manager_id="admin", manager_key=""):
        self.cars = []
        self.parking_history = []
        self.manager = CarManager(manager_id, manager_key)
        self.max_spaces = max_spaces
        self.last_save_path = ""
        
    def add_car(self, car):
        if self.available_spaces() <= 0:
            return "车位已满！"
            
        if any(c.number == car.number for c in self.cars):
            return "该车辆已在停车场中"
            
        self.cars.append(car)
        return ""
    
    def remove_car(self, number, current_time=None):
        car = next((c for c in self.cars if c.number == number), None)
        if car:
            car.calculate_cost(current_time)
            self.cars.remove(car)
            self.parking_history.append(car)
            self.manager.add_income(car.cost)
            return car
        return None
    
    def available_spaces(self):
        return self.max_spaces - len(self.cars)
    
    def save_to_file(self, filename, encrypt=False, password=""):
        data = {
            "manager_id": self.manager.id,
            "manager_key": self.manager.key if encrypt else "",
            "max_spaces": self.max_spaces,
            "cars": [vars(c) for c in self.cars],
            "parking_history": [vars(c) for c in self.parking_history],
            "total_income": self.manager.total_income,
            "encrypted": encrypt
        }
        
        json_data = json.dumps(data, indent=2).encode('utf-8')
        
        if encrypt:
            if not password:
                password = self.manager.key
            if not password:
                return False
                
            salt = get_random_bytes(16)
            key = PBKDF2(password, salt, dkLen=32, count=100000)
            iv = get_random_bytes(16)
            
            cipher = AES.new(key, AES.MODE_CBC, iv)
            padded_data = pad(json_data, AES.block_size)
            encrypted_data = cipher.encrypt(padded_data)
            
            magic_header = b"PBKDF2v1"
            try:
                with open(filename, 'wb') as f:
                    f.write(magic_header)
                    f.write(salt)
                    f.write(iv)
                    f.write(encrypted_data)
                self.last_save_path = filename
                return True
            except Exception as e:
                print(f"保存文件失败: {e}")
                return False
        else:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(json_data.decode('utf-8'))
                self.last_save_path = filename
                return True
            except Exception as e:
                print(f"保存文件失败: {e}")
                return False
    
    def load_from_file(self, filename, password=""):
        try:
            with open(filename, 'rb') as f:
                header = f.read(8)
                
            if header == b"PBKDF2v1":
                with open(filename, 'rb') as f:
                    f.seek(8)
                    salt = f.read(16)
                    iv = f.read(16)
                    encrypted_data = f.read()
                
                if not password:
                    return False, "文件已被加密，需要密码"
                
                try:
                    key = PBKDF2(password, salt, dkLen=32, count=100000)
                    cipher = AES.new(key, AES.MODE_CBC, iv)
                    decrypted_data = unpad(cipher.decrypt(encrypted_data), AES.block_size)
                    data = json.loads(decrypted_data.decode('utf-8'))
                except Exception as e:
                    return False, f"解密失败: {str(e)}"
                    
            else:
                try:
                    with open(filename, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except:
                    return False, "文件格式错误，无法解析"
                
            if "manager_id" not in data or "max_spaces" not in data:
                return False, "文件格式错误"
                
            self.manager = CarManager(
                data.get("manager_id", "admin"),
                data.get("manager_key", "")
            )
            self.manager.total_income = data.get("total_income", 0)
            self.max_spaces = data.get("max_spaces", 20)
            self.last_save_path = filename
                
            self.cars = [
                Car(c['number'], c['model'], c['enter_time'], c['quit_time'], c['price'], c['cost'])
                for c in data.get("cars", [])
            ]
            
            self.parking_history = [
                Car(c['number'], c['model'], c['enter_time'], c['quit_time'], c['price'], c['cost'])
                for c in data.get("parking_history", [])
            ]
            
            return True, "加载成功"
        except Exception as e:
            return False, f"加载失败: {str(e)}"

# 初始化窗口
class InitialWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.loaded_system = None
        
    def setup_ui(self):
        self.setWindowTitle("停车场系统初始化")
        self.setWindowIcon(QIcon('icon.png'))
        self.setGeometry(400, 300, 500, 400)
        
        layout = QVBoxLayout()
        self.setup_title(layout)
        self.setup_mode_selection(layout)
        self.setup_form_widgets(layout)
        self.setup_next_button(layout)
        self.setLayout(layout)
    
    def setup_title(self, layout):
        title = QLabel("停车场管理系统初始化")
        title_font = QFont("Arial", 16, QFont.Bold)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("margin: 20px 0; color: #2c3e50;")
        layout.addWidget(title)
    
    def setup_mode_selection(self, layout):
        mode_group = QGroupBox("选择初始化方式")
        mode_layout = QVBoxLayout()
        
        self.new_system_radio = QRadioButton("新建系统")
        self.new_system_radio.setChecked(True)
        self.load_system_radio = QRadioButton("从文件加载系统")
        
        mode_layout.addWidget(self.new_system_radio)
        mode_layout.addWidget(self.load_system_radio)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        self.new_system_radio.toggled.connect(self.toggle_mode)
    
    def setup_form_widgets(self, layout):
        self.stacked_widget = QStackedWidget()
        
        # 新建系统页面
        self.new_system_widget = self.create_new_system_widget()
        self.stacked_widget.addWidget(self.new_system_widget)
        
        # 加载系统页面
        self.load_system_widget = self.create_load_system_widget()
        self.stacked_widget.addWidget(self.load_system_widget)
        
        layout.addWidget(self.stacked_widget)
    
    def create_new_system_widget(self):
        widget = QWidget()
        layout = QFormLayout()
        layout.setSpacing(15)
        
        self.admin_id_input = QLineEdit()
        self.admin_id_input.setPlaceholderText("输入管理员ID")
        layout.addRow("管理员ID:", self.admin_id_input)
        
        self.max_spaces_input = QLineEdit()
        self.max_spaces_input.setPlaceholderText("输入车位数量")
        layout.addRow("车位数量:", self.max_spaces_input)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("可选")
        layout.addRow("管理员密码:", self.password_input)
        
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input.setPlaceholderText("可选")
        layout.addRow("确认密码:", self.confirm_password_input)
        
        # 连接信号
        inputs = [self.admin_id_input, self.max_spaces_input, 
                 self.password_input, self.confirm_password_input]
        for input in inputs:
            input.textChanged.connect(self.validate_inputs)
        
        widget.setLayout(layout)
        return widget
    
    def create_load_system_widget(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        file_layout = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("选择系统文件...")
        self.file_input.textChanged.connect(self.check_file_exists)
        
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_file)
        
        file_layout.addWidget(self.file_input)
        file_layout.addWidget(browse_btn)
        
        self.file_status = QLabel()
        self.file_status.setStyleSheet("color: #7f8c8d; font-size: 10pt;")
        
        self.password_label = QLabel("文件加密密码:")
        self.password_label.setVisible(False)
        self.file_password = QLineEdit()
        self.file_password.setEchoMode(QLineEdit.Password)
        self.file_password.setVisible(False)
        
        load_btn = QPushButton("读取文件")
        load_btn.clicked.connect(self.load_file)
        
        layout.addLayout(file_layout)
        layout.addWidget(self.file_status)
        layout.addWidget(self.password_label)
        layout.addWidget(self.file_password)
        layout.addWidget(load_btn)
        
        widget.setLayout(layout)
        return widget
    
    def setup_next_button(self, layout):
        self.next_btn = QPushButton("下一步")
        self.next_btn.setEnabled(False)
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self.next_btn.clicked.connect(self.accept)
        layout.addWidget(self.next_btn)
    
    def toggle_mode(self, checked):
        self.stacked_widget.setCurrentIndex(0 if checked else 1)
        if not checked:
            self.file_input.textChanged.emit(self.file_input.text())
    
    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择停车场系统文件", "", "Parking System Files (*.psys);;All Files (*)"
        )
        if file_path:
            self.file_input.setText(file_path)
    
    def check_file_exists(self, file_path):
        if not file_path:
            self.file_status.setText("")
            return
            
        if os.path.exists(file_path):
            self.file_status.setText("文件存在")
            self.file_status.setStyleSheet("color: #7f8c8d;")
        else:
            self.file_status.setText("文件不存在")
            self.file_status.setStyleSheet("color: red;")
    
    def validate_inputs(self):
        if self.new_system_radio.isChecked():
            admin_id = self.admin_id_input.text().strip()
            max_spaces = self.max_spaces_input.text().strip()
            password = self.password_input.text()
            confirm_password = self.confirm_password_input.text()
            
            valid = bool(admin_id)
            
            try:
                spaces = int(max_spaces)
                valid = valid and spaces > 0
            except:
                valid = False
            
            if password or confirm_password:
                valid = valid and (password == confirm_password)
        else:
            valid = bool(self.file_input.text().strip())
            
        self.next_btn.setEnabled(valid)
    
    def load_file(self):
        file_path = self.file_input.text().strip()
        if not file_path:
            self.file_status.setText("请选择文件")
            self.file_status.setStyleSheet("color: red;")
            return False
        
        if not os.path.isfile(file_path):
            self.file_status.setText("文件不存在")
            self.file_status.setStyleSheet("color: red;")
            return False
        
        temp_system = ParkingSystem()
        password = self.file_password.text() if self.file_password.isVisible() else ""
        success, msg = temp_system.load_from_file(file_path, password)
        
        if success:
            self.file_status.setText("文件加载成功")
            self.file_status.setStyleSheet("color: green;")
            self.loaded_system = temp_system
            self.next_btn.setEnabled(True)
            return True
        else:
            self.file_status.setText(msg)
            self.file_status.setStyleSheet("color: red;")
            
            if "需要密码" in msg:
                self.password_label.setVisible(True)
                self.file_password.setVisible(True)
            
            return False
    
    def get_system(self):
        if self.new_system_radio.isChecked():
            admin_id = self.admin_id_input.text().strip()
            max_spaces = int(self.max_spaces_input.text().strip())
            password = self.password_input.text()
            confirm_password = self.confirm_password_input.text()
            
            if password and password != confirm_password:
                QMessageBox.warning(self, "密码错误", "两次输入的密码不一致")
                return None
                
            return ParkingSystem(max_spaces, admin_id, password)
        else:
            return self.loaded_system

# 时间设置对话框（通用）
class TimeDialog(QDialog):
    def __init__(self, title, initial_time=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setup_ui(initial_time)
        
    def setup_ui(self, initial_time):
        layout = QVBoxLayout()
        
        self.datetime_edit = QDateTimeEdit(initial_time or QDateTime.currentDateTime())
        self.datetime_edit.setCalendarPopup(True)
        layout.addWidget(self.datetime_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def get_time(self):
        return self.datetime_edit.dateTime().toPyDateTime()

# 车辆编辑对话框
class CarEditDialog(QDialog):
    def __init__(self, car, parent=None):
        super().__init__(parent)
        self.car = car
        self.modified = False
        self.status_changed = False
        self.original_quit_time = car.quit_time
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("编辑车辆信息")
        self.setWindowIcon(QIcon('car.png'))
        self.setGeometry(500, 300, 400, 300)
        
        layout = QVBoxLayout()
        self.setup_plate_input(layout)
        self.setup_model_selection(layout)
        self.setup_enter_time(layout)
        self.setup_exit_time(layout)
        self.setup_buttons(layout)
        self.setLayout(layout)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_exit_time)
        self.timer.start(1000)
        self.exit_time_modified = False
    
    def setup_plate_input(self, layout):
        plate_layout = QHBoxLayout()
        plate_layout.addWidget(QLabel("车牌号:"))
        self.plate_input = QLineEdit(self.car.number)
        plate_layout.addWidget(self.plate_input)
        layout.addLayout(plate_layout)
    
    def setup_model_selection(self, layout):
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("车型:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(ParkingSystem.MODEL_PRICES.keys())
        self.model_combo.setCurrentText(self.car.model)
        model_layout.addWidget(self.model_combo)
        layout.addLayout(model_layout)
    
    def setup_enter_time(self, layout):
        enter_layout = QHBoxLayout()
        enter_layout.addWidget(QLabel("入场时间:"))
        self.enter_datetime = QDateTimeEdit()
        
        enter_dt = to_datetime(self.car.enter_time) or datetime.now()
        self.enter_datetime.setDateTime(QDateTime(
            QDate(enter_dt.year, enter_dt.month, enter_dt.day),
            QTime(enter_dt.hour, enter_dt.minute, enter_dt.second)
        ))
        
        enter_layout.addWidget(self.enter_datetime)
        layout.addLayout(enter_layout)
    
    def setup_exit_time(self, layout):
        self.exit_checkbox = QCheckBox("车辆已出场")
        self.exit_checkbox.stateChanged.connect(self.toggle_exit_time)
        layout.addWidget(self.exit_checkbox)
        
        exit_layout = QHBoxLayout()
        exit_layout.addWidget(QLabel("出场时间:"))
        self.exit_datetime = QDateTimeEdit()
        
        if self.car.quit_time:
            self.exit_checkbox.setChecked(True)
            exit_dt = to_datetime(self.car.quit_time) or datetime.now()
            self.exit_datetime.setDateTime(QDateTime(
                QDate(exit_dt.year, exit_dt.month, exit_dt.day),
                QTime(exit_dt.hour, exit_dt.minute, exit_dt.second)
            ))
        else:
            self.exit_datetime.setEnabled(False)
            now = datetime.now()
            self.exit_datetime.setDateTime(QDateTime(
                QDate(now.year, now.month, now.day),
                QTime(now.hour, now.minute, now.second)
            ))
        
        exit_layout.addWidget(self.exit_datetime)
        layout.addLayout(exit_layout)
    
    def setup_buttons(self, layout):
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def update_exit_time(self):
        if not self.exit_time_modified and self.exit_checkbox.isChecked():
            now = datetime.now()
            self.exit_datetime.setDateTime(QDateTime(
                QDate(now.year, now.month, now.day),
                QTime(now.hour, now.minute, now.second)
            ))
    
    def toggle_exit_time(self, state):
        enabled = state == Qt.Checked
        self.exit_datetime.setEnabled(enabled)
        
        if enabled and not self.exit_time_modified:
            self.timer.start(1000)
    
    def closeEvent(self, event):
        self.timer.stop()
        super().closeEvent(event)
    
    def validate_and_accept(self):
        plate = self.plate_input.text().strip()
        if not plate:
            QMessageBox.warning(self, "输入错误", "请输入车牌号")
            return
            
        enter_time = self.enter_datetime.dateTime().toPyDateTime()
        current_time = datetime.now()
        
        if enter_time > current_time:
            QMessageBox.warning(self, "时间错误", "入场时间不能晚于当前时间")
            return
            
        if self.exit_checkbox.isChecked():
            exit_time = self.exit_datetime.dateTime().toPyDateTime()
            if exit_time < enter_time:
                QMessageBox.warning(self, "时间错误", "出场时间不能早于入场时间")
                return
                
            if exit_time > current_time:
                QMessageBox.warning(self, "时间错误", "出场时间不能晚于当前时间")
                return
        
        self.car.number = plate
        self.car.model = self.model_combo.currentText()
        self.car.price = ParkingSystem.MODEL_PRICES[self.car.model]
        self.car.enter_time = to_str(enter_time)
        
        if self.exit_checkbox.isChecked():
            self.car.quit_time = to_str(exit_time)
            self.car.calculate_cost()
        else:
            self.car.quit_time = None
            self.car.cost = 0
            
        self.status_changed = (
            self.exit_checkbox.isChecked() and 
            not self.original_quit_time and 
            self.car.quit_time
        )
        
        self.modified = True
        self.accept()

# 管理员编辑对话框
class AdminEditDialog(QDialog):
    def __init__(self, manager, max_spaces, current_used_spaces, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.max_spaces = max_spaces
        self.current_used_spaces = current_used_spaces
        self.modified = False
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("修改管理员信息")
        self.setWindowIcon(QIcon('admin.png'))
        self.setGeometry(500, 300, 400, 350)
        
        layout = QVBoxLayout()
        form = QFormLayout()
        form.setSpacing(15)
        
        self.new_id_input = QLineEdit(self.manager.id)
        form.addRow("新管理员ID:", self.new_id_input)
        
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.Password)
        self.new_password.setPlaceholderText("留空表示不修改密码")
        form.addRow("新密码:", self.new_password)
        
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.Password)
        self.confirm_password.setPlaceholderText("留空表示不修改密码")
        form.addRow("确认新密码:", self.confirm_password)
        
        self.current_password = QLineEdit()
        self.current_password.setEchoMode(QLineEdit.Password)
        self.current_password.setPlaceholderText("如果设置了密码则必填")
        form.addRow("当前密码:", self.current_password)
        
        self.max_spaces_input = QLineEdit(str(self.max_spaces))
        self.max_spaces_input.setValidator(QIntValidator(1, 1000))
        form.addRow("最大车位数量:", self.max_spaces_input)
        
        form.addRow("当前已使用车位:", QLabel(f"{self.current_used_spaces}"))
        
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def validate_and_accept(self):
        new_id = self.new_id_input.text().strip()
        new_pass = self.new_password.text()
        confirm_pass = self.confirm_password.text()
        current_pass = self.current_password.text()
        
        try:
            new_max_spaces = int(self.max_spaces_input.text())
            if new_max_spaces <= 0:
                QMessageBox.warning(self, "输入错误", "车位数量必须大于0")
                return
                
            if new_max_spaces < self.current_used_spaces:
                QMessageBox.warning(
                    self, 
                    "输入错误", 
                    f"新的最大车位数({new_max_spaces})不能小于当前已使用车位数({self.current_used_spaces})"
                )
                return
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的车位数量")
            return
        
        if not new_id:
            QMessageBox.warning(self, "输入错误", "请输入管理员ID")
            return
            
        if new_pass or confirm_pass:
            if new_pass != confirm_pass:
                QMessageBox.warning(self, "密码错误", "两次输入的新密码不一致")
                return
                
        if self.manager.key and not self.manager.verify_password(current_pass):
            QMessageBox.warning(self, "验证失败", "当前密码不正确")
            return
        
        self.manager.id = new_id
        if new_pass:
            self.manager.key = new_pass
        
        self.max_spaces = new_max_spaces
            
        self.modified = True
        self.accept()

# 图形界面主类
class ParkingApp(QMainWindow):
    def __init__(self, system):
        super().__init__()
        self.system = system
        self.custom_time = None
        self.custom_enter_time = None
        self.custom_remove_time = None
        self.setup_ui()
        
        # 添加定时器用于更新自定义时间
        self.custom_time_timer = QTimer(self)
        self.custom_time_timer.timeout.connect(self.update_custom_time)
    
    def closeEvent(self, event):
        """重写关闭事件，弹出确认对话框"""
        reply = QMessageBox.question(
            self, '确认退出',
            '您确定要退出停车场管理系统吗?请确保系统数据已保存。',
            QMessageBox.Cancel | QMessageBox.Ok,
            QMessageBox.Cancel
        )
        
        if reply == QMessageBox.Ok:
            event.accept()
        else:
            event.ignore()
            
    def setup_ui(self):
        self.setWindowTitle("停车场管理系统")
        self.setWindowIcon(QIcon('parking.png'))
        self.setGeometry(100, 100, 1000, 700)
        
        # 设置全局字体
        app_font = QFont("Microsoft YaHei UI", 10)
        QApplication.setFont(app_font)
        
        # 主标签页
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 10px 20px;
                background: #ecf0f1;
                border: 1px solid #bdc3c7;
                border-bottom: none;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background: #3498db;
                color: white;
            }
        """)
        self.setCentralWidget(tabs)
        
        # 停车管理标签
        parking_tab = QWidget()
        self.setup_parking_tab(parking_tab)
        tabs.addTab(parking_tab, "停车管理")
        
        # 数据统计标签
        data_tab = QWidget()
        self.setup_data_tab(data_tab)
        tabs.addTab(data_tab, "数据统计")
        
        # 状态栏显示当前时间
        self.statusBar().setStyleSheet("color: #7f8c8d;")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.update_time()
        
        # 添加另一个定时器用于更新表格
        self.table_timer = QTimer(self)
        self.table_timer.timeout.connect(self.update_car_table)
        self.table_timer.start(10000)
    
    def setup_parking_tab(self, tab):
        layout = QVBoxLayout(tab)
        layout.setSpacing(20)
        
        # 时间显示区域
        time_group = QGroupBox("当前时间")
        time_layout = QVBoxLayout()
        
        self.time_label = QLabel()
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #2c3e50;")
        time_layout.addWidget(self.time_label)
        
        # 时间控制按钮
        btn_layout = QHBoxLayout()
        self.custom_time_btn = QPushButton("自定义当前时间")
        self.custom_time_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.custom_time_btn.clicked.connect(self.set_custom_time)
        
        self.clear_time_btn = QPushButton("同步当前时间")
        self.clear_time_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogResetButton))
        self.clear_time_btn.clicked.connect(self.clear_custom_time)
        self.clear_time_btn.setEnabled(False)
        
        btn_layout.addWidget(self.custom_time_btn)
        btn_layout.addWidget(self.clear_time_btn)
        time_layout.addLayout(btn_layout)
        
        time_group.setLayout(time_layout)
        layout.addWidget(time_group)
        
        # 添加车辆部分
        add_group = QGroupBox("车辆入场")
        add_layout = QVBoxLayout()
        
        # 车牌号输入
        plate_layout = QHBoxLayout()
        plate_layout.addWidget(QLabel("车牌号:"))
        self.plate_input = QLineEdit()
        self.plate_input.setPlaceholderText("例如: 京A12345")
        plate_layout.addWidget(self.plate_input)
        add_layout.addLayout(plate_layout)
        
        # 车型选择
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("车型:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(ParkingSystem.MODEL_PRICES.keys())
        model_layout.addWidget(self.model_combo)
        add_layout.addLayout(model_layout)
        
        # 时间选项
        time_option_layout = QHBoxLayout()
        time_option_layout.addWidget(QLabel("入场时间:"))
        
        self.time_option_group = QButtonGroup()
        self.current_time_radio = QRadioButton("当前时间")
        self.current_time_radio.setChecked(True)
        self.custom_time_radio = QRadioButton("自定义时间")
        
        # 入场时间部分修改 - 添加信号连接
        self.current_time_radio.toggled.connect(self.update_enter_time_display)
        self.custom_time_radio.toggled.connect(self.update_enter_time_display)
        
        self.time_option_group.addButton(self.current_time_radio)
        self.time_option_group.addButton(self.custom_time_radio)
        
        self.time_display = QLabel()
        self.update_enter_time_display()
        
        self.set_time_btn = QPushButton("设置时间")
        self.set_time_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.set_time_btn.clicked.connect(self.set_custom_enter_time)
        self.set_time_btn.setEnabled(False)
        
        time_option_layout.addWidget(self.current_time_radio)
        time_option_layout.addWidget(self.custom_time_radio)
        time_option_layout.addWidget(self.time_display)
        time_option_layout.addWidget(self.set_time_btn)
        time_option_layout.addStretch()
        add_layout.addLayout(time_option_layout)
        
        # 添加按钮
        add_btn = QPushButton("车辆入场登记")
        add_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogOkButton))
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 5px;
            }
        """)
        add_btn.clicked.connect(self.add_car)
        add_layout.addWidget(add_btn)
        
        add_group.setLayout(add_layout)
        layout.addWidget(add_group)
        
        # 移除车辆部分
        remove_group = QGroupBox("车辆出场")
        remove_layout = QVBoxLayout()

        # 车牌号输入
        remove_plate_layout = QHBoxLayout()
        remove_plate_layout.addWidget(QLabel("车牌号:"))
        self.remove_plate_input = QLineEdit()
        remove_plate_layout.addWidget(self.remove_plate_input)
        remove_layout.addLayout(remove_plate_layout)

        # 出场时间选项
        time_option_layout = QHBoxLayout()
        time_option_layout.addWidget(QLabel("出场时间:"))

        self.remove_time_option_group = QButtonGroup()
        self.remove_current_time_radio = QRadioButton("当前时间")
        self.remove_current_time_radio.setChecked(True)
        self.remove_custom_time_radio = QRadioButton("自定义时间")
        
        # 出场时间部分修改 - 添加信号连接
        self.remove_current_time_radio.toggled.connect(self.update_remove_time_display)
        self.remove_custom_time_radio.toggled.connect(self.update_remove_time_display)

        self.remove_time_display = QLabel()
        self.update_remove_time_display()

        self.set_remove_time_btn = QPushButton("设置时间")
        self.set_remove_time_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.set_remove_time_btn.clicked.connect(self.set_custom_remove_time)
        self.set_remove_time_btn.setEnabled(False)

        time_option_layout.addWidget(self.remove_current_time_radio)
        time_option_layout.addWidget(self.remove_custom_time_radio)
        time_option_layout.addWidget(self.remove_time_display)
        time_option_layout.addWidget(self.set_remove_time_btn)
        time_option_layout.addStretch()
        remove_layout.addLayout(time_option_layout)

        # 连接信号
        self.remove_custom_time_radio.toggled.connect(lambda checked: self.set_remove_time_btn.setEnabled(checked))

        # 移除按钮
        remove_btn = QPushButton("车辆出场结算")
        remove_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogCancelButton))
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 5px;
            }
        """)
        remove_btn.clicked.connect(self.remove_car)
        remove_layout.addWidget(remove_btn)

        remove_group.setLayout(remove_layout)
        layout.addWidget(remove_group)
        
        # 车位状态
        self.space_label = QLabel()
        self.space_label.setAlignment(Qt.AlignCenter)
        self.space_label.setStyleSheet("""
            QLabel {
                font-size: 16pt;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
                background-color: #ecf0f1;
            }
        """)
        self.update_space_label()
        layout.addWidget(self.space_label)
        
        # 创建顶部标题栏的水平布局
        header_layout = QHBoxLayout()
        
        # "当前在场车辆"标签
        current_cars_label = QLabel("当前在场车辆")
        current_cars_label.setStyleSheet("""
            font-size: 14pt; 
            font-weight: bold; 
            color: #2c3e50; 
        """)
        header_layout.addWidget(current_cars_label)
        
        # 添加弹簧，使按钮在右侧对齐
        header_layout.addStretch()
        
        # 刷新和导出按钮
        refresh_btn = QPushButton("刷新表格")
        refresh_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_BrowserReload))
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                padding: 6px;
                border-radius: 4px;
            }
        """)
        refresh_btn.clicked.connect(self.update_car_table)
        
        export_btn = QPushButton("导出表格")
        export_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogSaveButton))
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 6px;
                border-radius: 4px;
            }
        """)
        export_btn.clicked.connect(lambda: self.export_table(self.table, "在场车辆"))
        
        # 按钮水平布局
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(export_btn)
        
        header_layout.addLayout(btn_layout)
        
        # 添加标题栏到主布局
        layout.addLayout(header_layout)
        # ======== 修改结束 ========
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["车牌号", "车型", "入场时间", "停车时长(小时)", "费用(元)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_car_context_menu)
        self.table.setSortingEnabled(True)
        
        # 添加单击事件：当用户单击车牌号时，自动填充到移除车辆栏
        self.table.itemClicked.connect(self.handle_table_item_click)
        
        layout.addWidget(self.table)
        
        # 连接信号
        self.custom_time_radio.toggled.connect(lambda checked: self.set_time_btn.setEnabled(checked))
        
        # 初始化表格
        self.update_car_table()
        
        # 设置布局边距
        layout.setContentsMargins(15, 15, 15, 15)
    
    def setup_data_tab(self, tab):
        layout = QVBoxLayout(tab)
        layout.setSpacing(20)
        
        # 管理员信息部分
        admin_group = QGroupBox("管理员信息")
        admin_layout = QVBoxLayout()
        
        # 显示当前管理员信息
        self.admin_info_label = QLabel()
        self.update_admin_info()
        self.admin_info_label.setStyleSheet("font-size: 12pt; padding: 10px;")
        admin_layout.addWidget(self.admin_info_label)
        
        # 修改管理员信息按钮
        edit_admin_btn = QPushButton("修改管理员信息")
        edit_admin_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        edit_admin_btn.clicked.connect(self.edit_admin_info)
        admin_layout.addWidget(edit_admin_btn)
        
        admin_group.setLayout(admin_layout)
        layout.addWidget(admin_group)
        
        # 文件操作部分
        file_group = QGroupBox("文件操作")
        file_layout = QVBoxLayout()
        
        # 保存文件选项
        save_layout = QHBoxLayout()
        save_layout.addWidget(QLabel("保存到:"))
        
        self.save_path_input = QLineEdit()
        self.save_path_input.setPlaceholderText("选择保存位置...")
        save_layout.addWidget(self.save_path_input)
        
        browse_save_btn = QPushButton("浏览...")
        browse_save_btn.clicked.connect(self.browse_save_location)
        save_layout.addWidget(browse_save_btn)
        
        file_layout.addLayout(save_layout)
        
        # 加密选项
        self.encrypt_check = QCheckBox("加密保存文件")
        file_layout.addWidget(self.encrypt_check)
        
        # 保存按钮
        save_btn = QPushButton("保存系统数据")
        save_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogSaveButton))
        save_btn.setStyleSheet("background-color: #3498db; color: white; padding: 8px;")
        save_btn.clicked.connect(self.save_system_data)
        file_layout.addWidget(save_btn)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        file_layout.addWidget(separator)
        
        # 加载文件选项
        load_layout = QHBoxLayout()
        load_layout.addWidget(QLabel("从文件加载:"))
        
        self.load_path_input = QLineEdit()
        self.load_path_input.setPlaceholderText("选择系统文件...")
        self.load_path_input.textChanged.connect(self.check_file_exists)
        load_layout.addWidget(self.load_path_input)
        
        browse_load_btn = QPushButton("浏览...")
        browse_load_btn.clicked.connect(self.browse_load_location)
        load_layout.addWidget(browse_load_btn)
        
        file_layout.addLayout(load_layout)
        
        self.file_status_label = QLabel()
        self.file_status_label.setStyleSheet("font-size: 10pt; padding: 5px;")
        file_layout.addWidget(self.file_status_label)
        
        # 加载按钮
        load_btn = QPushButton("加载系统数据")
        load_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogOpenButton))
        load_btn.setStyleSheet("background-color: #2ecc71; color: white; padding: 8px;")
        load_btn.clicked.connect(self.load_system_data)
        file_layout.addWidget(load_btn)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # 历史记录部分
        history_group = QGroupBox("历史停车记录")
        history_layout = QVBoxLayout()
        
        # 添加导出按钮
        history_btn_layout = QHBoxLayout()
        history_btn_layout.addStretch()
        
        export_history_btn = QPushButton("导出历史停车记录")
        export_history_btn.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogSaveButton))
        export_history_btn.setStyleSheet("background-color: #3498db; color: white; padding: 8px; border-radius: 5px;")
        export_history_btn.clicked.connect(lambda: self.export_table(self.history_table, "历史记录"))
        history_btn_layout.addWidget(export_history_btn)
        
        history_layout.addLayout(history_btn_layout)
        
        # 历史记录表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels(["车牌号", "车型", "入场时间", "出场时间", "停车时长(小时)", "费用(元)"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setSortingEnabled(True)
        
        # 添加历史记录的右键菜单
        self.history_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_table.customContextMenuRequested.connect(self.show_history_context_menu)
        
        history_layout.addWidget(self.history_table)
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)
        
        # 初始化表格
        self.update_history_table()
        
        # 设置布局边距
        layout.setContentsMargins(15, 15, 15, 15)
    
    # 处理表格项点击事件
    def handle_table_item_click(self, item):
        """当用户点击表格项时，如果是车牌号列，则填充到移除车辆栏"""
        if item.column() == 0:  # 车牌号列
            plate_number = item.text()
            self.remove_plate_input.setText(plate_number)
    
    # 显示历史记录的右键菜单
    def show_history_context_menu(self, position):
        """显示历史记录表格的右键菜单"""
        # 获取点击的行
        row = self.history_table.rowAt(position.y())
        if row < 0:
            return
            
        menu = QMenu()
        delete_action = QAction("删除历史记录", self)
        delete_action.triggered.connect(lambda: self.delete_history_record(row))
        menu.addAction(delete_action)
        
        menu.exec_(self.history_table.viewport().mapToGlobal(position))
    
    # 删除历史记录
    def delete_history_record(self, row):
        """删除指定的历史记录"""
        if row < 0 or row >= len(self.system.parking_history):
            return
            
        car = self.system.parking_history[row]
        plate_number = car.number
        
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除车牌号 {plate_number} 的历史记录吗?\n此操作不可恢复!",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 从系统中删除
            del self.system.parking_history[row]
            # 更新历史记录表格
            self.update_history_table()
            QMessageBox.information(self, "删除成功", f"车牌号 {plate_number} 的历史记录已删除")
            
    def update_time(self):
        """更新当前时间显示"""
        current_time = self.custom_time if self.custom_time else datetime.now()
        self.time_label.setText(current_time.strftime("%Y-%m-%d %H:%M:%S"))
    
    def set_custom_time(self):
        """设置自定义当前时间"""
        initial_time = self.custom_time if self.custom_time else datetime.now()
        dialog = TimeDialog("设置自定义时间", initial_time, self)
        if dialog.exec_() == QDialog.Accepted:
            self.custom_time = dialog.get_time()
            self.clear_time_btn.setEnabled(True)
            self.update_time()
            self.update_car_table()
            
            # 启动自定义时间定时器
            self.custom_time_timer.start(1000)
    
    def update_custom_time(self):
        """每秒更新自定义时间"""
        if self.custom_time:
            # 每秒递增时间
            self.custom_time += timedelta(seconds=1)
            self.update_time()
            self.update_car_table()
    
    def clear_custom_time(self):
        """清除自定义时间"""
        self.custom_time = None
        self.clear_time_btn.setEnabled(False)
        self.update_time()
        self.update_car_table()
        
        # 停止自定义时间定时器
        self.custom_time_timer.stop()
    
    def update_enter_time_display(self):
        """更新入场时间显示"""
        if self.custom_time_radio.isChecked() and self.custom_enter_time:
            time_str = self.custom_enter_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = "使用当前时间"
        self.time_display.setText(f"<b>{time_str}</b>")
    
    def update_remove_time_display(self):
        """更新出场时间显示"""
        if self.remove_custom_time_radio.isChecked() and self.custom_remove_time:
            time_str = self.custom_remove_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = "使用当前时间"
        self.remove_time_display.setText(f"<b>{time_str}</b>")
    
    def update_space_label(self):
        """更新车位状态标签"""
        available = self.system.available_spaces()
        total = self.system.max_spaces
        used = total - available
        
        if available == 0:
            color = "#e74c3c"  # 红色
        elif available < total * 0.3:
            color = "#f39c12"  # 橙色
        else:
            color = "#27ae60"  # 绿色
            
        self.space_label.setText(
            f"<center>"
            f"<span style='font-size: 24pt; color: {color};'>{available}</span>"
            f"<span style='font-size: 18pt;'>/{total}</span><br>"
            f"<span style='font-size: 14pt;'>可用车位</span><br>"
            f"<span style='font-size: 12pt;'>(已使用: {used})</span>"
            f"</center>"
        )
    
    def update_admin_info(self):
        """更新管理员信息显示"""
        try:
            manager = self.system.manager
            password_set = "已设置" if manager.key else "未设置"
            self.admin_info_label.setText(
                f"<b>管理员ID:</b> {manager.id}<br>"
                f"<b>密码状态:</b> {password_set}<br>"
                f"<b>累计收费:</b> {manager.total_income}元"
            )
        except Exception as e:
            print(f"更新管理员信息时出错: {str(e)}")
            self.admin_info_label.setText(
                "<b>管理员信息加载错误</b>"
            )
    
    def update_car_table(self):
        """更新当前车辆表格，保持排序状态"""
        # 保存当前的排序状态
        sort_column = self.table.horizontalHeader().sortIndicatorSection()
        sort_order = self.table.horizontalHeader().sortIndicatorOrder()
        
        # 临时禁用排序以避免干扰数据填充
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        
        cars = self.system.cars
        self.table.setRowCount(len(cars))
        
        current_time = self.custom_time if self.custom_time else datetime.now()
        current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        
        for i, car in enumerate(cars):
            try:
                # 添加车牌号、车型、入场时间
                self.table.setItem(i, 0, QTableWidgetItem(car.number))
                self.table.setItem(i, 1, QTableWidgetItem(car.model))
                self.table.setItem(i, 2, QTableWidgetItem(car.enter_time))
                
                # 计算停车时长
                if car.enter_time:
                    try:
                        enter = to_datetime(car.enter_time)
                        duration = current_time - enter
                        hours = round(duration.total_seconds() / 3600, 2)
                        self.table.setItem(i, 3, QTableWidgetItem(f"{hours:.2f}"))
                        
                        # 计算费用
                        cost = self.calculate_cost_for_display(car, current_time_str)
                        self.table.setItem(i, 4, QTableWidgetItem(f"{cost:.2f}"))
                    except Exception as e:
                        print(f"计算费用错误: {str(e)}")
                        self.table.setItem(i, 3, QTableWidgetItem("错误"))
                        self.table.setItem(i, 4, QTableWidgetItem("0"))
                else:
                    self.table.setItem(i, 3, QTableWidgetItem("N/A"))
                    self.table.setItem(i, 4, QTableWidgetItem("0"))
            except Exception as e:
                print(f"更新车辆表格时出错: {str(e)}")
                self.table.setItem(i, 3, QTableWidgetItem("错误"))
                self.table.setItem(i, 4, QTableWidgetItem("0"))
        
        # 恢复排序状态
        self.table.setSortingEnabled(True)
        if sort_column >= 0:  # 确保有有效的排序列
            self.table.sortItems(sort_column, sort_order)
            self.table.horizontalHeader().setSortIndicator(sort_column, sort_order)
    
    def calculate_cost_for_display(self, car, current_time_str):
        """为显示目的计算车辆费用（不修改车辆的实际出场时间）"""
        if not car.enter_time:
            return 0
            
        try:
            enter = to_datetime(car.enter_time)
            quit = to_datetime(current_time_str)
        except ValueError:
            return 0
            
        # 计算总小时数（带小数）
        hours = (quit - enter).total_seconds() / 3600
        
        # 向上取整：不足一小时按一小时计算
        hours = int(hours) if hours.is_integer() else int(hours) + 1
        return hours * car.price
    
    def update_history_table(self):
        """更新历史记录表格"""
        history = self.system.parking_history
        self.history_table.setRowCount(len(history))
        
        for i, car in enumerate(history):
            try:
                self.history_table.setItem(i, 0, QTableWidgetItem(car.number))
                self.history_table.setItem(i, 1, QTableWidgetItem(car.model))
                self.history_table.setItem(i, 2, QTableWidgetItem(car.enter_time))
                self.history_table.setItem(i, 3, QTableWidgetItem(car.quit_time or ""))
                
                # 计算停车时长和费用
                if car.enter_time and car.quit_time:
                    enter = to_datetime(car.enter_time)
                    quit = to_datetime(car.quit_time)
                    hours = round((quit - enter).total_seconds() / 3600, 2)
                    self.history_table.setItem(i, 4, QTableWidgetItem(f"{hours}"))
                    self.history_table.setItem(i, 5, QTableWidgetItem(f"{car.cost}"))
                else:
                    self.history_table.setItem(i, 4, QTableWidgetItem("N/A"))
                    self.history_table.setItem(i, 5, QTableWidgetItem("0"))
            except Exception:
                self.history_table.setItem(i, 4, QTableWidgetItem("错误"))
                self.history_table.setItem(i, 5, QTableWidgetItem("0"))
    
    def set_custom_enter_time(self):
        """设置自定义入场时间 - 使用程序当前时间"""
        current_time = self.custom_time if self.custom_time else datetime.now()
        dialog = TimeDialog("设置入场时间", current_time, self)
        if dialog.exec_() == QDialog.Accepted:
            self.custom_enter_time = dialog.get_time()
            self.update_enter_time_display()
   
    def set_custom_remove_time(self):
        """设置自定义出场时间 - 使用程序当前时间"""
        current_time = self.custom_time if self.custom_time else datetime.now()
        dialog = TimeDialog("设置出场时间", current_time, self)
        if dialog.exec_() == QDialog.Accepted:
            self.custom_remove_time = dialog.get_time()
            self.update_remove_time_display()
            
    def add_car(self):
        """添加车辆入场"""
        number = self.plate_input.text().strip()
        if not number:
            QMessageBox.warning(self, "输入错误", "请输入车牌号")
            return
            
        # 检查车牌号是否重复
        if any(c.number == number for c in self.system.cars):
            QMessageBox.warning(self, "错误", "该车辆已在停车场中")
            return
            
        # 检查车位是否已满
        if self.system.available_spaces() <= 0:
            QMessageBox.warning(self, "车位已满", "当前停车场车位已满，无法再容纳更多车辆！")
            return
            
        model = self.model_combo.currentText()
        price = ParkingSystem.MODEL_PRICES[model]
        
        # 确定入场时间
        if self.custom_time_radio.isChecked() and self.custom_enter_time:
            enter_time = self.custom_enter_time
        else:
            # 使用程序当前时间（自定义时间或系统时间）
            enter_time = self.custom_time if self.custom_time else datetime.now()
        
        new_car = Car(number, model, to_str(enter_time), None, price)
        result = self.system.add_car(new_car)
        
        if result:
            QMessageBox.warning(self, "错误", result)
            return
            
        # 更新界面
        self.plate_input.clear()
        self.custom_enter_time = None
        self.update_car_table()
        self.update_space_label()
        self.update_enter_time_display()
        
        QMessageBox.information(self, "入场成功", f"车辆 {number} 已成功入场")

        # 添加功能：检查剩余车位是否为0
        if self.system.available_spaces() == 0:
            QMessageBox.warning(self, "车位已满", "当前停车场车位已满，无法再容纳更多车辆！")
    
    def remove_car(self):
        """移除车辆（出场结算） - 使用程序当前时间"""
        number = self.remove_plate_input.text().strip()
        if not number:
            QMessageBox.warning(self, "输入错误", "请输入车牌号")
            return
            
        # 确定出场时间 - 使用程序当前时间
        if self.remove_custom_time_radio.isChecked() and self.custom_remove_time:
            quit_time = self.custom_remove_time
        else:
            # 使用程序当前时间（自定义时间或系统时间）
            quit_time = self.custom_time if self.custom_time else datetime.now()
        
        # 验证车辆是否存在
        car = next((c for c in self.system.cars if c.number == number), None)
        if not car:
            QMessageBox.warning(self, "错误", "找不到该车辆")
            return
            
        # 验证出场时间不早于入场时间
        try:
            enter_time = to_datetime(car.enter_time)
            if quit_time < enter_time:
                QMessageBox.warning(self, "时间错误", "出场时间不能早于入场时间")
                return
        except Exception as e:
            print(f"时间格式错误: {str(e)}")
            QMessageBox.warning(self, "错误", "时间格式不正确")
            return
        
        # 移除车辆
        result = self.system.remove_car(number, to_str(quit_time))
        if not result:
            QMessageBox.warning(self, "错误", "移除车辆失败")
            return
            
        # 更新界面
        self.remove_plate_input.clear()
        self.custom_remove_time = None
        self.update_car_table()
        self.update_space_label()
        self.update_admin_info()
        self.update_history_table()
        self.update_remove_time_display()
        
        QMessageBox.information(self, "结算完成", f"车辆 {number} 已出场\n费用: {result.cost}元")
        
    def show_car_context_menu(self, position):
        """显示车辆表格的右键菜单"""
        menu = QMenu()
        
        edit_action = QAction("修改车辆信息", self)
        edit_action.triggered.connect(self.edit_car)
        
        delete_action = QAction("删除车辆记录", self)
        delete_action.triggered.connect(self.delete_car)
        
        menu.addAction(edit_action)
        menu.addAction(delete_action)
        
        menu.exec_(self.table.viewport().mapToGlobal(position))
    
    def edit_car(self):
        """编辑车辆信息"""
        selected_row = self.table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "选择错误", "请先选择要编辑的车辆")
            return
            
        car_number = self.table.item(selected_row, 0).text()
        car = next((c for c in self.system.cars if c.number == car_number), None)
        
        if not car:
            return
            
        dialog = CarEditDialog(car, self)
        if dialog.exec_() == QDialog.Accepted and dialog.modified:
            # 如果车辆状态从未出场变为已出场
            if dialog.status_changed:
                # 从当前车辆列表中移除
                if car in self.system.cars:
                    self.system.cars.remove(car)
                # 添加到历史记录
                self.system.parking_history.append(car)
                # 更新累计收费
                self.system.manager.add_income(car.cost)
                
            self.update_car_table()
            self.update_space_label()
            self.update_admin_info()
            self.update_history_table()
            
            QMessageBox.information(self, "修改成功", "车辆信息已更新")
    
    def delete_car(self):
        """删除车辆记录"""
        selected_row = self.table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "选择错误", "请先选择要删除的车辆")
            return
            
        car_number = self.table.item(selected_row, 0).text()
        
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除车辆 {car_number} 的记录吗?\n此操作不可恢复!",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
            
        # 从系统中删除
        car = next((c for c in self.system.cars if c.number == car_number), None)
        if car:
            self.system.cars.remove(car)
            
        # 更新界面
        self.update_car_table()
        self.update_space_label()
        
        QMessageBox.information(self, "删除成功", f"车辆 {car_number} 的记录已删除")
    
    def edit_admin_info(self):
        # 计算当前已使用车位数
        current_used_spaces = len(self.system.cars)
        
        # 传递当前的最大车位数和当前已使用车位数
        dialog = AdminEditDialog(
            self.system.manager, 
            self.system.max_spaces,
            current_used_spaces,
            self
        )
        
        if dialog.exec_() == QDialog.Accepted and dialog.modified:
            # 更新最大车位数
            self.system.max_spaces = dialog.max_spaces
            self.update_admin_info()
            self.update_space_label()  # 更新车位状态显示
            
            QMessageBox.information(self, "修改成功", "管理员信息及车位设置已更新")
    
    def browse_save_location(self):
        """浏览保存位置"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存系统数据", "", "Parking System Files (*.psys);;All Files (*)"
        )
        if file_path:
            # 确保文件扩展名正确
            if not file_path.lower().endswith('.psys'):
                file_path += '.psys'
            self.save_path_input.setText(file_path)
    
    def save_system_data(self):
        """保存系统数据到文件"""
        file_path = self.save_path_input.text().strip()
        if not file_path:
            QMessageBox.warning(self, "路径错误", "请选择保存位置")
            return
            
        encrypt = self.encrypt_check.isChecked()
        password = ""
        
        # 如果设置了加密但管理员没有密码，需要输入密码
        if encrypt and not self.system.manager.key:
            password, ok = QInputDialog.getText(
                self, "设置加密密码", 
                "请输入加密密码(将用于解密文件):",
                QLineEdit.Password
            )
            if not ok or not password:
                QMessageBox.warning(self, "密码错误", "必须提供加密密码")
                return
                
        # 保存文件
        success = self.system.save_to_file(file_path, encrypt, password)
        if success:
            QMessageBox.information(self, "保存成功", "系统数据已成功保存")
            self.file_status_label.setText("文件保存成功")
            self.file_status_label.setStyleSheet("color: green;")
        else:
            QMessageBox.warning(self, "保存失败", "保存文件时出错")
            self.file_status_label.setText("保存失败，请重试")
            self.file_status_label.setStyleSheet("color: red;")
    
    def browse_load_location(self):
        """浏览加载位置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "加载系统数据", "", "Parking System Files (*.psys);;All Files (*)"
        )
        if file_path:
            self.load_path_input.setText(file_path)
            self.check_file_exists(file_path)
    
    def check_file_exists(self, file_path=None):
        """检查文件是否存在并更新状态"""
        if file_path is None:
            file_path = self.load_path_input.text().strip()
            
        if not file_path:
            self.file_status_label.setText("")
            return
            
        if os.path.exists(file_path):
            self.file_status_label.setText("文件存在")
            self.file_status_label.setStyleSheet("color: #7f8c8d;")
        else:
            self.file_status_label.setText("文件不存在")
            self.file_status_label.setStyleSheet("color: red;")
    
    def load_system_data(self):
        """从文件加载系统数据"""
        file_path = self.load_path_input.text().strip()
        if not file_path:
            QMessageBox.warning(self, "路径错误", "请选择要加载的文件")
            return
            
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "文件不存在", "指定的文件不存在")
            return
            
        # 尝试加载文件
        temp_system = ParkingSystem()
        password = ""
        
        # 第一次尝试加载（可能不需要密码）
        success, message = temp_system.load_from_file(file_path, password)
        
        if not success and "需要密码" in message:
            # 如果需要密码，弹出输入对话框
            password, ok = QInputDialog.getText(
                self, "文件加密", 
                "该文件已被加密，请输入解密密码:",
                QLineEdit.Password
            )
            if not ok:
                return  # 用户取消输入
                
            # 使用输入的密码再次尝试加载
            success, message = temp_system.load_from_file(file_path, password)
        
        if success:
            # 加载成功，替换当前系统
            self.system = temp_system
            self.update_car_table()
            self.update_history_table()
            self.update_space_label()
            self.update_admin_info()
            
            # 清除自定义时间
            self.custom_time = None
            self.clear_time_btn.setEnabled(False)
            self.update_time()
            
            QMessageBox.information(self, "加载成功", "系统数据已成功加载")
            self.file_status_label.setText("加载成功")
            self.file_status_label.setStyleSheet("color: green;")
        else:
            QMessageBox.warning(self, "加载失败", message)
            self.file_status_label.setText(f"加载失败: {message}")
            self.file_status_label.setStyleSheet("color: red;")

    def export_table(self, table_widget, table_name):
        """导出表格数据到文件"""
        if table_widget.rowCount() == 0:
            QMessageBox.warning(self, "无数据", f"当前没有{table_name}数据可导出")
            return
        
        # 获取保存路径和格式
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, 
            f"导出{table_name}数据", 
            os.path.expanduser(f"~/Desktop/{table_name}数据"),
            "CSV文件 (*.csv);;Excel 97-2003 (*.xls);;Excel文件 (*.xlsx)"
        )
        
        if not file_path:
            return  # 用户取消
        
        # 根据选择的格式添加扩展名
        if selected_filter == "CSV文件 (*.csv)" and not file_path.lower().endswith('.csv'):
            file_path += '.csv'
        elif selected_filter == "Excel 97-2003 (*.xls)" and not file_path.lower().endswith('.xls'):
            file_path += '.xls'
        elif selected_filter == "Excel文件 (*.xlsx)" and not file_path.lower().endswith('.xlsx'):
            file_path += '.xlsx'
        
        try:
            # 获取表头
            headers = []
            for col in range(table_widget.columnCount()):
                headers.append(table_widget.horizontalHeaderItem(col).text())
            
            # 获取数据
            data = []
            for row in range(table_widget.rowCount()):
                row_data = []
                for col in range(table_widget.columnCount()):
                    item = table_widget.item(row, col)
                    row_data.append(item.text() if item else "")
                data.append(row_data)
            
            # 根据格式导出
            if file_path.lower().endswith('.csv'):
                self.export_to_csv(file_path, headers, data)
            elif file_path.lower().endswith('.xls'):
                self.export_to_xls(file_path, headers, data)
            elif file_path.lower().endswith('.xlsx'):
                self.export_to_xlsx(file_path, headers, data)
            
            QMessageBox.information(self, "导出成功", f"{table_name}数据已成功导出到:\n{file_path}")
        
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出过程中发生错误:\n{str(e)}")

    def export_to_csv(self, file_path, headers, data):
        """导出为CSV格式"""
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(data)

    def export_to_xls(self, file_path, headers, data):
        """导出为XLS格式"""
        workbook = xlwt.Workbook(encoding='utf-8')
        sheet = workbook.add_sheet('停车场数据')
        
        # 设置标题样式
        header_style = xlwt.easyxf(
            'font: bold on; align: vertical center, horizontal center;'
        )
        
        # 写入表头
        for col, header in enumerate(headers):
            sheet.write(0, col, header, header_style)
            # 设置列宽
            sheet.col(col).width = 256 * (len(header) + 5)
        
        # 写入数据
        for row_idx, row_data in enumerate(data, start=1):
            for col_idx, value in enumerate(row_data):
                sheet.write(row_idx, col_idx, value)
        
        workbook.save(file_path)

    def export_to_xlsx(self, file_path, headers, data):
        """导出为XLSX格式"""
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "停车场数据"
        
        # 写入表头
        sheet.append(headers)
        
        # 设置表头样式
        for cell in sheet[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # 写入数据
        for row_data in data:
            sheet.append(row_data)
        
        # 自动调整列宽
        for column in sheet.columns:
            max_length = 0
            column = [cell for cell in column]
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(cell.value)
                except:
                    pass
            adjusted_width = (max_length + 2)
            sheet.column_dimensions[column[0].column_letter].width = adjusted_width
        
        workbook.save(file_path)
    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 先显示初始化窗口
    init_window = InitialWindow()
    if init_window.exec_() == QDialog.Accepted:
        system = init_window.get_system()
        if system:
            # 初始化成功，显示主界面
            window = ParkingApp(system)
            window.show()
            sys.exit(app.exec_())
        else:
            QMessageBox.critical(None, "初始化失败", "无法初始化系统，程序将退出")
            sys.exit(1)
    else:
        # 用户取消初始化
        sys.exit(0)   
