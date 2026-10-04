from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


def _null_as_empty_list(value):
    return [] if value is None else value


class RoomGroup(BaseModel):
    group_id: int
    group_name: str | None = None
    can_book_unconfirmed: bool | None = None


class RoomCategory(BaseModel):
    category_id: int
    category_name: str | None = None
    min_days: int | None = None
    max_days: int | None = None


class Room(BaseModel):
    room_id: int
    room_name: str | None = None
    room_number: str | None = None
    category: RoomCategory | None = None
    group: RoomGroup | None = None
    building_id: int | None = None
    address: str | None = None
    area: str | None = None
    floor: str | None = None
    min_cap: int | None = None
    max_cap: int | None = None
    min_booking_days: int | None = None
    max_booking_days: int | None = None
    equipment: list = Field(default_factory=list)
    photo_link: str | None = None

    _equipment_default = field_validator("equipment", mode="before")(_null_as_empty_list)


class BookingStatus(BaseModel):
    status_id: int
    status_name: str | None = None


class BookingRoom(BaseModel):
    room_id: int
    room_name: str | None = None
    room_number: str | None = None
    address: str | None = None
    min_booking_days: int | None = None
    max_booking_days: int | None = None


class Booking(BaseModel):
    booking_id: int
    start_datetime: str | None = None
    end_datetime: str | None = None
    name: str | None = None
    participants: int | None = None
    owner_isu: int | None = None
    owner_fio: str | None = None
    contact_phone: str | None = None
    room: BookingRoom | None = None
    status: BookingStatus | None = None
    equipment: list = Field(default_factory=list)
    co_bookers: list = Field(default_factory=list)
    created_at: str | None = None

    _lists_default = field_validator("equipment", "co_bookers", mode="before")(
        _null_as_empty_list
    )


class BusyInterval(BaseModel):
    """An existing booking of a room; `status` may arrive as a bare id or an object."""

    start_datetime: str | None = None
    end_datetime: str | None = None
    status_id: int | None = None
    status_name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _flatten_status(cls, raw):
        if not isinstance(raw, dict) or "status" not in raw:
            return raw
        status = raw["status"]
        flat = {k: raw.get(k) for k in ("start_datetime", "end_datetime")}
        if isinstance(status, dict):
            flat["status_id"] = status.get("status_id")
            flat["status_name"] = status.get("status_name")
        else:
            flat["status_id"] = status
        return flat


class RoomAvailability(BaseModel):
    """A room with its existing (busy) bookings for one day, sorted by start time."""

    room_id: int
    room_name: str | None = None
    room_number: str | None = None
    address: str | None = None
    busy: list[BusyInterval] = Field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict) -> RoomAvailability:
        intervals = sorted(
            (BusyInterval.model_validate(item) for item in raw.get("bookings") or []),
            key=lambda interval: interval.start_datetime or "",
        )
        return cls(
            room_id=raw["room_id"],
            room_name=raw.get("room_name"),
            room_number=raw.get("room_number"),
            address=raw.get("address"),
            busy=intervals,
        )
