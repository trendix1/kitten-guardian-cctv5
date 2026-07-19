from __future__ import annotations

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel


class StatusRow(QWidget):
    """Baris kecil: 'Label : Value' dipakai di panel monitoring."""

    def __init__(self, label: str, initial_value: str = "-", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self.label = QLabel(label)
        self.label.setMinimumWidth(110)
        self.value = QLabel(initial_value)
        self.value.setProperty("role", "value")

        layout.addWidget(self.label)
        layout.addWidget(self.value)
        layout.addStretch()

    def set_value(self, text: str, role: str = "value"):
        self.value.setText(text)
        self.value.setProperty("role", role)
        self.value.style().unpolish(self.value)
        self.value.style().polish(self.value)
