from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time, os, requests, sys
from datetime import datetime

WATCHED_EXTENSIONS = {'.json', '.csv'}
API_URL = os.getenv('EI_OS_API', 'http://localhost:8000')

class DataFolderHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.last_triggered = 0.0

    def on_created(self, event):
        if event.is_directory:
            return
        ext = os.path.splitext(event.src_path)[1].lower()
        if ext not in WATCHED_EXTENSIONS:
            return

        # Debounce: ignore events within 3 seconds of the last trigger
        now = time.time()
        if now - self.last_triggered < 3.0:
            return
        self.last_triggered = now

        filename = os.path.basename(event.src_path)
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
              f"New file detected: {filename}")
        print("  Triggering ingest pipeline...")
        try:
            res = requests.post(f'{API_URL}/ingest', timeout=30)
            data = res.json()
            edges = data.get('results', {}).get('edges_created', 0)
            print(f"  Done — {edges} new edges created")
        except Exception as e:
            print(f"  Ingest failed: {e}")

    def on_modified(self, event):
        # Treat overwrites the same as new files
        self.on_created(event)


def start(data_dir: str = 'data/'):
    os.makedirs(data_dir, exist_ok=True)
    handler  = DataFolderHandler()
    observer = Observer()
    observer.schedule(handler, data_dir, recursive=False)
    observer.start()
    print(f"EI-OS file watcher started")
    print(f"Watching: {os.path.abspath(data_dir)}")
    print(f"Drop .json or .csv files here to trigger ingestion")
    print(f"Press Ctrl+C to stop\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == '__main__':
    data_dir = sys.argv[1] if len(sys.argv) > 1 else 'data/'
    start(data_dir)
