"""Local time and approximate location for agent system prompts (macOS / PyObjC)."""

from __future__ import annotations

import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any

_CACHE_LOCK = threading.Lock()
_CACHE_EXPIRES: float = 0.0
_CACHE_LINE: str = "Unknown"

_TTL_SECONDS = 300.0
_TOTAL_WAIT = 5.0


def _format_time_string() -> str:
    now = datetime.now(timezone.utc).astimezone()
    tzinfo = now.tzinfo
    iana = ""
    if tzinfo is not None and getattr(tzinfo, "key", None):
        iana = f" ({tzinfo.key})"
    abbrev = now.strftime("%Z")
    dow = now.strftime("%A")
    return f"{dow}, {now.strftime('%Y-%m-%d %H:%M')} {abbrev}{iana}"


def _street_line(pm: Any) -> str | None:
    if pm is None:
        return None
    try:
        sub = pm.subThoroughfare()
        th = pm.thoroughfare()
    except Exception:
        return None
    parts: list[str] = []
    if sub:
        parts.append(str(sub))
    if th:
        parts.append(str(th))
    if not parts:
        return None
    return " ".join(parts)


def _format_placemark_description(pm: Any) -> str:
    """Human-readable place; 'Unknown' if nothing usable."""
    if pm is None:
        return "Unknown"
    try:
        name_o = pm.name()
        name = str(name_o).strip() if name_o else ""
    except Exception:
        name = ""
    street = _street_line(pm)
    try:
        locality = str(pm.locality()).strip() if pm.locality() else ""
    except Exception:
        locality = ""
    try:
        admin = str(pm.administrativeArea()).strip() if pm.administrativeArea() else ""
    except Exception:
        admin = ""
    try:
        country = str(pm.country()).strip() if pm.country() else ""
    except Exception:
        country = ""

    poi = ""
    if name:
        if street and name.strip() == street.strip():
            pass
        elif street and street in name:
            pass
        else:
            poi = name

    tail = ", ".join(x for x in (locality, admin, country) if x)
    if poi and tail:
        return f"{poi}, {tail}"
    if tail:
        return tail
    if poi:
        return poi
    if street:
        return street
    return "Unknown"


def _location_line_from_state(lat: float | None, lon: float | None, desc: str) -> str:
    if lat is None or lon is None:
        return "Unknown"
    coord = f"{lat:.4f}, {lon:.4f}"
    if not desc or desc == "Unknown":
        return f"{coord} — Unknown"
    return f"{coord} — {desc}"


def _auth_int() -> int:
    if sys.platform != "darwin":
        return -1
    try:
        from CoreLocation import CLLocationManager

        return int(CLLocationManager.authorizationStatus())
    except Exception:
        return -1


def _is_authorized(auth: int) -> bool:
    try:
        from CoreLocation import (
            kCLAuthorizationStatusAuthorizedAlways,
            kCLAuthorizationStatusAuthorizedWhenInUse,
        )

        return auth in (
            int(kCLAuthorizationStatusAuthorizedAlways),
            int(kCLAuthorizationStatusAuthorizedWhenInUse),
        )
    except Exception:
        return False


def _is_denied_or_restricted(auth: int) -> bool:
    try:
        from CoreLocation import (
            kCLAuthorizationStatusDenied,
            kCLAuthorizationStatusRestricted,
        )

        return auth in (
            int(kCLAuthorizationStatusDenied),
            int(kCLAuthorizationStatusRestricted),
        )
    except Exception:
        return False


