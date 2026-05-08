"""Local time and approximate location for agent system prompts (macOS / PyObjC).

The location path mirrors ``~/dev/myprojects/geoloc/geoloc.py``: it polls
``CLLocationManager.location()`` instead of installing a delegate, then asks
``CLGeocoder`` for a ``CLPlacemark`` and concatenates whatever populated fields
Apple returns. We never invent any field that the OS did not give us.
"""

from __future__ import annotations

import sys
import threading
import time
from datetime import datetime, timezone

_CACHE_LOCK = threading.Lock()
_CACHE_EXPIRES: float = 0.0
_CACHE_LOC_TEXT: str = "Unknown"
_CACHE_GPS_TEXT: str = "Unknown"

_TTL_SECONDS = 300.0
_LOCATION_WAIT = 5.0
_GEOCODE_WAIT = 5.0


def _debug(msg: str, level: int = 1) -> None:
    """Forward to ``MacLLM.debug_log`` when the app is up; otherwise no-op."""
    try:
        from macllm.macllm import MacLLM

        if MacLLM._instance is not None:
            MacLLM._instance.debug_log(msg, level)
    except Exception:
        pass


def _format_time_string() -> str:
    now = datetime.now(timezone.utc).astimezone()
    iana = ""
    tzinfo = now.tzinfo
    if tzinfo is not None and getattr(tzinfo, "key", None):
        iana = f" ({tzinfo.key})"
    return f"{now.strftime('%A')}, {now.strftime('%Y-%m-%d %H:%M')} {now.strftime('%Z')}{iana}"


_PLACEMARK_FIELDS = (
    "name",
    "subThoroughfare",
    "thoroughfare",
    "subLocality",
    "locality",
    "subAdministrativeArea",
    "administrativeArea",
    "postalCode",
    "country",
)


def _placemark_field(pm, attr: str) -> str:
    try:
        value = getattr(pm, attr)()
    except Exception:
        return ""
    if not value:
        return ""
    return str(value).strip()


def _format_placemark_description(pm) -> str:
    """Return ``", "``-joined non-empty placemark fields, deduplicated.

    Only Apple-provided fields are echoed; nothing is invented. When ``name``
    already contains the street number/name (e.g. ``"140 Campo Bello Ln"``),
    the redundant ``subThoroughfare``/``thoroughfare`` entries are dropped.
    """
    if pm is None:
        return "Unknown"

    name = _placemark_field(pm, "name")
    sub_thoro = _placemark_field(pm, "subThoroughfare")
    thoro = _placemark_field(pm, "thoroughfare")
    skip: set[str] = set()
    if name:
        if sub_thoro and sub_thoro in name:
            skip.add("subThoroughfare")
        if thoro and thoro in name:
            skip.add("thoroughfare")

    seen: set[str] = set()
    parts: list[str] = []
    for attr in _PLACEMARK_FIELDS:
        if attr in skip:
            continue
        s = _placemark_field(pm, attr)
        if not s or s in seen:
            continue
        seen.add(s)
        parts.append(s)
    return ", ".join(parts) if parts else "Unknown"


def _fetch_location_uncached() -> tuple[str, str]:
    """Return ``(location_text, gps_text)``; either may be ``"Unknown"``."""
    if sys.platform != "darwin":
        return "Unknown", "Unknown"
    try:
        from CoreLocation import CLGeocoder, CLLocationManager
        from Foundation import NSDate, NSDefaultRunLoopMode, NSRunLoop
    except Exception:
        return "Unknown", "Unknown"

    manager = CLLocationManager.alloc().init()
    manager.startUpdatingLocation()

    deadline = time.time() + _LOCATION_WAIT
    loc = None
    while time.time() < deadline:
        loc = manager.location()
        if loc is not None:
            break
        time.sleep(0.1)
    manager.stopUpdatingLocation()

    if loc is None:
        _debug(
            f"[device_context] no CLLocationManager fix within {_LOCATION_WAIT}s",
            1,
        )
        return "Unknown", "Unknown"

    try:
        coord = loc.coordinate()
        lat, lon = float(coord.latitude), float(coord.longitude)
    except Exception:
        return "Unknown", "Unknown"

    gps_text = f"{lat:.4f}, {lon:.4f}"

    state: dict = {"desc": None, "done": False, "error": None}
    geocoder = CLGeocoder.alloc().init()

    def on_done(placemarks, error) -> None:
        try:
            if placemarks and len(placemarks) > 0:
                state["desc"] = _format_placemark_description(placemarks[0])
            elif error is not None:
                try:
                    state["error"] = str(error.localizedDescription())
                except Exception:
                    state["error"] = str(error)
        finally:
            state["done"] = True

    geocoder.reverseGeocodeLocation_completionHandler_(loc, on_done)

    geocode_deadline = time.time() + _GEOCODE_WAIT
    runloop = NSRunLoop.currentRunLoop()
    while not state["done"] and time.time() < geocode_deadline:
        runloop.runMode_beforeDate_(
            NSDefaultRunLoopMode,
            NSDate.dateWithTimeIntervalSinceNow_(0.1),
        )

    if not state["done"]:
        _debug(
            "[device_context] CLGeocoder reverse geocode timed out before completion "
            f"(lat={lat}, lon={lon}, budget={_GEOCODE_WAIT}s)",
            1,
        )
        return "Unknown", gps_text

    if state["error"]:
        _debug(f"[device_context] CLGeocoder error: {state['error']}", 1)

    return state["desc"] or "Unknown", gps_text


def _cached_location() -> tuple[str, str]:
    global _CACHE_EXPIRES, _CACHE_LOC_TEXT, _CACHE_GPS_TEXT
    now = time.monotonic()
    with _CACHE_LOCK:
        if now < _CACHE_EXPIRES and (_CACHE_LOC_TEXT or _CACHE_GPS_TEXT):
            return _CACHE_LOC_TEXT, _CACHE_GPS_TEXT
    loc_text, gps_text = _fetch_location_uncached()
    with _CACHE_LOCK:
        _CACHE_LOC_TEXT = loc_text
        _CACHE_GPS_TEXT = gps_text
        _CACHE_EXPIRES = time.monotonic() + _TTL_SECONDS
    return loc_text, gps_text


def get_device_context() -> str:
    """Three-line block: current local time, descriptive location, GPS coords."""
    loc_text, gps_text = _cached_location()
    return (
        f"Current time: {_format_time_string()}\n"
        f"Location: {loc_text}\n"
        f"GPS: {gps_text}"
    )
