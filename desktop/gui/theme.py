DARK_STYLESHEET = """
QWidget {
    background-color: #121212;
    color: #E0E0E0;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}
QMainWindow {
    background-color: #0D0D0D;
}
QLabel#VideoLabel {
    background-color: #000000;
    border: 2px solid #2A2A2A;
    border-radius: 8px;
}
QLabel#WarningLabel {
    color: #FF3B30;
    font-size: 20px;
    font-weight: bold;
}
QLabel[role="value"] {
    color: #4CAF50;
    font-weight: bold;
}
QLabel[role="valueWarn"] {
    color: #FF9800;
    font-weight: bold;
}
QLabel[role="valueBad"] {
    color: #FF3B30;
    font-weight: bold;
}
QPushButton {
    background-color: #1E1E1E;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 8px 14px;
    color: #E0E0E0;
}
QPushButton:hover {
    background-color: #2A2A2A;
    border: 1px solid #4CAF50;
}
QPushButton:pressed {
    background-color: #333333;
}
QPushButton:disabled {
    color: #555555;
    border: 1px solid #2A2A2A;
}
QPushButton#DangerButton:hover {
    border: 1px solid #FF3B30;
    background-color: #2A1414;
}
QPushButton#PrimaryButton {
    border: 1px solid #4CAF50;
    color: #4CAF50;
}
QComboBox, QLineEdit, QSpinBox {
    background-color: #1A1A1A;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 5px;
    color: #E0E0E0;
}
QTextEdit#LogView {
    background-color: #0A0A0A;
    border: 1px solid #2A2A2A;
    border-radius: 6px;
    color: #8FE388;
    font-family: 'Consolas', monospace;
    font-size: 12px;
}
QGroupBox {
    border: 1px solid #2A2A2A;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: bold;
    color: #4CAF50;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}
QScrollBar:vertical {
    background: #121212;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #333333;
    border-radius: 5px;
}
QTabWidget::pane {
    border: 1px solid #2A2A2A;
    border-radius: 8px;
    background-color: #161616;
    top: -1px;
}
QTabBar::tab {
    background-color: #1A1A1A;
    color: #AAAAAA;
    border: 1px solid #2A2A2A;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #161616;
    color: #4CAF50;
    font-weight: bold;
}
QTabBar::tab:hover {
    color: #E0E0E0;
}
QSplitter::handle {
    background-color: #2A2A2A;
    width: 3px;
}
QSplitter::handle:hover {
    background-color: #4CAF50;
}
QFrame#ControlBar {
    background-color: #161616;
    border: 1px solid #2A2A2A;
    border-radius: 8px;
}
"""
