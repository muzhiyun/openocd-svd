#!/user/bin/env python3

"""
Custom widgets special for openocd-svd
"""

from PyQt5 import QtCore
from PyQt5.QtGui import QCursor, QRegExpValidator, QIntValidator, QColor
from PyQt5.QtWidgets import (QWidget, QComboBox, QCheckBox, QVBoxLayout,
                             QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
                             QLineEdit, QAction, QPushButton, QSizePolicy)


class NumEdit(QLineEdit):
    def __init__(self, num_bwidth=32):
        QLineEdit.__init__(self)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.handle_context_menu_requested)
        self.__num_bwidth = num_bwidth
        self.__display_base = 16
        self.setText("0")
        self.setDisplayFormat(16)
        self.is_focused = False

    # -- Events --
    def focusInEvent(self, event):
        self.is_focused = True
        QLineEdit.focusInEvent(self, event)

    def focusOutEvent(self, event):
        self.is_focused = False
        QLineEdit.focusOutEvent(self, event)

    def wheelEvent(self, event):
        if self.is_focused:
            delta = 1 if event.angleDelta().y() > 0 else -1
            if 2**self.numBitWidth() > (self.num() + delta) >= 0:
                self.setNum(self.num() + delta)
            event.accept()
            self.editingFinished.emit()

    # -- Slots --
    def handle_context_menu_requested(self, pos):
        self.menu = self.createStandardContextMenu()

        self.menu.act_to_dec = QAction("Convert to Dec")
        self.menu.act_to_dec.triggered.connect(lambda: self.handle_act_convert_triggered(10))
        self.menu.act_to_hex = QAction("Convert to Hex")
        self.menu.act_to_hex.triggered.connect(lambda: self.handle_act_convert_triggered(16))
        self.menu.act_to_bin = QAction("Convert to Bin")
        self.menu.act_to_bin.triggered.connect(lambda: self.handle_act_convert_triggered(2))
        self.menu.insertActions(self.menu.actions()[0],
                                [self.menu.act_to_dec, self.menu.act_to_hex, self.menu.act_to_bin])
        self.menu.insertSeparator(self.menu.actions()[3])

        self.menu.exec_(QCursor.pos())

    def handle_act_convert_triggered(self, base):
        self.setDisplayFormat(base)

    # -- API --
    def numBitWidth(self):
        return self.__num_bwidth

    def setNumBitWidth(self, width):
        self.__num_bwidth = width

    def num(self):
        return int(self.text().replace(" ", ""), self.displayBase())

    def setNum(self, num, base=None):
        if base:
            self.setDisplayFormat(base, num)
        else:
            self.setDisplayFormat(self.displayBase(), num)

    def displayBase(self):
        return self.__display_base

    def setDisplayValidator(self, base):
        if base == 10:
            max_int = 2**self.numBitWidth()
            self.setValidator(QIntValidator(0, max_int - 1))
        elif base == 16:
            high_part = ""
            low_part = ""
            if self.numBitWidth() % 4 > 0:
                high_part = "[0-%d]" % (2**(self.numBitWidth() % 4) - 1)
            if int(self.numBitWidth() / 4) > 0:
                low_part = "[0-9A-Fa-f]{%d}" % int(self.numBitWidth() / 4)
            allowed_symbols = "0x" + high_part + low_part
            self.setValidator(QRegExpValidator(QtCore.QRegExp(allowed_symbols)))
        elif base == 2:
            high_part = ""
            low_part = ""
            if self.numBitWidth() % 4 > 0:
                high_part = "(0|1){%d}" % (self.numBitWidth() % 4)
            if int(self.numBitWidth() / 4) > 0:
                low_part = "((\s|)(0|1){4}){%d}" % int(self.numBitWidth() / 4)
            allowed_symbols = "^" + high_part + low_part + "$"
            self.setValidator(QRegExpValidator(QtCore.QRegExp(allowed_symbols)))

    def setDisplayFormat(self, base, num=None):
        if num is not None:
            self.setText(self.__format_num(num, base))
        else:
            self.setText(self.__format_num(self.num(), base))
        self.setDisplayValidator(base)
        self.__display_base = base

    def __format_num(self, num, base):
        if base == 10:
            return str(num)
        elif base == 16:
            return format(num, '#0%dx' % (2 + int(self.numBitWidth() / 4) + (self.numBitWidth() % 4 > 0)))
        elif base == 2:
            chunk_n = 4
            bin_str = format(num, '0%db' % self.numBitWidth())
            return ' '.join(([bin_str[::-1][i:i + chunk_n] for i in range(0, len(bin_str), chunk_n)]))[::-1]
        else:
            raise ValueError("Can't __format_num() - unknown base")


