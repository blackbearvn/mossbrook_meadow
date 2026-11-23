"""One request-driven line reader for blocking menus and timed auto controls.

Reading text in the worker also consumes lines already buffered by input().
The main thread only waits on a queue, so a partial line never stops ticks.
No new read starts until the consumer requests one, preserving manual input
after automation completes and avoiding unsolicited reads from input mocks.
"""
import builtins
from queue import Empty, Full, Queue
from threading import Event, Thread


class LineInput:
    def __init__(self):
        self._requests = Queue(maxsize=1)
        self._results = Queue(maxsize=1)
        self._closed = Event()
        self._thread = None
        self._pending = False

    def _read_lines(self):
        while not self._closed.is_set():
            read_line = self._requests.get()
            if read_line is None:
                return
            try:
                result = read_line(), None
            except BaseException as error:
                result = None, error
            self._results.put(result)

    def read(self, prompt='', *, timeout=None):
        """Return a complete line, None on timeout, or propagate EOF/interrupt.

        A timed-out read stays pending and is shared with the next call,
        including a blocking menu read after auto's final tick.
        """
        if self._closed.is_set():
            raise ValueError('The line reader is closed')
        if prompt:
            print(prompt, end='', flush=True)
        if not self._pending:
            if self._thread is None:
                self._thread = Thread(target=self._read_lines, name='farm-input', daemon=True)
                self._thread.start()
            # Capture the current callable so normal builtins.input test doubles
            # have the same line/EOF behavior without reading ahead indefinitely.
            self._requests.put(builtins.input)
            self._pending = True
        try:
            value, error = self._results.get(timeout=timeout)
        except Empty:
            return None
        self._pending = False
        if error is not None:
            raise error
        return value

    def close(self):
        """Stop idle input work; an outstanding read cannot block shutdown."""
        self._closed.set()
        if self._thread is not None:
            try:
                self._requests.put_nowait(None)
            except Full:
                pass
