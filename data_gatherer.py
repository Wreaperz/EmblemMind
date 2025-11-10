import time
import threading
from emblemmind_snapshot import TurnSnapshot
import os

# Paths
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
STATE_FILE = os.path.join(DATA_DIR, 'fe_state.txt')
MAP_FILE = os.path.join(DATA_DIR, 'fe_map.txt')

class DataGatherer:
    def __init__(self):
        self.snapshot = None
        self.cursor_position = None
        self.realtime_move_dest = (None, None)
        self.lock = threading.Lock()
        self.running = True
        self.thread = threading.Thread(target=self._gather_data)
        self.thread.start()

    def _gather_data(self):
        while self.running:
            with self.lock:
                try:
                    self.snapshot = TurnSnapshot.from_files(STATE_FILE, MAP_FILE)
                    self.cursor_position = self.snapshot.cursor_position
                    self.realtime_move_dest = self._get_realtime_move_dest()
                except Exception as e:
                    print(f"[ERROR] Data gathering failed: {e}")
            time.sleep(0.1)  # Adjust the frequency as needed

    def stop(self):
        self.running = False
        self.thread.join()

    def _get_realtime_move_dest(self):
        try:
            with open(STATE_FILE, 'r') as f:
                lines = f.readlines()
            in_realtime = False
            data = {}
            for line in lines:
                line = line.strip()
                if line == 'REALTIME_DATA':
                    in_realtime = True
                    continue
                if in_realtime:
                    if not line or (line.replace('_', '').isupper() and line.replace('_', '').isalpha()) or line.startswith('character='):
                        break
                    if '=' in line:
                        k, v = line.split('=', 1)
                        try:
                            data[k] = int(v)
                        except ValueError:
                            continue
            return data.get('move_dest_x'), data.get('move_dest_y')
        except Exception as e:
            print(f"[ERROR] Failed to read REALTIME_DATA: {e}")
            return None, None

    def get_snapshot(self):
        with self.lock:
            return self.snapshot

    def get_cursor_position(self):
        with self.lock:
            return self.cursor_position

    def get_realtime_move_dest(self):
        with self.lock:
            return self.realtime_move_dest

    def parse_map_section(self, section_name):
        with open(STATE_FILE, 'r') as f:
            lines = f.readlines()
        in_section = False
        grid = []
        for line in lines:
            line = line.strip()
            if line == section_name:
                in_section = True
                continue
            if in_section:
                if not line or (line.replace('_', '').isupper() and line.replace('_', '').isalpha()):
                    break
                if not all(all(c in "0123456789ABCDEFabcdef" for c in b) for b in line.split()):
                    break
                row = [int(b, 16) for b in line.split()]
                grid.append(row)
        return grid

# Example usage
# data_gatherer = DataGatherer()
# ... use data_gatherer.get_snapshot(), etc. ...
# data_gatherer.stop()