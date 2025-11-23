from enum import Enum

class PacketType(Enum):
    DATA_RECEIVED = 0
    REQUEST_RESEND = 1
    INVALID_TOKEN = 2
    ACTIVITY_CHECK = 3
