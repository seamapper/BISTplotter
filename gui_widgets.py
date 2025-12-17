"""Commonly used widgets for NOAA / MAC echosounder assessment tools"""


from PyQt6 import QtWidgets, QtGui
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtCore import Qt, QSize


class PushButton(QtWidgets.QPushButton):
    # generic push button class
    def __init__(self, text='PushButton', width=50, height=20, name='NoName', tool_tip=''):
        super(PushButton, self).__init__()
        self.setText(text)
        self.setFixedSize(int(width), int(height))
        self.setObjectName(name)
        self.setToolTip(tool_tip)
        
        # Set smaller font size for buttons
        font = self.font()
        font.setPointSize(font.pointSize() - 1)
        self.setFont(font)


class CheckBox(QtWidgets.QCheckBox):
    # generic checkbox class
    def __init__(self, text='CheckBox', set_checked=False, name='NoName', tool_tip='', width=0, height=0):
        super(CheckBox, self).__init__()
        self.setText(text)
        self.setObjectName(name)
        self.setToolTip(tool_tip)
        self.setChecked(set_checked)

        if height > 0:
            self.setFixedHeight(height)

        if width > 0:
            self.setFixedWidth(width)


class LineEdit(QtWidgets.QLineEdit):
    # generic line edit class
    def __init__(self, text='', width=100, height=20, name='NoName', tool_tip=''):
        super(LineEdit, self).__init__()
        self.setText(text)
        self.setFixedSize(int(width), int(height))
        self.setObjectName(name)
        self.setToolTip(tool_tip)
        
        # Set smaller font size for line edits
        font = self.font()
        font.setPointSize(font.pointSize() - 1)
        self.setFont(font)
        
        # Set text colors: white when active, grey when disabled
        self.setStyleSheet("""
            QLineEdit {
                color: white !important;
            }
            QLineEdit:disabled {
                color: grey !important;
            }
            /* Ensure text color is maintained even when parent is disabled */
            QGroupBox:disabled QLineEdit {
                color: grey !important;
            }
            QGroupBox:checked QLineEdit {
                color: white !important;
            }
        """)


class ComboBox(QtWidgets.QComboBox):
    # generic combobox class
    def __init__(self, items=[], width=100, height=20, name='NoName', tool_tip=''):
        super(ComboBox, self).__init__()
        self.addItems(items)
        self.setFixedSize(int(width), int(height))
        self.setObjectName(name)
        self.setToolTip(tool_tip)
        
        # Set smaller font size for comboboxes
        font = self.font()
        font.setPointSize(font.pointSize() - 1)
        self.setFont(font)
        
        # Set text colors: white when active, grey when disabled
        self.setStyleSheet("""
            QComboBox {
                color: white !important;
            }
            QComboBox:disabled {
                color: grey !important;
            }
            QComboBox QAbstractItemView {
                color: white !important;
            }
            /* Ensure text color is maintained even when parent is disabled */
            QGroupBox:disabled QComboBox {
                color: grey !important;
            }
            QGroupBox:checked QComboBox {
                color: white !important;
            }
        """)


class Label(QtWidgets.QLabel):
    # generic label class
    def __init__(self, text, width=100, height=20, name='NoName', alignment=(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)):
        super(Label, self).__init__()
        self.setText(text)
        # self.setFixedSize(int(width), int(height))
        self.resize(int(width), int(height))
        self.setObjectName(name)
        self.setAlignment(alignment)


class BoxLayout(QtWidgets.QVBoxLayout):
    # generic class to add widgets or layouts oriented in layout_dir
    def __init__(self, items=[], layout_dir='v', add_stretch=False, alignment=(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)):
        super(BoxLayout, self).__init__()
        # set direction based on logical of layout_dir = top to bottom ('v') or left to right ('h')
        self.setDirection([QtWidgets.QBoxLayout.Direction.TopToBottom, QtWidgets.QBoxLayout.Direction.LeftToRight][layout_dir == 'h'])

        for i in items:
            if isinstance(i, QtWidgets.QWidget):
                self.addWidget(i)
                self.setAlignment(alignment)
            else:
                self.addLayout(i)
                self.setAlignment(alignment)

        if add_stretch:
            self.addStretch()


class TextEdit(QtWidgets.QTextEdit):
    # generic class for a processing/activity log or text editor
    def __init__(self, stylesheet="background-color: lightgray", readonly=True, name='NoName'):
        super(TextEdit, self).__init__()
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Minimum)
        self.setStyleSheet(stylesheet)
        self.setReadOnly(readonly)
        self.setObjectName(name)


class GroupBox(QtWidgets.QGroupBox):
    # generic class for a groupbox
    def __init__(self, title='', layout=None, set_checkable=False, set_checked=False, name='NoName'):
        super(GroupBox, self).__init__()
        self.setTitle(title)
        self.setLayout(layout)
        self.setCheckable(set_checkable)
        self.setChecked(set_checked)
        self.setObjectName(name)
        
        # No specific styling needed for GroupBox - let child widgets handle their own styling
        # self.setToolTip(tool_tip)


class FileList(QtWidgets.QListWidget):
    # generic class for a file list
    def __init__(self):
        super(FileList, self).__init__()
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.MinimumExpanding, QtWidgets.QSizePolicy.Policy.Minimum)
        self.setIconSize(QSize(0, 0))  # set icon size to 0,0 or file names (from item.data) will be indented


class RadioButton(QtWidgets.QRadioButton):
    # generic class for a radio button
    def __init__(self, text='RadioButton', set_checked=False, name='NoName', tool_tip=''):
        super(RadioButton, self).__init__()
        self.setText(text)
        self.setObjectName(name)
        self.setToolTip(tool_tip)
        self.setChecked(set_checked)


class CheckBoxComboBox(QtWidgets.QHBoxLayout):
    # generic class for a checkbox with text and combobox in a horizontal layout
    def __init__(self, label='CheckBoxComboBox', set_checked=False, name='NoName', tool_tip='', items=[], width=100, height=20):
        super(CheckBoxComboBox, self).__init__()
        cbox = ComboBox(items, width, height, name)
        chk = CheckBox(label, set_checked, name, tool_tip)
        self.addWidget(chk)
        self.addWidget(cbox)


class CheckBoxTextBox(QtWidgets.QHBoxLayout):
    # generic class for a checkbox with text and text box in a horizontal layout
    def __init__(self, label='CheckBoxTextBox', set_checked=False, name='NoName', tool_tip='', text='', width=100, height=20):
        super(CheckBoxTextBox, self).__init__()
        self.textbox = LineEdit(text, width, height, name)
        self.chk = CheckBox(label, set_checked, name, tool_tip)
        self.addWidget(self.chk)
        self.addWidget(self.textbox)