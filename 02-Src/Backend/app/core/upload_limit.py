from .errors import error_payload


class UploadSizeLimitMiddleware:
    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = next(
            (value for name, value in scope.get("headers", ()) if name.lower() == b"content-length"),
            None,
        )
        if content_length is not None and int(content_length) > self.max_bytes:
            await self._too_large(scope, receive, send)
            return

        received_bytes = 0
        response_started = False

        async def limited_receive():
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_bytes:
                    raise UploadTooLarge
            return message

        async def tracked_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except UploadTooLarge:
            if not response_started:
                await self._too_large(scope, receive, send)

    async def _too_large(self, scope, receive, send):
        from starlette.responses import JSONResponse

        response = JSONResponse(
            status_code=413,
            content=error_payload("HTTP_413", "El archivo supera el tamaño máximo permitido."),
        )
        await response(scope, receive, send)


class UploadTooLarge(Exception):
    pass