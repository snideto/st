#!/usr/bin/env python3

# TODO: get some docstrings in here!

# TODO: CAMPid 98852142341263132467998754961432
import epyqlib.tee
import os
import sys

# TODO: CAMPid 953295425421677545429542967596754
log = open(os.path.join(os.getcwd(), 'epyq.log'), 'w', encoding='utf-8', buffering=1)

if sys.stdout is None:
    sys.stdout = log
else:
    sys.stdout = epyqlib.tee.Tee([sys.stdout, log])

if sys.stderr is None:
    sys.stderr = log
else:
    sys.stderr = epyqlib.tee.Tee([sys.stderr, log])

import logging
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')

import copy
import epyq
import epyqlib.canneo
import epyqlib.csvwindow
from epyqlib.svgwidget import SvgWidget
import epyqlib.txrx
import epyqlib.utils.qt
import epyqlib.widgets.progressbar
import epyqlib.widgets.lcd
import epyqlib.widgets.led
import functools
import io
import math
import platform
import threading

from PyQt5 import QtCore, QtWidgets, QtGui, uic
from PyQt5.QtCore import (QFile, QFileInfo, QTextStream, QCoreApplication,
                          Qt, pyqtSlot, QMarginsF)
from PyQt5.QtWidgets import (QApplication, QMessageBox, QFileDialog, QLabel,
                             QListWidgetItem, QAction, QMenu, QInputDialog,
                             QPlainTextEdit)
from PyQt5.QtGui import QPixmap, QPicture, QTextCursor
import time
import traceback

# See file COPYING in this source tree
__copyright__ = 'Copyright 2016, EPC Power Corp.'
__license__ = 'GPLv2+'


print(epyq.__version_tag__)


# TODO: CAMPid 9756562638416716254289247326327819
class Window(QtWidgets.QMainWindow):
    def __init__(self, ui_file, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent=parent)

        # TODO: CAMPid 980567566238416124867857834291346779
        ico_file = os.path.join(QFileInfo.absolutePath(QFileInfo(__file__)), 'icon.ico')
        ico = QtGui.QIcon(ico_file)
        self.setWindowIcon(ico)

        ui = ui_file
        # TODO: CAMPid 9549757292917394095482739548437597676742
        if not QFileInfo(ui).isAbsolute():
            ui_file = os.path.join(
                QFileInfo.absolutePath(QFileInfo(__file__)), ui)
        else:
            ui_file = ui
        ui_file = QFile(ui_file)
        ui_file.open(QFile.ReadOnly | QFile.Text)
        ts = QTextStream(ui_file)
        sio = io.StringIO(ts.readAll())
        self.ui = uic.loadUi(sio, self)

        self.ui.action_about.triggered.connect(self.about_dialog)
        self.ui.action_license.triggered.connect(self.license_dialog)
        self.ui.action_third_party_licenses.triggered.connect(
            self.third_party_licenses_dialog)

        self.ui.action_chart_log.triggered.connect(self.chart_log)

        device_tree = epyqlib.devicetree.Tree()
        self.device_tree_model = epyqlib.devicetree.Model(root=device_tree)
        self.device_tree_model.device_removed.connect(self._remove_device)
        self.ui.device_tree.setModel(self.device_tree_model)
        self.ui.device_tree.device_selected.connect(self.set_current_device)

        self.ui.collapse_button.clicked.connect(self.collapse_expand)
        size_hint = self.ui.collapse_button.sizeHint()
        size_hint.setWidth(0.75 * size_hint.width())
        size_hint.setHeight(6 * size_hint.width())
        self.ui.collapse_button.setMinimumSize(size_hint)
        self.ui.collapse_button.setMaximumSize(size_hint)

        self.subwindows = set()

        self.set_title()

        self.ui.stacked.currentChanged.connect(self.device_widget_changed)

    def device_widget_changed(self, index):
        device = self.device_tree_model.device_from_widget(
            widget=self.ui.stacked.widget(index))

        detail = None
        if device is not None:
            detail = device.name

        self.set_title(detail=detail)

    def set_title(self, detail=None):
        title = 'EPyQ v{}'.format(epyq.__version__)

        if detail is not None:
            title = ' - '.join((title, detail))

        self.setWindowTitle(title)

    def closeEvent(self, event):
        self.device_tree_model.terminate()

    def collapse_expand(self):
        self.ui.device_tree.setVisible(not self.ui.device_tree.isVisible())
        self.ui.collapse_button.setArrowType(
            Qt.LeftArrow if self.ui.device_tree.isVisible() else Qt.RightArrow)

    def dialog_from_file(self, title, file_name):
        # The Qt Installer Framework (QtIFW) likes to do a few things to license files...
        #  * '\n' -> '\r\n'
        #   * even such that '\r\n' -> '\r\r\n'
        #  * Recodes to something else (probably cp-1251)
        #
        # So, we'll just try different encodings and hope one of them works.

        encodings = [None, 'utf-8']

        for encoding in encodings:
            try:
                with open(os.path.join('Licenses', file_name), encoding=encoding) as in_file:
                    message = in_file.read()
            except UnicodeDecodeError:
                pass
            else:
                break

        self.dialog(title=title,
                    message=message,
                    scrollable=True)

    def license_dialog(self):
        self.dialog_from_file(title='EPyQ License',
                              file_name='epyq-COPYING.txt')

    def third_party_licenses_dialog(self):
        self.dialog_from_file(title='Third Party Licenses',
                              file_name='third_party-LICENSE.txt')

    def about_dialog(self):
        message = [
            __copyright__,
            __license__,
            epyq.__version_tag__
        ]

        message = '\n'.join(message)

        self.dialog(title='About EPyQ',
                    message=message)

    def dialog(self, title, message, scrollable=False):
        if not scrollable:
            box = QMessageBox(parent=self)
            box.setText(message)
        else:
            box = QInputDialog(parent=self)
            box.setOptions(QInputDialog.UsePlainTextEditForTextInput)
            box.setTextValue(message)
            box.setLabelText('')

            text_edit = box.findChildren(QPlainTextEdit)[0]

            metric = text_edit.fontMetrics()
            line_widths = sorted([metric.width(line) for line
                                  in message.splitlines()])

            index = int(0.95 * len(line_widths))
            width = line_widths[index]

            text_edit.setMinimumWidth(width * 1.1)
            text_edit.setReadOnly(True)

        box.setWindowTitle(title)

        # TODO: CAMPid 980567566238416124867857834291346779
        ico_file = os.path.join(QFileInfo.absolutePath(QFileInfo(__file__)),
                                'icon.ico')
        ico = QtGui.QIcon(ico_file)
        box.setWindowIcon(ico)

        box.exec_()

    def chart_log(self):
        filters = [
            ('CSV', ['csv']),
            ('All Files', ['*'])
        ]
        filename = epyqlib.utils.qt.file_dialog(filters, parent=self)

        if filename is not None:
            data = epyqlib.csvwindow.read_csv(filename)
            window = epyqlib.csvwindow.QtChartWindow(data=data)
            self.subwindows.add(window)
            window.closing.connect(
                functools.partial(
                    self.subwindows.discard,
                    window
                )
            )
            window.show()

    @pyqtSlot(object)
    def _remove_device(self, device):
        self.ui.stacked.removeWidget(device.ui)
        device.ui.setParent(None)
        device.terminate()

    @pyqtSlot(object)
    def set_current_device(self, device):
        self.ui.stacked.addWidget(device.ui)
        self.ui.stacked.setCurrentWidget(device.ui)


