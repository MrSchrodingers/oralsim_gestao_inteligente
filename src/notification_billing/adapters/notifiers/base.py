import time
from abc import ABC, abstractmethod
from http import HTTPStatus

import backoff
import httpx
import structlog
from prometheus_client import Counter, Histogram

logger = structlog.get_logger()

REQ_LATENCY = Histogram("notifier_request_seconds", "Latency", ["provider","channel"])
REQ_SUCCESS = Counter  ("notifier_success_total",   "Success", ["provider","channel"])
REQ_FAILURE = Counter  ("notifier_failure_total",   "Failure", ["provider","channel"])

class BaseNotifier(ABC):
    DEFAULT_TIMEOUT = 10

    def __init__(self, provider: str, channel: str) -> None:
        self.provider = provider
        self.channel  = channel

    @backoff.on_exception(backoff.expo, (httpx.TimeoutException, httpx.HTTPError),
                          max_tries=3, jitter=None)
    def _request(self, method: str, url: str, **kw) -> httpx.Response:
        start = time.perf_counter()
        try:
            resp = httpx.request(method, url, timeout=self.DEFAULT_TIMEOUT, **kw)
            if resp.status_code >= HTTPStatus.BAD_REQUEST:
                raise httpx.HTTPStatusError("Bad status", request=resp.request, response=resp)
            REQ_SUCCESS.labels(self.provider, self.channel).inc()
            return resp
        except Exception:
            REQ_FAILURE.labels(self.provider, self.channel).inc()
            raise
        finally:
            REQ_LATENCY.labels(self.provider, self.channel).observe(time.perf_counter() - start)

    @abstractmethod
    def send(self, *args, **kwargs) -> None:
        """Envia uma notificação. Assinatura varia por canal."""
        ...
