from __future__ import annotations

import time
from concurrent.futures import Future, ThreadPoolExecutor

from PySide6.QtCore import QObject, QTimer, Signal

from momentum_spyrographs.core.discovery import compute_seed_metrics
from momentum_spyrographs.core.models import PreviewDocument, PreviewPayload
from momentum_spyrographs.core.project import simulate_projected_points


# Fast-preview parameters: used while the user is rapidly changing controls.
_FAST_DURATION = 12.0
_FAST_DT = 0.04
_FAST_MAX_POINTS = 600

# Full-quality parameters
_FULL_DURATION = 36.0
_FULL_DT = 0.02
_FULL_MAX_POINTS = 1800

# If a new request arrives within this window after the previous one,
# we are in "rapid interaction" mode and use the fast-preview path.
_RAPID_WINDOW_S = 0.35

# Delay before computing the full-quality follow-up after a fast preview.
_SETTLE_MS = 400


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

        # Full-quality follow-up timer
        self._settle_timer = QTimer(self)
        self._settle_timer.setSingleShot(True)
        self._settle_timer.setInterval(_SETTLE_MS)
        self._settle_timer.timeout.connect(self._submit_full_quality)

        self._latest_document: PreviewDocument | None = None
        self._latest_request_id = 0
        self._last_request_time = 0.0
        self._pending_full: PreviewDocument | None = None

    def request_preview(self, document: PreviewDocument) -> None:
        self._latest_document = document
        # Cancel any pending full-quality follow-up -- a new interaction is starting.
        self._settle_timer.stop()
        self._pending_full = None
        self._timer.start()

    def shutdown(self) -> None:
        self._timer.stop()
        self._settle_timer.stop()
        self._executor.shutdown(wait=True, cancel_futures=True)

    # ------------------------------------------------------------------

    def _submit_latest(self) -> None:
        if self._latest_document is None:
            return
        document = self._latest_document
        now = time.monotonic()
        rapid = (now - self._last_request_time) < _RAPID_WINDOW_S and self._last_request_time > 0.0
        self._last_request_time = now

        self._latest_request_id += 1
        request_id = self._latest_request_id
        self.previewStarted.emit(request_id)

        if rapid:
            # Fast preview -- lower resolution for instant feedback
            future = self._executor.submit(
                self._compute_preview, document,
                duration_cap=_FAST_DURATION, dt_floor=_FAST_DT, max_points=_FAST_MAX_POINTS,
            )
            future.add_done_callback(lambda done, rid=request_id: self._handle_result(rid, done))
            # Schedule full-quality follow-up after input settles
            self._pending_full = document
            self._settle_timer.start()
        else:
            # Normal full-quality preview
            future = self._executor.submit(
                self._compute_preview, document,
                duration_cap=_FULL_DURATION, dt_floor=_FULL_DT, max_points=_FULL_MAX_POINTS,
            )
            future.add_done_callback(lambda done, rid=request_id: self._handle_result(rid, done))

    def _submit_full_quality(self) -> None:
        """Fires after input settles -- computes the high-fidelity preview."""
        document = self._pending_full
        self._pending_full = None
        if document is None:
            return
        self._latest_request_id += 1
        request_id = self._latest_request_id
        self.previewStarted.emit(request_id)
        future = self._executor.submit(
            self._compute_preview, document,
            duration_cap=_FULL_DURATION, dt_floor=_FULL_DT, max_points=_FULL_MAX_POINTS,
        )
        future.add_done_callback(lambda done, rid=request_id: self._handle_result(rid, done))

    def _handle_result(self, request_id: int, future: Future[PreviewPayload]) -> None:
        try:
            payload = future.result()
        except Exception as exc:  # pragma: no cover - surfaced through signal
            self.previewFailed.emit(request_id, str(exc))
            return
        self.previewReady.emit(request_id, payload)

    @staticmethod
    def _compute_preview(
        document: PreviewDocument,
        *,
        duration_cap: float = _FULL_DURATION,
        dt_floor: float = _FULL_DT,
        max_points: int = _FULL_MAX_POINTS,
    ) -> PreviewPayload:
        preview_seed = document.seed.with_updates(
            duration=min(document.seed.duration, duration_cap),
            dt=max(document.seed.dt, dt_floor),
        )
        points = simulate_projected_points(preview_seed, max_points=max_points)
        if len(points) < 2:
            raise ValueError("Simulation diverged at this energy. Lower the arm energy or shorten the duration.")
        metrics = compute_seed_metrics(preview_seed, points)
        return PreviewPayload(
            document=document,
            selected_seed=document.seed,
            points=points,
            metrics=metrics,
            suggestions=tuple(),
        )
