from typing import Generic, TypeVar

T = TypeVar("T")


class ServiceResult(Generic[T]):

    def __init__(
        self,
        success: bool,
        message: str,
        data: T | None = None
    ):
        self.success = success
        self.message = message
        self.data = data

    @classmethod
    def Success(cls, message: str, data=None):
        return cls(
            success=True,
            message=message,
            data=data
        )

    @classmethod
    def Failure(cls, message: str):
        return cls(
            success=False,
            message=message,
            data=None
        )