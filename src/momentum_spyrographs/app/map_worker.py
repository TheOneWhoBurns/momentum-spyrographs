from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor

from PySide6.QtCore import QObject, QTimer, Signal

from momentum_spyrographs.core.map_tiles import RESOLUTION_LEVELS
from momentum_spyrographs.core.models import MapRequest, StabilityMapPayload
from momentum_spyrographs.core.stability_map import render_map_level


class MapWorker(QObject):
    mapStarted = Signal(int)
    mapReady = Signal(int, object)
    mapFailed = Signal(int, str)

    def __init__(self, debounce_ms: int = 250, *, cache_limit: int = 24) -> None:
        super().__init__()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="stability-map")
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self._submit_latest)
        self._latest_request: MapRequest | None = None
        self._latest_request_id = 0
        self._cache_limit = cache_limit
        self._level_cache: OrderedDict[tuple, StabilityMapPayload] = OrderedDict()
        self._final_cache_key: tuple | None = None
        self._final_payload: StabilityMapPayload | None = None
        self._requested_serial = 0

    def request_map(self, request: MapRequest) -> None:
        self._requested_serial += 1
        self._latest_request = request
        final_key = self._request_cache_key(request, RESOLUTION_LEVELS[-1])
        if self._final_cache_key == final_key and self._final_payload is not None:
            request_id = self._requested_serial
            self.mapStarted.emit(request_id)
            self.mapReady.emit(request_id, self._with_selection(self._final_payload, request))
            return
        self._timer.start()

    def shutdown(self) -> None:
        self._timer.stop()
        self._executor.shutdown(wait=True, cancel_futures=True)

    def _submit_latest(self) -> None:
        if self._latest_request is None:
            return
        request = self._latest_request
        request_id = self._requested_serial
        self._latest_request_id = request_id
        self.mapStarted.emit(request_id)
        future = self._executor.submit(self._compute_progressive, request)
        future.add_done_callback(lambda done, rid=request_id: self._handle_result(rid, done))

    def _handle_result(self, request_id: int, future: Future[list[StabilityMapPayload]]) -> None:
        if request_id != self._requested_serial:
            return
        try:
            payloads = future.result()
        except Exception as exc:  # pragma: no cover
            self.mapFailed.emit(request_id, str(exc))
            return
        for payload in payloads:
            self.mapReady.emit(request_id, payload)

    def _compute_progressive(self, request: MapRequest) -> list[StabilityMapPayload]:
        payloads: list[StabilityMapPayload] = []
        for level in RESOLUTION_LEVELS:
            cache_key = self._request_cache_key(request, level)
            cached = self._level_cache.get(cache_key)
            if cached is None:
                rendered = render_map_level(request, resolution_level=level)
                self._level_cache[cache_key] = rendered
                self._level_cache.move_to_end(cache_key)
                while len(self._level_cache) > self._cache_limit:
                    self._level_cache.popitem(last=False)
                cached = rendered
            payload = self._with_selection(cached, request)
            payloads.append(payload)
            if level == RESOLUTION_LEVELS[-1]:
                self._final_cache_key = cache_key
                self._final_payload = cached
        return payloads

    @staticmethod
    def _request_cache_key(request: MapRequest, level: int) -> tuple:
        viewport = request.viewport
        return (
            *request.structural_key,
            round(viewport.center_omega1, 6),
            round(viewport.center_omega2, 6),
            round(viewport.span_omega1, 6),
            round(viewport.span_omega2, 6),
            level,
        )

    @staticmethod
    def _with_selection(payload: StabilityMapPayload, request: MapRequest) -> StabilityMapPayload:
        return StabilityMapPayload(
            image=payload.image,
            periodicity=payload.periodicity,
            chaos=payload.chaos,
            loop_score=payload.loop_score,
            overlay_seed=request.seed,
            selected_omega1=request.selected_omega1,
            selected_omega2=request.selected_omega2,
            viewport_omega1_min=payload.viewport_omega1_min,
            viewport_omega1_max=payload.viewport_omega1_max,
            viewport_omega2_min=payload.viewport_omega2_min,
            viewport_omega2_max=payload.viewport_omega2_max,
            resolution_level=payload.resolution_level,
            tile_size=payload.tile_size,
            pending_tiles=payload.pending_tiles,
            completed_tiles=payload.completed_tiles,
        )