class RegEdit(QWidget):
    def __init__(self, svd_reg):
        QWidget.__init__(self)
        self.svd = svd_reg
        self.horiz_layout = QHBoxLayout(self)
        self.horiz_layout.setContentsMargins(0, 0, 0, 0)
        self.horiz_layout.setSpacing(0)
        if self.svd["access"] == "read-only":
            self.is_enabled = False
        else:
            self.is_enabled = True
        self.nedit_val = NumEdit(32)
        self.nedit_val.editingFinished.connect(self.handle_reg_value_changed)
        self.nedit_val.setMinimumSize(QtCore.QSize(320, 20))
        self.nedit_val.setMaximumSize(QtCore.QSize(16777215, 20))
        self.nedit_val.setEnabled(self.is_enabled)
        self.nedit_val.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))
        self.horiz_layout.addWidget(self.nedit_val)
        self.btn_read = QPushButton(self)
        self.btn_read.setText("R")
        self.btn_read.setMaximumSize(QtCore.QSize(25, 20))
        self.horiz_layout.addWidget(self.btn_read)
        if self.is_enabled:
            self.btn_write = QPushButton(self)
            self.btn_write.setText("W")
            self.btn_write.setMaximumSize(QtCore.QSize(25, 20))
            self.horiz_layout.addWidget(self.btn_write)
        self.fields = {}
        for field in self.svd["fields"]:
            self.fields[field["name"]] = FieldEdit(field)
            self.fields[field["name"]].valueChanged.connect(self.handle_field_value_changed)
        self.__opt_autowrite = False

    # -- Slots --
    def handle_reg_value_changed(self):
        # if value changed we should set new fields values
        for key in self.fields.keys():
            val = self.val()
            val = (val >> self.fields[key].svd["lsb"]) & ((2 ** self.fields[key].num_bwidth) - 1)
            self.fields[key].setVal(val)
        if self.autoWrite():
            self.btn_write.clicked.emit()

    def handle_field_value_changed(self):
        # if field value changed we should set update reg value
        val = self.val() & ~(((2 ** self.sender().num_bwidth) - 1) << self.sender().svd["lsb"])
        val = val | (self.sender().val() << self.sender().svd["lsb"])
        self.__update_val(val)
        if self.autoWrite():
            self.btn_write.clicked.emit()

    # -- API --
    def val(self):
        return self.nedit_val.num()

    def __update_val(self, val):
        self.nedit_val.setNum(val)

    def setVal(self, val):
        self.__update_val(val)
        self.handle_reg_value_changed()

    def autoWrite(self):
        return self.__opt_autowrite

    def setAutoWrite(self, state):
        self.__opt_autowrite = state


class FieldEdit(QWidget):
    valueChanged = QtCore.pyqtSignal()

    def __init__(self, svd_field):
        QWidget.__init__(self)
        self.svd = svd_field
        self.horiz_layout = QHBoxLayout(self)
        self.horiz_layout.setContentsMargins(0, 0, 0, 0)
        self.horiz_layout.setSpacing(6)
        if self.svd["access"] == "read-only":
            self.is_enabled = False
        else:
            self.is_enabled = True

        self.num_bwidth = self.svd["msb"] - self.svd["lsb"] + 1

        if self.num_bwidth == 1:
            self.chbox_val = QCheckBox(self)
            self.chbox_val.setEnabled(self.is_enabled)
            self.chbox_val.setMaximumSize(QtCore.QSize(16777215, 20))
            self.chbox_val.stateChanged.connect(self.handle_field_value_changed)
            self.horiz_layout.addWidget(self.chbox_val)
        else:
            self.nedit_val = NumEdit(self.num_bwidth)
            self.nedit_val.setEnabled(self.is_enabled)
            self.nedit_val.editingFinished.connect(self.handle_field_value_changed)
            self.nedit_val.setMaximumSize(QtCore.QSize(16777215, 20))
            self.horiz_layout.addWidget(self.nedit_val)

        if self.svd["enums"]:
            self.is_enums = True
            self.combo_enum = QComboBox(self)
            self.combo_enum.setEnabled(self.is_enabled)
            self.combo_enum.currentIndexChanged.connect(self.handle_enum_value_changed)
            self.combo_enum.values = []
            for enum in self.svd["enums"]:
                self.combo_enum.values += [int(enum["value"])]
                self.combo_enum.addItem("(0x%x) %s : %s" % (int(enum["value"]), enum["name"], enum["description"]))
            self.combo_enum.setMaximumSize(QtCore.QSize(16777215, 20))
            self.horiz_layout.addWidget(self.combo_enum)
            if self.num_bwidth == 1:
                self.chbox_val.setMaximumSize(QtCore.QSize(320, 20))
            else:
                self.nedit_val.setMaximumSize(QtCore.QSize(320, 20))
        else:
            self.is_enums = False

    # -- Slots --
    def handle_field_value_changed(self, value=None):
        if self.is_enums:
            try:
                if self.val() != self.combo_enum.values[self.combo_enum.currentIndex()]:
                    self.combo_enum.setCurrentIndex(self.combo_enum.values.index(self.val()))
            except ValueError:
                self.combo_enum.setCurrentIndex(-1)
        self.valueChanged.emit()

    def handle_enum_value_changed(self, currentIndex):
        if self.is_enums and currentIndex != -1:
            if self.val() != self.combo_enum.values[currentIndex]:
                self.setVal(self.combo_enum.values[currentIndex])

    # -- API --
    def val(self):
        if self.num_bwidth == 1:
            if self.chbox_val.checkState():
                return 1
            else:
                return 0
        else:
            return self.nedit_val.num()

    def setVal(self, val):
        if self.num_bwidth == 1:
            if val:
                self.chbox_val.setCheckState(QtCore.Qt.Checked)
            else:
                self.chbox_val.setCheckState(QtCore.Qt.Unchecked)
        else:
            self.nedit_val.setNum(val)
        self.handle_field_value_changed()


