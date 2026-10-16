# SPDX-License-Identifier: GPL-3.0-or-later
"""Main PySide6 window."""

from __future__ import annotations

import hashlib

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import edid
from ..apply import kscreen
from ..color import icc, model
from ..paths import profile_dir, profile_path
from ..settings import CHANNELS, Channel, ColorSettings, load_settings, save_settings
from .pattern import PatternWidget

CHANNEL_LABELS = {"__all__": "All channels", "red": "Red", "green": "Green", "blue": "Blue"}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("plasma-tint — per-channel display colour adjustment")
        self.settings: ColorSettings = load_settings()
        self._loading = False
        self._outputs: list[kscreen.Output] = []

        self._live_timer = QTimer(self)
        self._live_timer.setSingleShot(True)
        self._live_timer.setInterval(350)
        self._live_timer.timeout.connect(self._apply_live)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(600)
        self._save_timer.timeout.connect(lambda: save_settings(self.settings))

        self._build_ui()
        self._refresh_outputs()
        self._load_channel_into_sliders()
        self._update_preview()

    # -- UI construction ---------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.addWidget(self._build_controls(), 0)

        self.on_screen_pattern = PatternWidget(simulate=False)
        self.simulated_pattern = PatternWidget(simulate=True)
        tabs = QTabWidget()
        tabs.addTab(self.on_screen_pattern, "On-screen pattern")
        tabs.addTab(self.simulated_pattern, "Simulated preview")
        wrapper = QWidget()
        box = QVBoxLayout(wrapper)
        box.addWidget(tabs)
        note = QLabel(
            "“On-screen pattern” is neutral — look at it on the corrected screen.\n"
            "Screenshots and colour pickers capture the buffer <i>before</i> the adjustment, "
            "so they will not show the effect."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(mid);")
        box.addWidget(note)
        root.addWidget(wrapper, 1)

        self.statusBar().showMessage("Ready")

    def _build_controls(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # -- display --
        display_box = QGroupBox("Display")
        display_form = QFormLayout(display_box)
        self.output_combo = QComboBox()
        self.output_combo.currentIndexChanged.connect(self._on_output_changed)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._refresh_outputs)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.output_combo, 1)
        row_layout.addWidget(self.refresh_button)
        display_form.addRow("Output", row)
        self.hdr_check = QCheckBox("Apply as HDR profile (hdrIccProfile)")
        self.hdr_check.stateChanged.connect(lambda _=None: self._schedule_live())
        display_form.addRow("", self.hdr_check)
        layout.addWidget(display_box)

        # -- colour correction --
        color_box = QGroupBox("Colour correction")
        color_layout = QVBoxLayout(color_box)
        self.channel_combo = QComboBox()
        for key, label in CHANNEL_LABELS.items():
            self.channel_combo.addItem(label, key)
        self.channel_combo.currentIndexChanged.connect(self._load_channel_into_sliders)
        color_layout.addWidget(self.channel_combo)

        form = QFormLayout()
        self.brightness_slider, self.brightness_spin = self._add_control(
            form, "Brightness", -100, 100, 0, decimals=0
        )
        self.contrast_slider, self.contrast_spin = self._add_control(
            form, "Contrast", -100, 100, 0, decimals=0
        )
        self.gamma_slider, self.gamma_spin = self._add_control(
            form, "Gamma", 10, 1000, 100, decimals=2
        )
        color_layout.addLayout(form)

        reset_row = QWidget()
        reset_layout = QHBoxLayout(reset_row)
        reset_layout.setContentsMargins(0, 0, 0, 0)
        reset_channel = QPushButton("Reset channel")
        reset_channel.clicked.connect(self._reset_channel)
        reset_all = QPushButton("Reset all")
        reset_all.clicked.connect(self._reset_all)
        reset_layout.addWidget(reset_channel)
        reset_layout.addWidget(reset_all)
        color_layout.addWidget(reset_row)
        layout.addWidget(color_box)

        # -- apply --
        apply_box = QGroupBox("Apply")
        apply_layout = QVBoxLayout(apply_box)
        self.live_check = QCheckBox("Live preview (re-applies as you drag)")
        self.live_check.setChecked(True)
        apply_layout.addWidget(self.live_check)
        apply_now = QPushButton("Apply now")
        apply_now.clicked.connect(self._apply_live)
        revert = QPushButton("Revert (back to sRGB/EDID)")
        revert.clicked.connect(self._revert)
        save_button = QPushButton("Save profile as…")
        save_button.clicked.connect(self._save_profile_as)
        apply_layout.addWidget(apply_now)
        apply_layout.addWidget(revert)
        apply_layout.addWidget(save_button)
        layout.addWidget(apply_box)

        layout.addStretch(1)
        return panel

    def _add_control(self, form, label, lo, hi, default, decimals):
        """Add a slider plus a synced spin box (exact numeric entry / fine steps)."""
        scale = 10**decimals
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(default)
        slider.setSingleStep(1)
        slider.setPageStep(max(1, (hi - lo) // 20))

        if decimals == 0:
            spin: QSpinBox | QDoubleSpinBox = QSpinBox()
            spin.setRange(lo, hi)
        else:
            spin = QDoubleSpinBox()
            spin.setDecimals(decimals)
            spin.setRange(lo / scale, hi / scale)
            spin.setSingleStep(10 ** (-decimals))
            spin.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
        spin.setValue(default / scale)
        spin.setFixedWidth(84)
        spin.setKeyboardTracking(False)

        def on_slider(value: int) -> None:
            spin.blockSignals(True)
            spin.setValue(value / scale)
            spin.blockSignals(False)
            self._on_control_changed()

        def on_spin(value) -> None:
            slider.blockSignals(True)
            slider.setValue(int(round(value * scale)))
            slider.blockSignals(False)
            self._on_control_changed()

        slider.valueChanged.connect(on_slider)
        spin.valueChanged.connect(on_spin)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(slider, 1)
        row_layout.addWidget(spin)
        form.addRow(label, row)
        return slider, spin

    # -- state helpers -----------------------------------------------------

    def _current_output(self) -> kscreen.Output | None:
        index = self.output_combo.currentIndex()
        if 0 <= index < len(self._outputs):
            return self._outputs[index]
        return None

    def _target_channels(self) -> list[str]:
        selected = self.channel_combo.currentData()
        return list(CHANNELS) if selected == "__all__" else [selected]

    # -- events ------------------------------------------------------------

    def _on_control_changed(self, *args) -> None:
        if self._loading:
            return
        brightness = self.brightness_slider.value() / 100.0
        contrast = self.contrast_slider.value() / 100.0
        gamma = self.gamma_slider.value() / 100.0
        for name in self._target_channels():
            self.settings.set(name, Channel(brightness, contrast, gamma))
        self._update_preview()
        self._save_timer.start()
        self._schedule_live()

    def _load_channel_into_sliders(self, _index: int = 0) -> None:
        names = self._target_channels()
        representative = self.settings.get(names[0] if names else "red")
        self._loading = True
        self.brightness_slider.setValue(int(round(representative.brightness * 100)))
        self.contrast_slider.setValue(int(round(representative.contrast * 100)))
        self.gamma_slider.setValue(int(round(representative.gamma * 100)))
        self._loading = False

    def _reset_channel(self) -> None:
        for name in self._target_channels():
            self.settings.set(name, Channel())
        self._load_channel_into_sliders()
        self._update_preview()
        self._save_timer.start()
        self._schedule_live()

    def _reset_all(self) -> None:
        self.settings.reset()
        self._load_channel_into_sliders()
        self._update_preview()
        self._save_timer.start()
        self._schedule_live()

    def _refresh_outputs(self) -> None:
        try:
            self._outputs = kscreen.list_outputs()
        except kscreen.KScreenError as error:
            self.statusBar().showMessage(str(error))
            self._outputs = []
        self.output_combo.blockSignals(True)
        self.output_combo.clear()
        for output in self._outputs:
            self.output_combo.addItem(output.label)
        self.output_combo.blockSignals(False)
        for index, output in enumerate(self._outputs):
            if output.hdr_capable:
                self.output_combo.setCurrentIndex(index)
                break
        self._on_output_changed()

    def _on_output_changed(self, _index: int = 0) -> None:
        output = self._current_output()
        capable = bool(output and output.hdr_capable)
        self.hdr_check.setEnabled(capable)
        if not capable:
            self.hdr_check.setChecked(False)
        if output:
            self.hdr_check.setText(
                f"Apply as HDR profile ({'capable' if capable else 'not HDR-capable'})"
            )

    # -- preview / apply ---------------------------------------------------

    def _update_preview(self) -> None:
        luts = model.build_luts(self.settings)
        self.on_screen_pattern.set_luts(luts)
        self.simulated_pattern.set_luts(luts)

    def _schedule_live(self) -> None:
        if self.live_check.isChecked():
            self._live_timer.start()

    def _build_profile(self) -> tuple[bytes, str]:
        """Return ``(profile_bytes, human_description)`` for the current state."""
        output = self._current_output()
        luts = model.build_luts(self.settings)
        if self.hdr_check.isChecked():
            luminance = edid.hdr_luminance(output.name) if output else None
            if luminance is not None:
                data = icc.build_hdr_profile(
                    luts,
                    peak_luminance=luminance.max_nits,
                    max_fall=luminance.max_average_nits,
                    min_luminance=luminance.min_nits,
                )
                return data, f"HDR, BT.2020, peak {luminance.max_nits:.0f} nits"
            return icc.build_hdr_profile(luts), "HDR, BT.2020, default luminance"
        return icc.build_profile(luts), "SDR"

    def _store_profile(self, name: str, hdr: bool, data: bytes) -> "object":
        """Write ``data`` to a content-hashed path so KWin always reloads.

        KWin (via libkscreen) treats an unchanged ``hdrIccProfile`` path as a
        no-op, so re-using one filename silently drops later edits. A hash in
        the name guarantees the path changes whenever the profile does.
        """
        mode = "hdr" if hdr else "sdr"
        digest = hashlib.sha1(data).hexdigest()[:10]
        path = profile_dir() / f"{name}.{mode}.{digest}.icc"
        for stale in profile_dir().glob(f"{name}.{mode}.*.icc"):
            if stale.name != path.name:
                try:
                    stale.unlink()
                except OSError:
                    pass
        path.write_bytes(data)
        return path

    def _apply_live(self) -> None:
        output = self._current_output()
        if output is None:
            self.statusBar().showMessage("No output selected")
            return
        hdr = self.hdr_check.isChecked()
        data, description = self._build_profile()
        path = self._store_profile(output.name, hdr, data)
        try:
            kscreen.apply_profile(output.name, str(path), hdr=hdr)
        except kscreen.KScreenError as error:
            self.statusBar().showMessage(f"Apply failed: {error}")
            return
        self.statusBar().showMessage(f"Applied {description} to {output.name}")

    def _revert(self) -> None:
        output = self._current_output()
        if output is None:
            return
        try:
            kscreen.revert(output.name, hdr=self.hdr_check.isChecked())
        except kscreen.KScreenError as error:
            self.statusBar().showMessage(f"Revert failed: {error}")
            return
        self.statusBar().showMessage(f"Reverted {output.name} to default colour source")

    def _save_profile_as(self) -> None:
        output = self._current_output()
        hdr = self.hdr_check.isChecked()
        suggested = str(profile_path(output.name, hdr)) if output else "plasma-tint.icc"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save ICC profile", suggested, "ICC profiles (*.icc)"
        )
        if not path:
            return
        data, description = self._build_profile()
        from pathlib import Path

        Path(path).write_bytes(data)
        self.statusBar().showMessage(f"Saved {description} profile to {path}")
