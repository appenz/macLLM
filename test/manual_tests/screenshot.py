import Quartz


def list_windows():
    # visible windows only
    options = Quartz.kCGWindowListOptionOnScreenOnly
    window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
    return [(w['kCGWindowNumber'], w.get('kCGWindowName', '')) for w in window_list if w.get('kCGWindowName')]


if __name__ == "__main__":
    for win_id, title in list_windows():
        print(f"{win_id}: {title}")