if sys.platform == "darwin":
    try:
        from Foundation import NSDate, NSDefaultRunLoopMode, NSObject, NSRunLoop
        from CoreLocation import (
            CLGeocoder,
            CLLocationManager,
            kCLLocationAccuracyKilometer,
        )

        class _LocationDelegate(NSObject):
            """CLLocationManager delegate; ``macllm_state`` must be set to a shared dict."""

            def locationManagerDidChangeAuthorization_(self, manager) -> None:  # noqa: N802
                state = getattr(self, "macllm_state", None)
                if not isinstance(state, dict):
                    return
                if state.get("updates_started"):
                    return
                if _is_authorized(_auth_int()):
                    state["updates_started"] = True
                    manager.startUpdatingLocation()

            def locationManager_didUpdateLocations_(self, manager, locations) -> None:  # noqa: N802
                state = getattr(self, "macllm_state", None)
                if not isinstance(state, dict) or state.get("geocode_started"):
                    return
                if not locations:
                    return
                loc_obj = locations[-1]
                try:
                    coord = loc_obj.coordinate()
                    lat, lon = float(coord.latitude), float(coord.longitude)
                except Exception:
                    state["done"] = True
                    return
                state["lat"] = lat
                state["lon"] = lon
                state["geocode_started"] = True
                manager.stopUpdatingLocation()

                geocoder = CLGeocoder.alloc().init()

                def on_placemarks(placemarks, error) -> None:  # noqa: ARG001
                    try:
                        if placemarks and len(placemarks) > 0:
                            state["desc"] = _format_placemark_description(placemarks[0])
                    finally:
                        state["geocode_done"] = True
                        state["done"] = True

                try:
                    geocoder.reverseGeocodeLocation_completionHandler_(loc_obj, on_placemarks)
                except Exception:
                    state["geocode_done"] = True
                    state["done"] = True

            def locationManager_didFailWithError_(self, manager, error) -> None:  # noqa: N802, ARG002
                state = getattr(self, "macllm_state", None)
                if isinstance(state, dict) and not state.get("geocode_started"):
                    state["done"] = True

        _LOCATION_IMPORTS_OK = True
    except Exception:
        _LOCATION_IMPORTS_OK = False
else:
    _LOCATION_IMPORTS_OK = False


def _location_worker(state: dict[str, Any]) -> None:
    if not _LOCATION_IMPORTS_OK:
        state["done"] = True
        return

    try:
        delegate = _LocationDelegate.alloc().init()
        delegate.macllm_state = state
        manager = CLLocationManager.alloc().init()
        manager.setDelegate_(delegate)

        auth = _auth_int()
        if _is_denied_or_restricted(auth):
            state["done"] = True
            return

        manager.setDesiredAccuracy_(kCLLocationAccuracyKilometer)

        if _is_authorized(auth):
            state["updates_started"] = True
            manager.startUpdatingLocation()
        elif auth == 0:
            try:
                manager.requestWhenInUseAuthorization()
            except Exception:
                state["done"] = True
                return
            state["updates_started"] = True
            manager.startUpdatingLocation()
        else:
            state["done"] = True
            return

        deadline = time.time() + _TOTAL_WAIT
        rl = NSRunLoop.currentRunLoop()
        while time.time() < deadline and not state["done"]:
            rl.runMode_beforeDate_(
                NSDefaultRunLoopMode,
                NSDate.dateWithTimeIntervalSinceNow_(0.05),
            )
        manager.stopUpdatingLocation()
        manager.setDelegate_(None)
        if state.get("geocode_started") and not state.get("geocode_done"):
            state["done"] = True
        if not state.get("geocode_started"):
            state["done"] = True
    except Exception:
        state["done"] = True


def _fetch_location_line_uncached() -> str:
    if sys.platform != "darwin" or not _LOCATION_IMPORTS_OK:
        return "Unknown"
    state: dict[str, Any] = {
        "done": False,
        "lat": None,
        "lon": None,
        "desc": "Unknown",
        "geocode_started": False,
        "geocode_done": False,
        "updates_started": False,
    }
    t = threading.Thread(target=_location_worker, args=(state,), daemon=True)
    t.start()
    t.join(_TOTAL_WAIT + 1.0)
    return _location_line_from_state(
        state.get("lat"),
        state.get("lon"),
        str(state.get("desc") or "Unknown"),
    )


def _cached_location_line() -> str:
    global _CACHE_EXPIRES, _CACHE_LINE
    now = time.monotonic()
    with _CACHE_LOCK:
        if now < _CACHE_EXPIRES and _CACHE_LINE:
            return _CACHE_LINE
    line = _fetch_location_line_uncached()
    with _CACHE_LOCK:
        _CACHE_LINE = line
        _CACHE_EXPIRES = time.monotonic() + _TTL_SECONDS
    return line


def get_device_context() -> str:
    """Two-line block: current local time (with IANA zone) and location line."""
    time_s = _format_time_string()
    loc = _cached_location_line()
    return f"Current time: {time_s}\nLocation: {loc}"
