from app.schemas.common import Schema


class CategoryCreate(Schema):
    name: str


class CategoryUpdate(Schema):
    name: str | None = None


class CategoryRead(CategoryCreate):
    id: int