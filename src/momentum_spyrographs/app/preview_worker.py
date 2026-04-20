from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor

from PySide6.QtCore import QObject, QTimer, Signal

from momentum_spyrographs.core.analysis_config import canonical_seed
from momentum_spyrographs.core.discovery import compute_seed_metrics
from momentum_spyrographs.core.models import PreviewDocument, PreviewPayload
from momentum_spyrographs.core.project import simulate_projected_path

_MAX_POINTS = 1800


class PreviewWorker(QObject):
    previewStarted = Signal(int)
    previewReady = Signal(int, object)
    previewFailed = Signal(int, str)

    def __init__(self, debounce_ms: int = 150) -> None:
        super().__init__()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="preview")
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self._submit_latest)
        self._latest_document: PreviewDocument | None = None
        self._latest_request_id = 0

    def request_preview(self, document: PreviewDocument) -> None:
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
        self.previewStarted.emit(request_id)
        future = self._executor.submit(self._compute_preview, document)
        future.add_done_callback(lambda done, rid=request_id: self._handle_result(rid, done))

    def _handle_result(self, request_id: int, future: Future[PreviewPayload]) -> None:
        try:
            payload = future.result()
        except Exception as exc:  # pragma: no cover - surfaced through signal
            self.previewFailed.emit(request_id, str(exc))
            return
        self.previewReady.emit(request_id, payload)

    @staticmethod
    def _compute_preview(document: PreviewDocument) -> PreviewPayload:
        preview_seed = canonical_seed(document.seed)
        points, states = simulate_projected_path(preview_seed, max_points=_MAX_POINTS)
        if len(points) < 2:
            raise ValueError("Simulation diverged inside the 24.0s analysis window.")
        metrics = compute_seed_metrics(preview_seed, points, states=states)
        return PreviewPayload(
            document=document,
            selected_seed=document.seed,
            points=points,
            metrics=metrics,
            suggestions=tuple(),
        )
