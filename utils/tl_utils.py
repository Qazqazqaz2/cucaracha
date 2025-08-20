from telethon.tl.tlobject import TLRequest
from telethon.extensions import BinaryReader
from typing import Optional

class _TLWriter:
    """Minimal TL binary writer for the specific fields we need (int, long, string)."""
    def __init__(self):
        self._buf = bytearray()

    def write_int(self, value: int, signed: bool = True):
        # TL uses little-endian 32-bit integers
        self._buf += int(value).to_bytes(4, byteorder="little", signed=signed)

    def write_long(self, value: int, signed: bool = True):
        # TL uses little-endian 64-bit integers
        self._buf += int(value).to_bytes(8, byteorder="little", signed=signed)

    def write_string(self, s: Optional[str]):
        if s is None:
            # Should not be called with None when field not present
            s = ""
        data = s.encode("utf-8")
        l = len(data)
        if l < 254:
            self._buf += bytes([l]) + data
            # pad to 4-byte boundary
            pad = (4 - ((1 + l) % 4)) % 4
            self._buf += b"\x00" * pad
        else:
            self._buf += bytes([254])
            self._buf += (l & 0xFF).to_bytes(1, "little")
            self._buf += ((l >> 8) & 0xFF).to_bytes(1, "little")
            self._buf += ((l >> 16) & 0xFF).to_bytes(1, "little")
            self._buf += data
            pad = (4 - (l % 4)) % 4
            self._buf += b"\x00" * pad

    def get_bytes(self) -> bytes:
        return bytes(self._buf)

class _RawGetStarGifts(TLRequest):
    """
    Ручная реализация TL-запроса payments.getStarGifts#c4563590
    Result: payments.StarGifts
    """
    CONSTRUCTOR_ID = 0xC4563590  # payments.getStarGifts

    def __init__(self, hash: int = 0):
        self.hash = hash

    def write(self) -> bytes:
        w = _TLWriter()
        # constructor id
        w.write_int(self.CONSTRUCTOR_ID, signed=False)
        w.write_int(self.hash)
        return w.get_bytes()

    # Telethon will call read_result to parse the response payload
    @staticmethod
    def read_result(reader: BinaryReader):
        # Read the constructor ID for payments.StarGifts
        cid = reader.read_int(signed=False)
        if cid == 0xA388A368:  # starGiftsNotModified
            return []
        if cid != 0x901689EA:  # starGifts
            raise ValueError(f"Unexpected constructor id for payments.StarGifts: {hex(cid)}")
        hash_ = reader.read_int()
        # Vector<StarGift>
        vector_id = reader.read_int(signed=False)
        if vector_id != 0x1CB5C415:
            raise ValueError("Expected Vector constructor for StarGift list")
        count = reader.read_int()
        results = []
        for _ in range(count):
            # StarGift constructor id
            item_cid = reader.read_int(signed=False)
            if item_cid != 0x49C577CD:
                raise ValueError(f"Unexpected constructor id for StarGift: {hex(item_cid)}")
            flags = reader.read_int()
            limited = bool(flags & (1 << 0))
            sold_out = bool(flags & (1 << 1))
            birthday = bool(flags & (1 << 2))
            id_ = reader.read_long()
            # sticker: Document
            sticker = reader.read_object()  # Parse Document
            stars = reader.read_long()
            if limited:
                availability_remains = reader.read_int()
                availability_total = reader.read_int()
            else:
                availability_remains = 999999
                availability_total = 999999
            convert_stars = reader.read_long()
            if sold_out:
                availability_remains = 0
                first_sale_date = reader.read_int()
                last_sale_date = reader.read_int()
            results.append({
                "id": int(id_),
                "stars": int(stars),
                "store_product": None,  # Not present
                "currency": "XTR",
                "amount": int(stars),
                "remaining": availability_remains,
                "limited": limited,
                "sold_out": sold_out,
            })
        return results