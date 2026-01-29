import Quartz
from AppKit import NSRunningApplication


def get_app_info_from_pid(pid):
    """Get application info from PID using NSRunningApplication."""
    try:
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        if app:
            return {
                'bundle_id': app.bundleIdentifier(),
                'bundle_url': str(app.bundleURL()) if app.bundleURL() else None,
                'executable_url': str(app.executableURL()) if app.executableURL() else None,
                'localized_name': app.localizedName(),
            }
    except Exception as e:
        return {'error': str(e)}
    return None


def list_windows():
    # visible windows only
    options = Quartz.kCGWindowListOptionOnScreenOnly
    window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
    return list(window_list)


if __name__ == "__main__":
    windows = list_windows()
    
    # First, show all available keys from the first window with a name
    print("=" * 60)
    print("AVAILABLE KEYS IN WINDOW INFO:")
    print("=" * 60)
    for w in windows:
        if w.get('kCGWindowName'):
            for key in sorted(w.keys()):
                value = w[key]
                print(f"  {key}: {value}")
            break
    
    print("\n" + "=" * 60)
    print("APP-LEVEL WINDOWS (Layer 0, normal apps):")
    print("=" * 60)
    
    # Cache PID lookups
    pid_cache = {}
    
    for w in windows:
        name = w.get('kCGWindowName', '')
        layer = w.get('kCGWindowLayer', -1)
        
        # Only show normal app windows (layer 0) with names
        if name and layer == 0:
            win_id = w.get('kCGWindowNumber', '?')
            owner = w.get('kCGWindowOwnerName', '?')
            owner_pid = w.get('kCGWindowOwnerPID', 0)
            bounds = w.get('kCGWindowBounds', {})
            memory = w.get('kCGWindowMemoryUsage', 0)
            
            # Get app info from PID
            if owner_pid not in pid_cache:
                pid_cache[owner_pid] = get_app_info_from_pid(owner_pid)
            app_info = pid_cache[owner_pid]
            
            print(f"\n  Window #{win_id}: {name}")
            print(f"    Owner: {owner} (PID: {owner_pid})")
            print(f"    Size: {bounds.get('Width', '?')}x{bounds.get('Height', '?')} at ({bounds.get('X', '?')}, {bounds.get('Y', '?')})")
            print(f"    Memory: {memory / 1024:.1f} KB")
            
            if app_info:
                print(f"    Bundle ID: {app_info.get('bundle_id', 'N/A')}")
                print(f"    Executable: {app_info.get('executable_url', 'N/A')}")

