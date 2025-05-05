import sys
import os
import subprocess
import serial
import serial.tools.list_ports
from serial.serialutil import SerialException
from PyQt5.QtGui import QColor, QTextCursor, QKeySequence, QFont, QTextCharFormat, QSyntaxHighlighter, QTextFormat, QPainter, QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, QFile, QTextStream, QSettings, QRegularExpression, QStringListModel, QDir
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QGroupBox,
    QMessageBox, QFileDialog, QTabWidget, QTextEdit, QToolBar,
    QAction, QStatusBar, QSplitter, QPlainTextEdit, QShortcut, QSizePolicy, QCompleter, QTreeView, QDialog, QFormLayout, QMenuBar, QMenu, QWidgetAction
)

import zipfile
import tempfile
import shutil
import json
from pathlib import Path

import threading
import re
from PyQt5.QtWidgets import QProgressBar

#os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = 'C:/Users/洛崽崽/AppData/Local/Programs/Python/Python38/Lib/site-packages/PyQt5/Qt/plugins'

class UploadConsoleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("上传控制台")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout()
        
        # 控制台输出
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #D4D4D4;
                font-family: Consolas;
                font-size: 10pt;
            }
        """)
        layout.addWidget(self.console)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 3px;
                text-align: center;
                background-color: #333333;
            }
            QProgressBar::chunk {
                background-color: #0e639c;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # 关闭按钮
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        layout.addWidget(self.close_btn)
        
        self.setLayout(layout)
    
    def append_log(self, text):
        self.console.append(text)
        self.console.moveCursor(QTextCursor.End)
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)

class Project:
    def __init__(self, name="Untitled", path=None, project_type="empty"):
        self.name = name
        self.path = path  # 项目根目录
        self.type = project_type
        self.files = []  # 存储相对路径
        self.settings = {}
        
    def add_file(self, file_path):
        if self.path:
            # 转换为相对于项目目录的路径
            rel_path = os.path.relpath(file_path, self.path)
            if rel_path not in self.files:
                self.files.append(rel_path)
        else:
            # 如果没有项目目录，暂时存储绝对路径
            if file_path not in self.files:
                self.files.append(file_path)
            
    def remove_file(self, file_path):
        if self.path:
            rel_path = os.path.relpath(file_path, self.path)
            if rel_path in self.files:
                self.files.remove(rel_path)
        else:
            if file_path in self.files:
                self.files.remove(file_path)
            
    def save_project_file(self):
        if not self.path:
            return False
            
        project_file = os.path.join(self.path, f"{self.name}.nsproject")
        project_data = {
            "name": self.name,
            "type": self.type,
            "files": [os.path.relpath(f, self.path) if os.path.isabs(f) else f 
                    for f in self.files],  # Ensure all paths are relative
            "settings": self.settings
        }
        
        with open(project_file, 'w') as f:
            json.dump(project_data, f, indent=4)
            
        return True
        
    @staticmethod
    def load_project_file(project_path):
        try:
            with open(project_path, 'r') as f:
                data = json.load(f)
                
            project_dir = os.path.dirname(project_path)
            project = Project(
                name=data.get('name', 'Untitled'),
                path=project_dir,
                project_type=data.get('type', 'empty')
            )
            
            # 将相对路径转换为绝对路径，同时确保路径存在
            files = data.get('files', [])
            project.files = []
            for f in files:
                abs_path = os.path.normpath(os.path.join(project_dir, f))
                if os.path.exists(abs_path):
                    project.files.append(abs_path)
                else:
                    print(f"警告: 文件不存在，已跳过: {abs_path}")
            
            project.settings = data.get('settings', {})
            
            return project
        except Exception as e:
            print(f"加载项目失败: {e}")
            return None
            
    def export_project(self, output_path):
        if not self.path:
            return False
            
        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add project metadata
                self.save_project_file()
                project_file = os.path.join(self.path, f"{self.name}.nsproject")
                zipf.write(project_file, os.path.basename(project_file))
                
                # Add all project files
                for file in self.files:
                    # Get absolute path of the file
                    abs_file = os.path.normpath(os.path.join(self.path, file)) if not os.path.isabs(file) else file
                    if os.path.exists(abs_file):
                        # In zip file, maintain relative path structure from project root
                        arcname = os.path.relpath(abs_file, self.path) if os.path.isabs(file) else file
                        zipf.write(abs_file, arcname)
                        
            return True
        except Exception as e:
            print(f"导出项目失败: {e}")
            return False
            
    @staticmethod
    def import_project(project_path, target_dir):
        try:
            with zipfile.ZipFile(project_path, 'r') as zipf:
                # Extract all files while preserving directory structure
                zipf.extractall(target_dir)
                
                # Find the project file
                for name in zipf.namelist():
                    if name.endswith('.nsproject'):
                        project_file = os.path.join(target_dir, name)
                        project = Project.load_project_file(project_file)
                        
                        # Ensure all files in project use relative paths
                        if project:
                            project.files = [os.path.relpath(
                                os.path.normpath(os.path.join(target_dir, f)), 
                                target_dir
                            ) for f in project.files]
                        return project
                        
            return None
        except Exception as e:
            print(f"加载项目失败: {e}")
            return None
        
class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setStyleSheet("""
            QDialog {
                background-color: #252526;
            }
            QLabel {
                color: #d4d4d4;
            }
            QLineEdit, QComboBox {
                background-color: #333333;
                color: #d4d4d4;
                border: 1px solid #444;
                padding: 5px;
                min-height: 25px;
            }
            QPushButton {
                min-width: 80px;
                padding: 5px;
            }
        """)
        
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Project name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("项目名称:"))
        self.name_edit = QLineEdit()
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)
        
        # Project location
        location_layout = QHBoxLayout()
        location_layout.addWidget(QLabel("保存路径:"))
        self.location_edit = QLineEdit()
        self.location_edit.setText(os.path.expanduser("~"))
        browse_btn = QPushButton("选择...")
        browse_btn.clicked.connect(self.browse_location)
        location_layout.addWidget(self.location_edit)
        location_layout.addWidget(browse_btn)
        layout.addLayout(location_layout)
        
        # Project type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("项目类型:"))
        self.type_combo = QComboBox()
        self.type_combo.addItem("Empty Project", "empty")
        self.type_combo.addItem("MakeX Competition DemoA", "makex_demoA")
        self.type_combo.addItem("MakeX Competition DemoB", "makex_demoB")
        
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("创建")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
    def browse_location(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, 
            "选择存放位置", 
            self.location_edit.text()
        )
        if dir_path:
            self.location_edit.setText(dir_path)
            
    def get_project_info(self):
        return {
            "name": self.name_edit.text(),
            "path": self.location_edit.text(),
            "type": self.type_combo.currentData()
        }

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        keyword_format.setFontWeight(QFont.Bold)

        self.highlighting_rules = [
            (r'\b(and|as|assert|break|class|continue|def|del|elif|else|except|'
             r'finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|'
             r'pass|raise|return|try|while|with|yield|True|False|None)\b',
             keyword_format)
        ]

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))
        self.highlighting_rules.append((r'"[^"\\]*(\\.[^"\\]*)*"', string_format))
        self.highlighting_rules.append((r"'[^'\\]*(\\.[^'\\]*)*'", string_format))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
        self.highlighting_rules.append((r'#[^\n]*', comment_format))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#B5CEA8"))
        self.highlighting_rules.append((r'\b[0-9]+\b', number_format))

        self_format = QTextCharFormat()
        self_format.setForeground(QColor("#569CD6"))
        self.highlighting_rules.append((r'\bself\b', self_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            expression = QRegularExpression(pattern)
            match_iterator = expression.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)


class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1E1E1E;
                color: #D4D4D4;
                font-family: Consolas;
                font-size: 12pt;
                selection-background-color: #264F78;
                selection-color: #FFFFFF;
            }
        """)
        self.highlighter = PythonHighlighter(self.document())
        self.setLineWrapMode(QPlainTextEdit.NoWrap)

        # 设置边距
        self.setViewportMargins(40, 0, 0, 0)

        # 行号区域
        self.line_number_area = LineNumberArea(self)

        # 连接信号
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        # 初始化
        self.update_line_number_area_width()
        self.highlight_current_line()

        # 自动补全设置
        self.completer = QCompleter()
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.activated.connect(self.insert_completion)

        # Python 关键字列表
        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def", "del",
            "elif", "else", "except", "finally", "for", "from", "global", "if",
            "import", "in", "is", "lambda", "nonlocal", "not", "or", "pass",
            "raise", "return", "try", "while", "with", "yield", "True", "False", "None"
        ]
        self.model = QStringListModel(keywords, self.completer)
        self.completer.setModel(self.model)

    def insert_completion(self, completion):
        tc = self.textCursor()
        # 获取当前补全前缀
        completionPrefix = self.completer.completionPrefix()
        # 删除当前补全前缀
        tc.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, len(completionPrefix))
        tc.movePosition(QTextCursor.EndOfWord, QTextCursor.KeepAnchor)
        tc.removeSelectedText()
        # 插入完整的补全内容
        tc.insertText(completion)
        self.setTextCursor(tc)

    def text_under_cursor(self):
        tc = self.textCursor()
        tc.select(QTextCursor.WordUnderCursor)
        return tc.selectedText()

    def focusInEvent(self, event):
        if self.completer:
            self.completer.setWidget(self)
        super().focusInEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_ParenLeft, Qt.Key_QuoteDbl, Qt.Key_Apostrophe):
            self.insert_pair(event.text())
            return

        if self.completer and self.completer.popup().isVisible():
            if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab):
                event.ignore()
                return

        is_shortcut = ((event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_E)
        if not self.completer or not is_shortcut:
            super().keyPressEvent(event)

        ctrlOrShift = event.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.ShiftModifier)
        if not self.completer or (ctrlOrShift and len(event.text()) == 0):
            return

        eow = "~!@#$%^&*()_+{}|:\"<>?,./;'[]\\-="
        hasModifier = (event.modifiers() != Qt.NoModifier) and not ctrlOrShift
        completionPrefix = self.text_under_cursor()

        if not is_shortcut and (hasModifier or len(event.text()) == 0 or len(completionPrefix) < 1 or event.text()[-1] in eow):
            self.completer.popup().hide()
            return

        # 更新自动补全列表
        self.update_completion_list()

        if completionPrefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(completionPrefix)
            self.completer.popup().setCurrentIndex(self.completer.completionModel().index(0, 0))

        cr = self.cursorRect()
        cr.setWidth(self.completer.popup().sizeHintForColumn(0) + self.completer.popup().verticalScrollBar().sizeHint().width())
        self.completer.complete(cr)

    def insert_pair(self, char):
        tc = self.textCursor()
        if char == '(':
            tc.insertText('()')
            tc.movePosition(QTextCursor.Left)
        elif char == '"':
            tc.insertText('""')
            tc.movePosition(QTextCursor.Left)
        elif char == "'":
            tc.insertText("''")
            tc.movePosition(QTextCursor.Left)
        self.setTextCursor(tc)

    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(),
                                         self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            cr.left(), cr.top(),
            self.line_number_area_width(), cr.height()
        )

    def highlight_current_line(self):
        extra_selections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor("#2D2D2D")
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#1E1E1E"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(
            self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        font = painter.font()
        font.setFamily("Consolas")
        font.setPointSize(12)
        painter.setFont(font)

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#858585"))
                painter.drawText(
                    0, top,
                    self.line_number_area.width() - 5,
                    self.fontMetrics().height(),
                    Qt.AlignRight, number
                )

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def update_completion_list(self):
        text = self.toPlainText()
        # 简单的正则表达式来匹配变量和函数名
        pattern = r'\b[a-zA-Z_][a-zA-Z0-9_]*\b'
        expression = QRegularExpression(pattern)
        match_iterator = expression.globalMatch(text)
        words = []
        while match_iterator.hasNext():
            match = match_iterator.next()
            word = match.captured()
            if word not in words:
                words.append(word)

        # Python 关键字列表
        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def", "del",
            "elif", "else", "except", "finally", "for", "from", "global", "if",
            "import", "in", "is", "lambda", "nonlocal", "not", "or", "pass",
            "raise", "return", "try", "while", "with", "yield", "True", "False", "None"
        ]
        all_words = keywords + words
        self.model.setStringList(all_words)


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


