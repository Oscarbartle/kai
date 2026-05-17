"""Background worker for refreshing Woolworths metadata without blocking the UI."""

from __future__ import annotations
import random
import time

from PySide6.QtCore import Qt, QObject, Signal, QRunnable, QThreadPool
from PySide6.QtWidgets import QPushButton

# Module-level progress signals — connect to these from the main window.
class _ProgressSignals(QObject):
    started  = Signal(int)       # total items
    step     = Signal(int, int)  # (completed, total)
    finished = Signal()

progress = _ProgressSignals()

# Keep strong refs to signal objects alive until tasks finish.
_active: list[object] = []


class _RefreshRunnable(QRunnable):
    def __init__(self, item_names: list[str], signals: _ProgressSignals, delay: float):
        super().__init__()
        self.setAutoDelete(True)
        self._item_names = item_names
        self._signals = signals
        self._delay = delay

    def run(self):
        from kai.core.backend import get_item
        item_obj = get_item()
        total = len(self._item_names)
        for i, name in enumerate(self._item_names):
            try:
                item_obj.refresh_online_data(name)
            except Exception:
                pass
            progress.step.emit(i + 1, total)
            if self._delay > 0 and i < total - 1:
                time.sleep(self._delay + random.uniform(-0.5, 2.0))
        self._signals.finished.emit()


def run_refresh(
    item_names: list[str],
    on_done=None,
    parent=None,
    button: QPushButton | None = None,
    delay: float = 0.0,
) -> None:
    """Refresh item metadata in a background thread pool worker.

    *delay* — seconds to wait between successive API calls (use 2–3 for bulk
    refreshes to avoid being rate-limited by Woolworths).

    If *button* is supplied it is disabled and labelled '…' while the
    refresh runs, then restored afterwards.
    """
    signals = _ProgressSignals()
    _active.append(signals)

    total = len(item_names)
    progress.started.emit(total)

    original_text: str | None = None
    if button is not None:
        original_text = button.text()
        button.setText("…")
        button.setEnabled(False)

    def _on_done():
        progress.finished.emit()
        if button is not None:
            button.setText(original_text or "↻")
            button.setEnabled(True)
        if on_done:
            callbacks = on_done if isinstance(on_done, list) else [on_done]
            for cb in callbacks:
                cb()
        if signals in _active:
            _active.remove(signals)

    signals.finished.connect(_on_done, Qt.ConnectionType.QueuedConnection)

    task = _RefreshRunnable(item_names, signals, delay)
    QThreadPool.globalInstance().start(task)
