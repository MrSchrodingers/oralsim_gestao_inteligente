class EventDispatcher:
    """Very-simple sync dispatcher; plug a proper bus later."""
    def __init__(self):
        self._listeners = {}

    def subscribe(self, evt_cls, fn):
        self._listeners.setdefault(evt_cls, []).append(fn)

    def dispatch(self, event):
        for fn in self._listeners.get(type(event), []):
            fn(event)