class PeriphTab(QWidget):
    def __init__(self, svd_periph):
        QWidget.__init__(self)
        self.svd = svd_periph
        self.setObjectName(self.svd["name"])
        # vertical layout inside
        self.vert_layout = QVBoxLayout(self)
        self.vert_layout.setContentsMargins(6, 6, 6, 6)
        self.vert_layout.setSpacing(6)
        # label with peripheral description and read all button
        self.header = QWidget(self)
        self.horiz_layout = QHBoxLayout(self.header)
        self.lab_periph_descr = QLabel(self.header)
        self.lab_periph_descr.setText(self.svd["description"])
        self.lab_periph_descr.setTextInteractionFlags(QtCore.Qt.LinksAccessibleByMouse |
                                                      QtCore.Qt.TextSelectableByMouse)
        self.horiz_layout.addWidget(self.lab_periph_descr)
        self.btn_readall = QPushButton(self.header)
        self.btn_readall.setText("Read all")
        self.btn_readall.setMaximumSize(QtCore.QSize(100, 20))
        self.btn_readall.clicked.connect(self.handle_btn_readall_clicked)
        self.horiz_layout.addWidget(self.btn_readall)
        self.vert_layout.addWidget(self.header)
        # tree widget for displaying regs
        reg_col = 0
        val_col = 1
        self.tree_regs = QTreeWidget(self)
        self.tree_regs.itemSelectionChanged.connect(self.handle_tree_selection_changed)
        self.tree_regs.headerItem().setText(reg_col, "Register")
        self.tree_regs.setColumnWidth(reg_col, 200)
        self.tree_regs.headerItem().setText(val_col, "Value")
        for reg in self.svd["regs"]:
            item0 = QTreeWidgetItem(self.tree_regs)
            item0.svd = reg
            item0.setText(reg_col, reg["name"])
            background = QColor(240, 240, 240)
            item0.setBackground(0, background)
            item0.setBackground(1, background)
            reg_edit = RegEdit(reg)
            self.tree_regs.setItemWidget(item0, val_col, reg_edit)
            self.tree_regs.addTopLevelItem(item0)
            for field in reg["fields"]:
                item1 = QTreeWidgetItem(item0)
                item1.svd = field
                item1.setText(reg_col, field["name"])
                self.tree_regs.setItemWidget(item1, val_col, reg_edit.fields[field["name"]])
                item0.addChild(item1)
        self.vert_layout.addWidget(self.tree_regs)
        # label with register/field description
        self.lab_info = QLabel(self)
        self.lab_info.setMaximumSize(QtCore.QSize(16777215, 40))
        self.lab_info.setMinimumSize(QtCore.QSize(16777215, 40))
        self.lab_info.setText("")
        self.lab_info.setTextInteractionFlags(QtCore.Qt.LinksAccessibleByMouse |
                                              QtCore.Qt.TextSelectableByMouse)
        self.vert_layout.addWidget(self.lab_info)

    # -- Slots --
    def handle_tree_selection_changed(self):
        tree_item = self.tree_regs.selectedItems()[0]
        name = tree_item.svd["name"]
        descr = tree_item.svd["description"]
        addr = tree_item.svd["address_offset"]
        if "access" in tree_item.svd.keys() and tree_item.svd["access"]:
            temp = tree_item.svd["access"]
            access = "<%s>" % (temp.split("-")[0][0] + temp.split("-")[1][0]).upper()
        else:
            access = ""
        if "msb" in tree_item.svd.keys():
            bits = "[%d:%d]" % (tree_item.svd["msb"],
                                tree_item.svd["lsb"])
        else:
            bits = ""
        self.lab_info.setText("(0x%08x)%s%s : %s\n%s" % (addr, bits, access, name, descr))

    def handle_btn_readall_clicked(self):
        for reg_n in range(0, self.tree_regs.topLevelItemCount()):
            reg = self.tree_regs.itemWidget(self.tree_regs.topLevelItem(reg_n), 1)
            reg.btn_read.clicked.emit()


# -- Standalone run -----------------------------------------------------------
if __name__ == '__main__':
    print("Nothing to do")
