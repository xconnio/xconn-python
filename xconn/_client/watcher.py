from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, on_change):
        super().__init__()
        self.on_change = on_change

    def on_any_event(self, event):
        if event.src_path.endswith(".py"):
            print(f"Detected change in {event.src_path}")
            self.on_change()


def start_file_watcher(on_change, directory: str = "."):
    observer = Observer()
    handler = FileChangeHandler(on_change)
    observer.schedule(handler, path=directory, recursive=True)
    observer.start()

    return observer
