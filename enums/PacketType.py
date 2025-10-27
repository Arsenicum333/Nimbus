from enum import Enum

class PacketType(Enum):
    REQUEST_RESEND = 0
    DATA_RECEIVED = 1
