class AppException(Exception):

    def __init__(
        self,
        message: str,
        status_code: int = 400
    ):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundException(AppException):

    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=404
        )


class BadRequestException(AppException):

    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=400
        )


class UnauthorizedException(AppException):

    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=401
        )


class ConflictException(AppException):

    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=409
        )