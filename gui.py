import os
import sys

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from run import scan_source, sync_target


class Worker(QObject):
    log = Signal(str)
    finished = Signal(bool)

    def __init__(self, mode, src_dir, dst_dir, map_path, dry_run):
        super().__init__()
        self.mode = mode
        self.src_dir = src_dir
        self.dst_dir = dst_dir
        self.map_path = map_path
        self.dry_run = dry_run

    @Slot()
    def run(self):
        try:
            def logger(message):
                self.log.emit(str(message))

            if self.mode == "scan":
                scan_source(self.src_dir, self.map_path, log_fn=logger)
            else:
                sync_target(self.dst_dir, self.map_path, dry_run=self.dry_run, log_fn=logger)
            self.finished.emit(True)
        except Exception as exc:
            self.log.emit(f"[错误] {exc}")
            self.finished.emit(False)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File-Structure-Sync")
        self.resize(720, 520)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["scan", "sync"])

        self.src_edit = QLineEdit()
        self.src_btn = QPushButton("选择目录")
        self.dst_edit = QLineEdit()
        self.dst_btn = QPushButton("选择目录")
        self.map_edit = QLineEdit("file_map.json")
        self.map_btn = QPushButton("选择文件")
        self.dry_run_chk = QCheckBox("预览模式（不实际移动）")
        self.run_btn = QPushButton("开始")

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        layout = QVBoxLayout()
        layout.addLayout(self._row("模式", self.mode_combo))
        layout.addLayout(self._row("源目录", self.src_edit, self.src_btn))
        layout.addLayout(self._row("目标目录", self.dst_edit, self.dst_btn))
        layout.addLayout(self._row("映射文件", self.map_edit, self.map_btn))
        layout.addWidget(self.dry_run_chk)
        layout.addWidget(self.run_btn)
        layout.addWidget(QLabel("日志输出："))
        layout.addWidget(self.log_view)
        self.setLayout(layout)

        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self.src_btn.clicked.connect(self._choose_src)
        self.dst_btn.clicked.connect(self._choose_dst)
        self.map_btn.clicked.connect(self._choose_map)
        self.run_btn.clicked.connect(self._start)

        self._on_mode_changed(self.mode_combo.currentText())

        self.worker_thread = None
        self.worker = None

    def _row(self, label, *widgets):
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        for w in widgets:
            row.addWidget(w)
        return row

    def _on_mode_changed(self, mode):
        is_scan = mode == "scan"
        self.src_edit.setEnabled(is_scan)
        self.src_btn.setEnabled(is_scan)
        self.dst_edit.setEnabled(not is_scan)
        self.dst_btn.setEnabled(not is_scan)
        self.dry_run_chk.setEnabled(not is_scan)
        if is_scan and not self.map_edit.text().strip():
            self.map_edit.setText("file_map.json")

    def _choose_src(self):
        path = QFileDialog.getExistingDirectory(self, "选择源目录")
        if path:
            self.src_edit.setText(path)

    def _choose_dst(self):
        path = QFileDialog.getExistingDirectory(self, "选择目标目录")
        if path:
            self.dst_edit.setText(path)

    def _choose_map(self):
        mode = self.mode_combo.currentText()
        if mode == "scan":
            path, _ = QFileDialog.getSaveFileName(
                self, "保存映射文件", self.map_edit.text() or "file_map.json", "JSON 文件 (*.json)"
            )
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "选择映射文件", self.map_edit.text() or "", "JSON 文件 (*.json)"
            )
        if path:
            self.map_edit.setText(path)

    def _validate_inputs(self):
        mode = self.mode_combo.currentText()
        src_dir = self.src_edit.text().strip()
        dst_dir = self.dst_edit.text().strip()
        map_path = self.map_edit.text().strip()

        if not map_path:
            QMessageBox.warning(self, "提示", "请指定映射文件路径。")
            return None

        if mode == "scan":
            if not src_dir:
                QMessageBox.warning(self, "提示", "请指定源目录。")
                return None
            if not os.path.isdir(src_dir):
                QMessageBox.warning(self, "提示", "源目录不存在。")
                return None
        else:
            if not dst_dir:
                QMessageBox.warning(self, "提示", "请指定目标目录。")
                return None
            if not os.path.isdir(dst_dir):
                QMessageBox.warning(self, "提示", "目标目录不存在。")
                return None
            if not os.path.isfile(map_path):
                QMessageBox.warning(self, "提示", "映射文件不存在。")
                return None

        return mode, src_dir, dst_dir, map_path

    def _set_running(self, running):
        self.run_btn.setEnabled(not running)
        self.mode_combo.setEnabled(not running)
        self.src_edit.setEnabled(not running and self.mode_combo.currentText() == "scan")
        self.src_btn.setEnabled(not running and self.mode_combo.currentText() == "scan")
        self.dst_edit.setEnabled(not running and self.mode_combo.currentText() == "sync")
        self.dst_btn.setEnabled(not running and self.mode_combo.currentText() == "sync")
        self.map_edit.setEnabled(not running)
        self.map_btn.setEnabled(not running)
        self.dry_run_chk.setEnabled(not running and self.mode_combo.currentText() == "sync")
        self.run_btn.setText("运行中..." if running else "开始")

    def _start(self):
        inputs = self._validate_inputs()
        if not inputs:
            return
        mode, src_dir, dst_dir, map_path = inputs
        dry_run = self.dry_run_chk.isChecked()

        self.log_view.clear()
        self._set_running(True)

        self.worker_thread = QThread()
        self.worker = Worker(mode, src_dir, dst_dir, map_path, dry_run)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.log.connect(self._append_log)
        self.worker.finished.connect(self._on_finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    def _append_log(self, message):
        self.log_view.append(message)

    def _on_finished(self, ok):
        self._set_running(False)
        if ok:
            QMessageBox.information(self, "完成", "操作已完成。")
        else:
            QMessageBox.warning(self, "提示", "操作未成功完成，请查看日志。")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