class UploadSettingsDialog(QDialog):
    def __init__(self, port_combo, parent=None):
        super().__init__(parent)
        self.setWindowTitle("上传设置")
        self.setStyleSheet("""
            QDialog {
                background-color: #252526;
            }
            QLabel {
                color: #d4d4d4;
            }
            QLineEdit, QComboBox {
                background-color: #333333;
                color: #d4d4d4;
                border: 1px solid #444;
                padding: 5px;
                min-height: 25px;
            }
            QPushButton {
                min-width: 80px;
                padding: 5px;
            }
        """)
        
        layout = QFormLayout()
        layout.setLabelAlignment(Qt.AlignRight)
        
        # 串口选择
        self.port_combo_dialog = QComboBox()
        for i in range(port_combo.count()):
            self.port_combo_dialog.addItem(port_combo.itemText(i), port_combo.itemData(i))
        layout.addRow("目标串口:", self.port_combo_dialog)
        
        # 烧录路径
        self.path_edit = QLineEdit("/flash/main.py")
        layout.addRow("目标路径:", self.path_edit)
        
        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)

    def get_settings(self):
        # 获取串口选择的值
        port = self.port_combo_dialog.currentData()
        # 获取烧录路径的值
        flash_path = self.path_edit.text()
        return port, flash_path


class VSCodeLikeEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NScode Pro V5")
        self.current_file = None
        self.init_ui()
        self.load_settings()
        self.refresh_ports()
        self.show_welcome_page()

    def init_ui(self):
        self.current_project = None

        # 主窗口设置
        self.setMinimumSize(800, 600)

        # 创建中心部件和主布局
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 创建水平分割器
        self.horizontal_splitter = QSplitter(Qt.Horizontal)
        self.main_layout.addWidget(self.horizontal_splitter)

        # 创建侧边栏（文件管理和上传配置）
        self.create_sidebar()

        # 创建垂直分割器
        self.vertical_splitter = QSplitter(Qt.Vertical)
        self.horizontal_splitter.addWidget(self.vertical_splitter)

        # 创建编辑器区域
        self.create_editor_area()

        # 创建欢迎页
        self.create_welcome_page()

        # 创建底部面板（增加控制台）
        self.create_bottom_panel()

        # 创建工具栏（增加运行功能）
        self.create_toolbar()

        # 创建菜单栏
        self.create_menu_bar()

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    def create_menu_bar(self):
        menu_bar = self.menuBar()

        # Modify the file menu to include project operations
        file_menu = self.menuBar().addMenu("文件")
        file_menu.addAction("新建项目", self.new_project)
        file_menu.addAction("打开项目", self.open_project)
        file_menu.addAction("关闭项目", self.close_project)
        file_menu.addSeparator()
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction("导出项目", self.export_project)
        file_menu.addAction("导入项目", self.import_project)
        file_menu.addSeparator()
        file_menu.addAction("退出", self.close)
        
        # 文件菜单
        '''
        file_menu = menu_bar.addMenu("文件")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction("退出", self.close)
        '''

        # 编辑菜单
        edit_menu = menu_bar.addMenu("编辑")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.cut_action)
        edit_menu.addAction(self.copy_action)
        edit_menu.addAction(self.paste_action)

        # 工具菜单
        tools_menu = menu_bar.addMenu("工具")
        tools_menu.addAction("上传到设备", self.show_upload_settings)
        tools_menu.addAction("运行", self.run_file)
        tools_menu.addAction("刷新串口", self.refresh_ports)

        # 帮助菜单
        help_menu = menu_bar.addMenu("帮助")
        help_menu.addAction("关于", self.show_about)

    def new_project(self):
        dialog = NewProjectDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            project_info = dialog.get_project_info()
            
            # Create project directory
            project_dir = os.path.join(project_info['path'], project_info['name'])
            try:
                os.makedirs(project_dir, exist_ok=True)
                
                # Create project
                self.current_project = Project(
                    name=project_info['name'],
                    path=project_dir,
                    project_type=project_info['type']
                )
                
                # Create initial files based on project type
                if project_info['type'] == 'makex_demoA':
                    # Create demo.py from template
                    demo_path = os.path.join(project_dir, 'main.py')
                    try:
                        # Try to copy from local template if exists
                        template_path = os.path.join(os.path.dirname(__file__), 'demoA.py')
                        if os.path.exists(template_path):
                            shutil.copy(template_path, demo_path)
                        else:
                            # Fallback to creating default content
                            with open(demo_path, 'w') as f:
                                f.write("# MakeX Competition Demo\n\n")
                                f.write("def main():\n")
                                f.write("    print('Hello MakeX!')\n\n")
                                f.write("if __name__ == '__main__':\n")
                                f.write("    main()\n")
                        
                        self.current_project.add_file(demo_path)
                        self.load_file(demo_path)
                    except Exception as e:
                        QMessageBox.warning(self, "警告", f"无法创建样例文件: {str(e)}")

                if project_info['type'] == 'makex_demoB':
                    # Create demo.py from template
                    demo_path = os.path.join(project_dir, 'main.py')
                    try:
                        # Try to copy from local template if exists
                        template_path = os.path.join(os.path.dirname(__file__), 'demoB.py')
                        if os.path.exists(template_path):
                            shutil.copy(template_path, demo_path)
                        else:
                            # Fallback to creating default content
                            with open(demo_path, 'w') as f:
                                f.write("# MakeX Competition Demo\n\n")
                                f.write("def main():\n")
                                f.write("    print('Hello MakeX!')\n\n")
                                f.write("if __name__ == '__main__':\n")
                                f.write("    main()\n")
                        
                        self.current_project.add_file(demo_path)
                        self.load_file(demo_path)
                    except Exception as e:
                        QMessageBox.warning(self, "警告", f"无法创建样例文件: {str(e)}")
                
                # Save project file
                self.current_project.save_project_file()
                
                # Update file explorer
                self.load_directory(project_dir)
                
                self.status_bar.showMessage(f"项目创建成功: {project_info['name']}")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法创建项目: {str(e)}")
                self.current_project = None

    def open_project(self):
        project_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Open Project", 
            "", 
            "NScode Projects (*.nsproject)"
        )
        
        if project_path:
            project_dir = os.path.dirname(project_path)
            self.current_project = Project.load_project_file(project_path)
            
            if self.current_project:
                # 加载项目中的第一个有效文件
                for file_path in self.current_project.files:
                    if os.path.exists(file_path):
                        self.load_file(file_path)
                        break
                else:
                    QMessageBox.warning(self, "警告", "项目中未找到可用的文件")
                
                # 更新文件浏览器
                self.load_directory(project_dir)
                
                self.status_bar.showMessage(f"项目已打开: {self.current_project.name}")
            else:
                QMessageBox.critical(self, "错误", "无法打开项目文件")

    def close_project(self):
        self.current_project = None
        self.editor.clear()
        self.file_model.clear()
        self.status_bar.showMessage("项目关闭")

    def export_project(self):
        if not self.current_project:
            QMessageBox.warning(self, "警告", "没有已经打开的项目")
            return
            
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Project",
            f"{self.current_project.name}.nsproject",
            "NScode Projects (*.nsproject)"
        )
        
        if output_path:
            if not output_path.endswith('.nsproject'):
                output_path += '.nsproject'
                
            if self.current_project.export_project(output_path):
                QMessageBox.information(self, "成功", "Project exported successfully")
            else:
                QMessageBox.critical(self, "错误", "Failed to export project")

    def import_project(self):
        project_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Import Project", 
            "", 
            "NScode Projects (*.nsproject)"
        )
        
        if project_path:
            target_dir = QFileDialog.getExistingDirectory(
                self,
                "Select Import Location",
                os.path.expanduser("~")
            )
            
            if target_dir:
                project = Project.import_project(project_path, target_dir)
                if project:
                    self.current_project = project
                    # Load the first file in project
                    if self.current_project.files:
                        self.load_file(self.current_project.files[0])
                    
                    # Update file explorer
                    self.load_directory(target_dir)
                    
                    self.status_bar.showMessage(f"Project imported: {self.current_project.name}")
                else:
                    QMessageBox.critical(self, "Error", "Could not import project")

    def show_about(self):
        QMessageBox.about(self, "关于 NScode Pro V5", 
                         "NScode Pro V5 - Python 代码编辑器\n"
                         "版本: 5.0\n"
                         "作者: 小北ovo\n"
                         "联系方式:wx(Atlas_LX1393)")

    def create_sidebar(self):
        sidebar = QSplitter(Qt.Vertical)
        sidebar.setHandleWidth(2)
        
        # 设置侧边栏整体宽度
        sidebar.setMinimumWidth(100)  # 减小整体宽度
        sidebar.setMaximumWidth(200)

        # 文件管理系统
        self.create_file_explorer()
        sidebar.addWidget(self.file_view)

        # 上传配置区域 - 设置固定高度
        self.create_upload_settings_area()
        self.upload_settings_widget.setFixedHeight(350)  # 减小上传区域高度
        sidebar.addWidget(self.upload_settings_widget)

        # 设置弹性布局策略
        self.horizontal_splitter.addWidget(sidebar)
        self.horizontal_splitter.setSizes([350, 600])  # 调整初始比例 (侧边栏:主区域=1:3)
        self.horizontal_splitter.setStretchFactor(1, 3)  # 主区域弹性伸缩

    def create_upload_settings_area(self):
        self.upload_settings_widget = QWidget()
        self.upload_settings_widget.setStyleSheet("""
            QWidget {
                background-color: #252526;
                border-top: 1px solid #1a1a1a;
                padding: 5px;
            }
            QLabel {
                color: #d4d4d4;
                font-size: 12px;
            }
            QComboBox, QPushButton {
                min-height: 28px;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(self.upload_settings_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)  # 减小间距

        # 串口配置组
        port_group = QGroupBox("串口配置")
        port_group.setStyleSheet("""
            QGroupBox {
                color: #569CD6;
                border: 1px solid #444;
                border-radius: 4px;
                margin-top: 5px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 5px;
            }
        """)
        port_layout = QVBoxLayout(port_group)
        port_layout.setContentsMargins(5, 10, 5, 5)  # 减小内边距
        port_layout.setSpacing(5)

        # 串口选择行
        port_row = QHBoxLayout()
        self.port_combo = QComboBox()
        self.port_combo.setStyleSheet("""
            QComboBox {
                background-color: #333333;
                color: #d4d4d4;
                border: 1px solid #444;
                padding: 0 5px;
                max-height: 28px;
            }
            QComboBox:hover {
                border-color: #555;
            }
            QComboBox::drop-down {
                width: 18px;
                border: none;
            }
        """)
        port_row.addWidget(self.port_combo)
        port_layout.addLayout(port_row)

        # 串口状态指示器
        status_row = QHBoxLayout()
        self.port_status = QLabel("●")
        self.port_status.setFixedWidth(16)
        self.port_status_label = QLabel("串口状态")
        self.port_status_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")

        status_row.addWidget(self.port_status)
        status_row.addWidget(self.port_status_label)
        status_row.addStretch()
        port_layout.addLayout(status_row)

        # 刷新按钮
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setToolTip("刷新串口列表")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #d4d4d4;
                border: 1px solid #444;
                font-size: 12px;
                max-height: 24px;
                max-width: 24px;
            }
            QPushButton:hover {
                background-color: #3e3e3e;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_ports)
        port_layout.addWidget(self.refresh_btn, 0, Qt.AlignRight)

        # 上传配置组
        upload_group = QGroupBox("上传配置")
        upload_group.setStyleSheet(port_group.styleSheet())
        upload_layout = QVBoxLayout(upload_group)
        upload_layout.setContentsMargins(5, 10, 5, 5)
        upload_layout.setSpacing(5)

        # 上传按钮
        self.upload_action = QPushButton("上传到设备")
        self.upload_action.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 5px;
                border-radius: 3px;
                max-height: 28px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #666666;
            }
        """)
        self.upload_action.clicked.connect(self.show_upload_settings)
        upload_layout.addWidget(self.upload_action)

        # 添加到主布局
        layout.addWidget(port_group)
        layout.addWidget(upload_group)
        layout.addStretch()

        # 调整布局以确保状态显示不被遮挡
        port_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        upload_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.upload_settings_widget.setLayout(layout)

    def create_upload_settings_area(self):
        self.upload_settings_widget = QWidget()
        self.upload_settings_widget.setStyleSheet("""
            QWidget {
                background-color: #252526;
                border-top: 1px solid #1a1a1a;
                padding: 8px;
            }
            QPushButton {
                min-height: 32px;  /* 保证按钮可点击区域 */
                padding: 6px;
            }
        """)

        layout = QVBoxLayout(self.upload_settings_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # 串口配置组
        port_group = QGroupBox("串口配置")
        port_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        port_layout = QVBoxLayout(port_group)
        port_layout.setContentsMargins(10, 15, 10, 10)
        
        # 串口选择器
        self.port_combo = QComboBox()
        self.port_combo.setMinimumHeight(32)  # 保证下拉菜单可操作
        port_layout.addWidget(self.port_combo)

        # 状态指示器
        status_layout = QHBoxLayout()
        self.port_status = QLabel("●")
        self.port_status.setFixedSize(24, 24)  # 固定尺寸保证可见性
        self.port_status_label = QLabel("串口状态")
        status_layout.addWidget(self.port_status)
        status_layout.addWidget(self.port_status_label)
        port_layout.addLayout(status_layout)

        # 刷新按钮
        self.refresh_btn = QPushButton("刷新端口 (↻)")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)  # 显示可点击状态
        self.refresh_btn.clicked.connect(self.refresh_ports)  # 确保信号连接
        port_layout.addWidget(self.refresh_btn)

        # 上传配置组
        upload_group = QGroupBox("上传配置")
        upload_layout = QVBoxLayout(upload_group)
        self.upload_action = QPushButton("上传到设备")
        self.upload_action.setCursor(Qt.PointingHandCursor)
        self.upload_action.clicked.connect(self.show_upload_settings)  # 确保信号连接
        upload_layout.addWidget(self.upload_action)

        # 弹性布局管理
        layout.addWidget(port_group)
        layout.addWidget(upload_group)
        layout.addStretch()

    def create_file_explorer(self):
        self.file_model = QStandardItemModel()
        self.file_view = QTreeView()
        self.file_view.setModel(self.file_model)
        self.file_view.setStyleSheet("background-color: #252526; color: #d4d4d4;")
        self.file_view.clicked.connect(self.open_file_from_explorer)

        # 初始加载当前目录
        self.load_directory(QDir.currentPath())

    def open_file_from_explorer(self, index):
        item = self.file_model.itemFromIndex(index)
        if item and not item.hasChildren():  # 只处理文件，不处理文件夹
            file_path = item.data(Qt.UserRole)
            if os.path.isfile(file_path):
                self.load_file(file_path)
                self.hide_welcome_page()

    def load_directory(self, path):
        self.file_model.clear()
        self.file_model.setHorizontalHeaderLabels([os.path.basename(path)])
        
        try:
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    dir_item = QStandardItem(item)
                    dir_item.setData(item_path, Qt.UserRole)
                    self.file_model.appendRow(dir_item)
                elif item.endswith('.py'):
                    file_item = QStandardItem(item)
                    file_item.setData(item_path, Qt.UserRole)
                    self.file_model.appendRow(file_item)
        except UnicodeDecodeError:
            QMessageBox.warning(self, "警告", "目录包含无法解码的文件名")

    def create_upload_settings_area(self):
        self.upload_settings_widget = QWidget()
        self.upload_settings_widget.setStyleSheet("""
            QWidget {
                background-color: #252526;
                border-top: 1px solid #1a1a1a;
                padding: 10px;
            }
            QLabel {
                color: #d4d4d4;
                font-size: 12px;
            }
            QComboBox, QPushButton {
                min-height: 28px;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(self.upload_settings_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # 串口配置组
        port_group = QGroupBox("串口配置")
        port_group.setStyleSheet("""
            QGroupBox {
                color: #569CD6;
                border: 1px solid #444;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
            }
        """)
        port_layout = QVBoxLayout(port_group)
        port_layout.setContentsMargins(10, 15, 10, 10)
        port_layout.setSpacing(8)

        # 串口选择行
        port_row = QHBoxLayout()
        self.port_combo = QComboBox()
        self.port_combo.setStyleSheet("""
            QComboBox {
                background-color: #333333;
                color: #d4d4d4;
                border: 1px solid #444;
                padding: 0 8px;
            }
            QComboBox:hover {
                border-color: #555;
            }
            QComboBox::drop-down {
                width: 20px;
                border: none;
            }
        """)
        port_row.addWidget(self.port_combo)
        port_layout.addLayout(port_row)

        # 串口状态指示器
        status_row = QHBoxLayout()
        self.port_status = QLabel("●")
        self.port_status.setFixedWidth(250)
        self.port_status_label = QLabel("串口状态")
        self.port_status_label.setStyleSheet("color: #a0a0a0;")

        status_row.addWidget(self.port_status)
        status_row.addWidget(self.port_status_label)
        status_row.addStretch()
        port_layout.addLayout(status_row)

        # 刷新按钮移到下方
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setToolTip("刷新串口列表")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #d4d4d4;
                border: 1px solid #444;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3e3e3e;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_ports)
        port_layout.addWidget(self.refresh_btn)

        # 上传配置组
        upload_group = QGroupBox("上传配置")
        upload_group.setStyleSheet(port_group.styleSheet())
        upload_layout = QVBoxLayout(upload_group)
        upload_layout.setContentsMargins(10, 15, 10, 10)
        upload_layout.setSpacing(8)

        # 上传按钮
        self.upload_action = QPushButton("上传到设备")
        self.upload_action.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #666666;
            }
        """)
        self.upload_action.clicked.connect(self.show_upload_settings)
        upload_layout.addWidget(self.upload_action)

        # 添加到主布局
        layout.addWidget(port_group)
        layout.addWidget(upload_group)
        layout.addStretch()

        # 调整布局以确保状态显示不被遮挡
        port_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        upload_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        self.upload_settings_widget.setLayout(layout)

    def create_toolbar(self):
        # 文件工具栏
        self.toolbar = QToolBar("主工具栏")
        self.toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        # 文件操作
        self.new_action = QAction("新建", self)
        self.new_action.setShortcut("Ctrl+N")
        self.new_action.triggered.connect(self.new_file)

        self.open_action = QAction("打开", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(self.open_file)

        self.save_action = QAction("保存", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_file)

        self.save_as_action = QAction("另存为", self)
        self.save_as_action.setShortcut("Ctrl+Shift+S")
        self.save_as_action.triggered.connect(self.save_file_as)

        # 编辑操作
        self.undo_action = QAction("撤销", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.triggered.connect(self.editor.undo)

        self.redo_action = QAction("重做", self)
        self.redo_action.setShortcut("Ctrl+Y")
        self.redo_action.triggered.connect(self.editor.redo)

        self.cut_action = QAction("剪切", self)
        self.cut_action.setShortcut("Ctrl+X")
        self.cut_action.triggered.connect(self.editor.cut)

        self.copy_action = QAction("复制", self)
        self.copy_action.setShortcut("Ctrl+C")
        self.copy_action.triggered.connect(self.editor.copy)

        self.paste_action = QAction("粘贴", self)
        self.paste_action.setShortcut("Ctrl+V")
        self.paste_action.triggered.connect(self.editor.paste)

        # 运行功能
        self.run_action = QAction("运行", self)
        self.run_action.setShortcut("Ctrl+R")
        self.run_action.triggered.connect(self.run_file)
        self.toolbar.addAction(self.run_action)

        # 添加到工具栏
        self.toolbar.addAction(self.new_action)
        self.toolbar.addAction(self.open_action)
        self.toolbar.addAction(self.save_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.undo_action)
        self.toolbar.addAction(self.redo_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.cut_action)
        self.toolbar.addAction(self.copy_action)
        self.toolbar.addAction(self.paste_action)

    def create_bottom_panel(self):
        # 底部面板容器
        self.bottom_panel = QWidget()
        self.bottom_panel.setStyleSheet("background-color: #252526;")

        # 底部面板布局
        bottom_layout = QVBoxLayout(self.bottom_panel)
        bottom_layout.setContentsMargins(10, 10, 10, 10)
        bottom_layout.setSpacing(15)

        # 控制台
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #1E1E1E; color: #D4D4D4;")
        bottom_layout.addWidget(self.console)

        # 添加到底部分割器
        self.vertical_splitter.addWidget(self.bottom_panel)
        self.vertical_splitter.setSizes([500, 200])

    def run_file(self):
        if self.current_file is None:
            QMessageBox.critical(self, "错误", "请先打开或保存文件")
            return

        try:
            # 处理中文路径的解决方案
            if ' ' in self.current_file or any(ord(c) > 127 for c in self.current_file):
                # 对路径进行双引号转义
                cmd = f'python "{self.current_file}"'
            else:
                cmd = f'python {self.current_file}'

            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                encoding='gbk',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0:
                output = result.stdout
                self.console.append(output)
                self.status_bar.showMessage(f"运行成功: {self.current_file}")
            else:
                error_msg = result.stderr if result.stderr else "未知错误"
                self.console.append(error_msg)
                self.status_bar.showMessage(f"运行失败: {error_msg}")
        except Exception as e:
            self.console.append(str(e))
            self.status_bar.showMessage(f"运行过程中发生错误: {str(e)}")

    def new_file(self):
        self.hide_welcome_page()
        self.editor.clear()
        self.current_file = None
        self.status_bar.showMessage("新建文件")

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "", "Python文件 (*.py);;所有文件 (*)"
        )

        if file_path:
            self.load_file(file_path)
            # 更新文件管理路径为打开文件的路径
            self.load_directory(os.path.dirname(file_path))
            self.hide_welcome_page()

    def load_file(self, file_path):
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")
                
            # 尝试用UTF-8打开
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                # 如果UTF-8失败，尝试GBK
                try:
                    with open(file_path, 'r', encoding='gbk') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    # 如果GBK也失败，使用错误忽略模式
                    with open(file_path, 'r', encoding='gbk', errors='ignore') as f:
                        content = f.read()
                    self.status_bar.showMessage(f"已打开: {file_path} (部分字符已忽略)")
                
            self.editor.setPlainText(content)
            self.current_file = file_path
            self.status_bar.showMessage(f"已打开: {file_path}")
            
        except FileNotFoundError as e:
            QMessageBox.critical(self, "错误", str(e))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开文件:\n{str(e)}")

    def save_file(self):
        if self.current_file is None:
            return self.save_file_as()

        try:
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())
            
            # If we have a project, add this file to it if not already there
            if self.current_project and self.current_file not in self.current_project.files:
                self.current_project.add_file(self.current_file)  # 这里会自动处理路径转换
                self.current_project.save_project_file()
            
            self.status_bar.showMessage(f"已保存: {self.current_file}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"保存失败: {str(e)}")

    def save_file_as(self):
        # Start in project directory if we have one
        start_dir = self.current_project.path if self.current_project else os.path.expanduser("~")
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save As", 
            start_dir,
            "Python Files (*.py);;All Files (*)"
        )
        
        if file_path:
            self.current_file = file_path
            self.save_file()
            
            # Add to project if we have one
            if self.current_project:
                self.current_project.add_file(file_path)
                self.current_project.save_project_file()
                
                # Refresh file explorer
                self.load_directory(self.current_project.path)
            
            return True
        return False

    def refresh_ports(self):
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("扫描中...")
        self.port_status.setStyleSheet("color: gray; font-weight: bold;")

        try:
            all_ports = []
            for port in serial.tools.list_ports.comports():
                if (not self.is_bluetooth_port(port) and
                        not self.is_virtual_port(port)):
                    all_ports.append(port)

            def port_sort_key(port):
                desc = (port.description or "").lower()
                if 'ch340' in desc: return 0
                if 'cp210' in desc: return 1
                if 'ftdi' in desc: return 2
                if 'pl2303' in desc: return 3
                return 4

            all_ports.sort(key=port_sort_key)

            self.port_combo.clear()
            if not all_ports:
                self.port_status.setStyleSheet("color: red; font-weight: bold;")
                self.port_status.setText("● 无可用串口")
                self.refresh_btn.setText("刷新串口")
                self.refresh_btn.setEnabled(True)
                return

            for port in all_ports:
                desc = port.description or "串口设备"
                self.port_combo.addItem(f"{desc} ({port.device})", port.device)

            self.port_combo.setCurrentIndex(0)
            self.check_port_status()

        except Exception as e:
            self.port_status.setStyleSheet("color: red; font-weight: bold;")
            self.port_status.setText(f"● 错误: {str(e)}")
            QMessageBox.critical(self, "串口错误", f"检测串口失败:\n{str(e)}")
        finally:
            self.refresh_btn.setText("刷新串口")
            self.refresh_btn.setEnabled(True)

    def is_bluetooth_port(self, port):
        bluetooth_indicators = [
            'bluetooth', 'bth', 'rfcomm',
            'standard serial over bluetooth',
            '蓝牙', 'wireless', 'virtual'
        ]

        desc = (port.description or "").lower()
        hwid = (port.hwid or "").lower()

        bluetooth_chips = [
            'csr', 'bcm', 'bluez', 'bluefruit',
            'rn42', 'hc-05', 'hc-06'
        ]

        return (any(indicator in desc for indicator in bluetooth_indicators) or
                any(indicator in hwid for indicator in bluetooth_indicators) or
                any(chip in desc for chip in bluetooth_chips) or
                any(chip in hwid for chip in bluetooth_chips))

    def is_virtual_port(self, port):
        virtual_indicators = [
            'virtual', 'com0com', 'tcp', 'udp',
            'pipe', 'vsp', 'emulator', 'composite'
        ]
        desc = (port.description or "").lower()
        hwid = (port.hwid or "").lower()
        return (any(indicator in desc for indicator in virtual_indicators) or
                any(indicator in hwid for indicator in virtual_indicators))

    def check_port_status(self):
        if self.port_combo.currentIndex() == -1:
            return False

        selected_port = self.port_combo.currentData()

        self.port_status.setStyleSheet("color: yellow; font-weight: bold;")
        self.port_status.setText("● 检测中...")

        try:
            with serial.Serial(selected_port, timeout=1) as ser:
                if ser.is_open:
                    self.port_status.setStyleSheet("color: green; font-weight: bold;")
                    self.port_status.setText("● 可用")
                    return True
                else:
                    self.port_status.setStyleSheet("color: red; font-weight: bold;")
                    self.port_status.setText("● 不可用")
                    return False
        except SerialException as e:
            self.port_status.setStyleSheet("color: red; font-weight: bold;")
            self.port_status.setText(f"● 错误: {str(e)}")
            return False
        except Exception as e:
            self.port_status.setStyleSheet("color: red; font-weight: bold;")
            self.port_status.setText(f"● 错误: {str(e)}")
            return False

    def show_upload_settings(self):
        if self.current_file is None:
            QMessageBox.critical(self, "错误", "请先打开或保存文件")
            return

        dialog = UploadSettingsDialog(self.port_combo, self)
        if dialog.exec_() == QDialog.Accepted:
            port, flash_path = dialog.get_settings()
            if not flash_path:
                QMessageBox.critical(self, "错误", "请输入烧录路径")
                return

            if not self.check_port_status():
                if QMessageBox.question(self, "警告", "当前串口状态不正常，确定要继续上传吗？",
                                        QMessageBox.Yes | QMessageBox.No) == QMessageBox.No:
                    return

            # 创建控制台窗口
            self.upload_console = UploadConsoleDialog(self)
            self.upload_console.show()
            self.upload_console.append_log(f"开始上传: {self.current_file}")
            self.upload_console.append_log(f"目标设备: {port}")
            self.upload_console.append_log(f"目标路径: {flash_path}")
            
            # 使用线程执行上传，避免阻塞UI
            upload_thread = threading.Thread(
                target=self.execute_upload,
                args=(port, flash_path),
                daemon=True
            )
            upload_thread.start()

    def execute_upload(self, port, flash_path):
        cmd = f"firefly_upload.exe -p {port} -i \"{self.current_file}\" -o \"{flash_path}\""
        
        try:
            self.upload_action.setEnabled(False)
            self.upload_action.setText("上传中...")
            
            # 使用subprocess.Popen以便实时获取输出
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding='gbk',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # 实时读取输出
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # 更新控制台和进度条
                    self.upload_console.append_log(output.strip())
                    
                    # 检查进度信息
                    progress_match = re.search(r'(\d+)%', output)
                    if progress_match:
                        progress = int(progress_match.group(1))
                        self.upload_console.update_progress(progress)
            
            # 检查返回码
            return_code = process.poll()
            if return_code == 2:
                self.upload_console.append_log("上传成功!")
                self.status_bar.showMessage(f"代码已成功上传到设备 - 端口: {port}, 路径: {flash_path}")
            else:
                error_msg = process.stderr.read()
                self.upload_console.append_log(f"上传失败: {error_msg}")
                self.status_bar.showMessage(f"上传失败: {error_msg}")
                
        except Exception as e:
            self.upload_console.append_log(f"上传过程中发生错误: {str(e)}")
            self.status_bar.showMessage(f"上传过程中发生错误: {str(e)}")
        finally:
            self.upload_action.setText("上传到设备")
            self.upload_action.setEnabled(True)

    def load_settings(self):
        settings = QSettings("NorthSoft", "BMFV4O_Editor")
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        state = settings.value("windowState")
        if state:
            self.restoreState(state)

        splitter_sizes = settings.value("splitterSizes")
        if splitter_sizes:
            self.horizontal_splitter.setSizes([int(size) for size in splitter_sizes[:2]])
            self.vertical_splitter.setSizes([int(size) for size in splitter_sizes[2:]])

    def save_settings(self):
        settings = QSettings("NorthSoft", "BMFV4O_Editor")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        splitter_sizes = self.horizontal_splitter.sizes() + self.vertical_splitter.sizes()
        settings.setValue("splitterSizes", splitter_sizes)

    def closeEvent(self, event):
        self.save_settings()
        event.accept()

    def show_welcome_page(self):
        self.welcome_page.show()
        self.editor.hide()

    def hide_welcome_page(self):
        self.welcome_page.hide()
        self.editor.show()

    def create_editor_area(self):
        self.editor = CodeEditor()
        self.vertical_splitter.addWidget(self.editor)

    def create_welcome_page(self):
        self.welcome_page = QWidget()
        layout = QVBoxLayout(self.welcome_page)
        
        welcome_label = QLabel("欢迎使用 NScode Pro V5")
        welcome_label.setStyleSheet("font-size: 24px; color: #569CD6;")
        welcome_label.setAlignment(Qt.AlignCenter)
        
        recent_label = QLabel("- App Version 5.0.0")
        recent_label.setStyleSheet("font-size: 18px; color: #D4D4D4;")

        recent_label2 = QLabel("- By 小北ovo (LCH) - 2025 DCIC Champion")
        recent_label2.setStyleSheet("font-size: 18px; color: #D4D4D4;")

        recent_label3 = QLabel("- 祝每一位选手好运")
        recent_label3.setStyleSheet("font-size: 18px; color: #D4D4D4;")
        
        layout.addWidget(welcome_label)
        layout.addWidget(recent_label)
        layout.addWidget(recent_label2)
        layout.addWidget(recent_label3)
        layout.addStretch()


        btn_layout = QHBoxLayout()
        new_project_btn = QPushButton("新建项目")
        new_project_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                padding: 10px;
                border-radius: 4px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        new_project_btn.clicked.connect(self.new_project)
        
        open_project_btn = QPushButton("打开项目")
        open_project_btn.setStyleSheet(new_project_btn.styleSheet())
        open_project_btn.clicked.connect(self.open_project)
        
        btn_layout.addStretch()
        btn_layout.addWidget(new_project_btn)
        btn_layout.addWidget(open_project_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        self.vertical_splitter.addWidget(self.welcome_page)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 设置应用程序样式
    app.setStyle("Fusion")

    # 设置调色板 - 暗色主题
    palette = app.palette()
    palette.setColor(palette.Window, QColor(53, 53, 53))
    palette.setColor(palette.WindowText, QColor(255, 255, 255))
    palette.setColor(palette.Base, QColor(42, 42, 42))
    palette.setColor(palette.AlternateBase, QColor(66, 66, 66))
    palette.setColor(palette.ToolTipBase, QColor(53, 53, 53))
    palette.setColor(palette.ToolTipText, QColor(255, 255, 255))
    palette.setColor(palette.Text, QColor(255, 255, 255))
    palette.setColor(palette.Button, QColor(53, 53, 53))
    palette.setColor(palette.ButtonText, QColor(255, 255, 255))
    palette.setColor(palette.BrightText, QColor(255, 0, 0))
    palette.setColor(palette.Highlight, QColor(74, 144, 226))
    palette.setColor(palette.HighlightedText, QColor(0, 0, 0))
    app.setPalette(palette)

    try:
        editor = VSCodeLikeEditor()
        editor.show()
        sys.exit(app.exec_())
    except Exception as e:
        QMessageBox.critical(None, "启动错误", f"程序初始化失败：\n{str(e)}")