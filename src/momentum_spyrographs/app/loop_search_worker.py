from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor

from PySide6.QtCore import QObject, QTimer, Signal

from momentum_spyrographs.core.models import RegionSearchRequest, RegionSearchResult
from momentum_spyrographs.core.stability_map import search_stable_minima


class LoopSearchWorker(QObject):
    searchStarted = Signal(int)
    searchReady = Signal(int, object)
    searchFailed = Signal(int, str)

    def __init__(self, debounce_ms: int = 60) -> None:
        super().__init__()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="loop-search")
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self._submit_latest)
        self._latest_request: RegionSearchRequest | None = None
        self._requested_serial = 0

    def request_search(self, request: RegionSearchRequest) -> None:
        self._requested_serial += 1
        self._latest_request = request
        self._timer.start()

    def cancel_pending(self) -> None:
        self._requested_serial += 1
        self._latest_request = None
        self._timer.stop()

    def shutdown(self) -> None:
        self._timer.stop()
        self._executor.shutdown(wait=True, cancel_futures=True)

    def _submit_latest(self) -> None:
        if self._latest_request is None:
            return
        request_id = self._requested_serial
        request = self._latest_request
        self.searchStarted.emit(request_id)
        future = self._executor.submit(search_stable_minima, request)
        future.add_done_callback(lambda done, rid=request_id: self._handle_result(rid, done))

    def _handle_result(self, request_id: int, future: Future[RegionSearchResult]) -> None:
        if request_id != self._requested_serial:
            return
        try:
            result = future.result()
        except Exception as exc:  # pragma: no cover
            self.searchFailed.emit(request_id, str(exc))
            return
        self.searchReady.emit(request_id, result)
