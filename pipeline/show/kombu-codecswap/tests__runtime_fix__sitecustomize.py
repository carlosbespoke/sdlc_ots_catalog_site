# Verifier-owned runtime fix: honours the declared content_encoding when a str body is published and
# when a text body without a registered decoder is loaded. Every repository file stays byte-identical
# to the buggy tree; the corrected callables are installed after import.
try:
    import codecs
    import types

    import kombu.message as _message
    import kombu.messaging as _messaging
    import kombu.serialization as _serialization

    _original_prepare = _messaging.Producer._prepare

    def _prepare(self, body, serializer=None, content_type=None,
                 content_encoding=None, compression=None, headers=None):
        if content_type and isinstance(body, str):
            content_encoding = content_encoding or 'utf-8'
            body = codecs.encode(body, content_encoding)
        return _original_prepare(self, body, serializer, content_type,
                                 content_encoding, compression, headers)

    _messaging.Producer._prepare = _prepare

    _registry = _serialization.registry
    _original_loads = _serialization.SerializerRegistry.loads

    def _loads(self, data, content_type, content_encoding, accept=None, force=False,
               _trusted_content=_serialization.TRUSTED_CONTENT):
        ctype = (_serialization.bytes_to_str(content_type) if content_type
                 else 'application/data')
        encoding = (content_encoding or 'utf-8').lower()
        if (data and not isinstance(data, str) and not self._decoders.get(ctype)
                and encoding not in _serialization.SKIP_DECODE):
            # same accept / disabled checks as the original, on an empty body
            _original_loads(self, b'', content_type, content_encoding, accept, force,
                            _trusted_content)
            try:
                return codecs.decode(data, encoding)
            except Exception as exc:
                raise _serialization.DecodeError(exc)
        return _original_loads(self, data, content_type, content_encoding, accept, force,
                               _trusted_content)

    _serialization.SerializerRegistry.loads = _loads
    _registry.loads = types.MethodType(_loads, _registry)
    _serialization.loads = _registry.loads
    _message.loads = _registry.loads
except Exception:  # the tree may not be importable at all
    pass
