from enum import Enum

class PacketType(Enum):
    REQUEST_RESEND = 0
    DATA_RECEIVED = 1
    ACTIVITY_CHECK = 2
    ACTIVITY_CONFIRMATION = 3
