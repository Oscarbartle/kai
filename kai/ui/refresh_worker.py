"""Background worker for refreshing Woolworths metadata without blocking the UI."""

from PySide6.QtCore import QThread, Signal, Qt

# Module-level list keeps Python references alive until threads finish.
_active_threads: list[QThread] = []


class _RefreshThread(QThread):
    def __init__(self, item_names: list[str]):
        super().__init__()
        self._item_names = item_names

    def run(self):
        from kai.objects.item import Item
        item_obj = Item()
        for name in self._item_names:
            try:
                item_obj.refresh_online_data(name)
            except Exception as e:
                print(f"[RefreshThread] error refreshing '{name}': {e}")


def run_refresh(item_names: list[str], on_done=None, parent=None) -> QThread:
    """Spawn a background thread to refresh metadata for the given item names."""
    thread = _RefreshThread(item_names)

    if on_done:
        callbacks = on_done if isinstance(on_done, list) else [on_done]
        for cb in callbacks:
            # QueuedConnection ensures callbacks run on the main thread
            thread.finished.connect(cb, Qt.ConnectionType.QueuedConnection)

    def _cleanup():
        if thread in _active_threads:
            _active_threads.remove(thread)

    thread.finished.connect(_cleanup)
    _active_threads.append(thread)
    thread.start()
    return thread
