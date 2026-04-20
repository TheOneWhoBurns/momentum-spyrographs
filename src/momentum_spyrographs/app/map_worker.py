from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor

from PySide6.QtCore import QObject, QTimer, Signal

from momentum_spyrographs.core.models import PreviewDocument, StabilityMapPayload
from momentum_spyrographs.core.stability_map import sample_stability_map


class MapWorker(QObject):
    mapStarted = Signal(int)
    mapReady = Signal(int, object)
    mapFailed = Signal(int, str)

    def __init__(self, debounce_ms: int = 250) -> None:
        super().__init__()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="stability-map")
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self._submit_latest)
        self._latest_document: PreviewDocument | None = None
        self._latest_request_id = 0

    def request_map(self, document: PreviewDocument) -> None:
        self._latest_document = document
        self._timer.start()

    def shutdown(self) -> None:
        self._timer.stop()
        self._executor.shutdown(wait=True, cancel_futures=True)

    def _submit_latest(self) -> None:
        if self._latest_document is None:
            return
        document = self._latest_document
        self._latest_request_id += 1
        request_id = self._latest_request_id
        self.mapStarted.emit(request_id)
        future = self._executor.submit(self._compute_map, document)
        future.add_done_callback(lambda done, rid=request_id: self._handle_result(rid, done))

    def _handle_result(self, request_id: int, future: Future[StabilityMapPayload]) -> None:
        try:
            payload = future.result()
        except Exception as exc:  # pragma: no cover
            self.mapFailed.emit(request_id, str(exc))
            return
        self.mapReady.emit(request_id, payload)

    @staticmethod
    def _compute_map(document: PreviewDocument) -> StabilityMapPayload:
        return sample_stability_map(document.seed)
