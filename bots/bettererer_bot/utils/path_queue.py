from collections import deque

class PathQueue:
    def __init__(self, items: list):
        self._deque = deque(items)
        self._set = set(items)

    def popleft(self):
        item = self._deque.popleft()
        self._set.discard(item)
        return item

    def __contains__(self, item):
        return item in self._set

    def __getitem__(self, idx):
        return self._deque[idx]

    def __bool__(self):
        return bool(self._deque)

    def __len__(self):
        return len(self._deque)