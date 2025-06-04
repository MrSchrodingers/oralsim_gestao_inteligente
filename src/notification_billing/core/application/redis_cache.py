import contextlib
import functools
import pickle
from collections.abc import Callable
from typing import Any

from redis import Redis

Serializer = Callable[[Any], bytes]
Deserializer = Callable[[bytes], Any]

def cached_query(
    ttl_seconds: int,
    key_fn: Callable[[Any], str] | None = None,
    serializer: Serializer | None = None,
    deserializer: Deserializer | None = None,
):
    """
    Decorator para QueryHandler.handle:
      - tenta carregar do Redis antes de chamar o handler original
      - se não existir, executa, armazena no cache e retorna

    :param ttl_seconds: tempo de vida em cache
    :param key_fn: função que recebe a query e retorna uma string de chave
    :param serializer: converte resultado em bytes (default: pickle.dumps)
    :param deserializer: converte bytes de volta em objeto (default: pickle.loads)
    """
    serializer = serializer or pickle.dumps
    deserializer = deserializer or pickle.loads

    def decorator(handle_fn):
        @functools.wraps(handle_fn)
        def wrapped(self, query):
            from django.conf import settings

            from notification_billing.adapters.config.composition_root import setup_di_container_from_settings
            
            setup_di_container_from_settings(settings)
            
            from notification_billing.adapters.config.composition_root import container
            
            redis: Redis = container.redis_client()
            key = key_fn(query) if key_fn else f"{query.__class__.__name__}:{pickle.dumps(query)}"
            raw = redis.get(key)
            if raw is not None:
                try:
                    return deserializer(raw)
                except Exception:
                    redis.delete(key)

            result = handle_fn(self, query)
            with contextlib.suppress(Exception):
                redis.setex(key, ttl_seconds, serializer(result))
            return result
        return wrapped
    return decorator