def main(args=None):
    print('starting epyq')

    # TODO: CAMPid 9757656124812312388543272342377
    app = QApplication(sys.argv)
    sys.excepthook = epyqlib.utils.qt.exception_message_box
    QtCore.qInstallMessageHandler(epyqlib.utils.qt.message_handler)
    app.setStyleSheet('QMessageBox {{ messagebox-text-interaction-flags: {}; }}'
                      .format(Qt.TextBrowserInteraction))
    app.setOrganizationName('EPC Power Corp.')
    app.setApplicationName('EPyQ')

    import qt5reactor
    qt5reactor.install()

    if args is None:
        import argparse

        ui_default = 'main.ui'

        parser = argparse.ArgumentParser()
        parser.add_argument('--ui', default=ui_default)
        parser.add_argument('--verbose', '-v', action='count', default=0)
        args = parser.parse_args()

    can_logger_modules = ('can', 'can.socketcan.native')

    for module in can_logger_modules:
        logging.getLogger(module).setLevel(logging.WARNING)

    if args.verbose >= 1:
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)

    if args.verbose >= 2:
        import twisted.internet.defer
        twisted.internet.defer.setDebugging(True)

    if args.verbose >= 3:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.verbose >= 4:
        logging.getLogger().setLevel(logging.INFO)
        for module in can_logger_modules:
            logging.getLogger(module).setLevel(logging.DEBUG)


    font_paths = [
        os.path.join(
            QtCore.QFileInfo.absolutePath(QFileInfo(__file__)),
            '..', 'venv', 'src', 'fontawesome', 'fonts', 'FontAwesome.otf'),
    ]

    for font_path in font_paths:
        # TODO: CAMPid 9549757292917394095482739548437597676742
        if not QtCore.QFileInfo(font_path).isAbsolute():
            font_path = os.path.join(
                QtCore.QFileInfo.absolutePath(QtCore.QFileInfo(__file__)),
                font_path
            )

        QtGui.QFontDatabase.addApplicationFont(font_path)

    window = Window(ui_file=args.ui)

    sys.excepthook = functools.partial(
        epyqlib.utils.qt.exception_message_box,
        version_tag=epyq.__version_tag__,
        parent=window
    )

    window.show()

    from twisted.internet import reactor
    reactor.runReturn()
    result = app.exec()
    if reactor.threadpool is not None:
        reactor._stopThreadPool()
        logging.debug('Thread pool stopped')
    logging.debug('Application ended')
    reactor.stop()
    logging.debug('Reactor stopped')

    return result


if __name__ == '__main__':
    sys.exit(main())
