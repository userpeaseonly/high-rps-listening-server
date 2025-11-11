from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass

class StatusCode(int, Enum):
    OK = 1
    DEVICE_BUSY = 2
    DEVICE_ERROR = 3
    INVALID_OPERATION = 4
    INVALID_MESSAGE_FORMAT = 5
    INVALID_MESSAGE_CONTENT = 6
    REBOOT_REQUIRED = 7

@dataclass(frozen=True)
class SubStatus:
    error_code: str
    description: str

STATUS_CODES: Dict[StatusCode, Dict[str, SubStatus]] = {
    StatusCode.OK: {
        "ok": SubStatus("0x1", "Operation completed."),
        "riskPassword": SubStatus("0x10000002", "Risky password."),
    },
    StatusCode.DEVICE_BUSY: {
        "noMemory": SubStatus("0x20000001", "Insufficient memory."),
        "upgrading": SubStatus("0x20000003", "Upgrading."),
        "networkError": SubStatus("0x20000009", "Network error."),
    },
    StatusCode.DEVICE_ERROR: {
        "deviceError": SubStatus("0x30000001", "Device hardware error."),
        "createSocketError": SubStatus("0x30000004", "Creating socket failed."),
        "sendRequestError": SubStatus("0x30000006", "Sending request failed."),
        "passwordDecodeError": SubStatus("0x30000008", "Decrypting password failed."),
        "passwordEncryptError": SubStatus("0x30000009", "Encrypting password failed."),
        "pictureUploadFailed": SubStatus("0x3000000B", "Uploading picture failed."),
        "connectDatabaseError": SubStatus("0x3000000E", "Connecting to database failed."),
        "internalError": SubStatus("0x30000014", "Internal error."),
        "uninitialized": SubStatus("0x3000000C", "Uninitialized."),
    },
    StatusCode.INVALID_OPERATION: {
        "notSupport": SubStatus("0x40000001", "Not supported."),
        "lowPrivilege": SubStatus("0x40000002", "No permission."),
        "badAuthorization": SubStatus("0x40000003", "Authentication failed."),
        "methodNotAllowed": SubStatus("0x40000004", "Invalid HTTP method."),
        "notActivated": SubStatus("0x40000007", "Inactivated."),
        "hasActivated": SubStatus("0x40000008", "Activated."),
        "invalidContent": SubStatus("0x4000000A", "Invalid message content."),
        "maxSessionUserLink": SubStatus("0x4000000B", "No more user can log in."),
        "loginPasswordError": SubStatus("0x4000000C", "Incorrect password."),
        "MgmtLockedError": SubStatus("0x4000000D", "Logging in management platform failed. IP is locked."),
        # (additional entries omitted for brevity, add as needed)
    },
    StatusCode.INVALID_MESSAGE_FORMAT: {
        "badJsonFormat": SubStatus("0x50000002", "Invalid JSON format."),
        "badURLFormat": SubStatus("0x50000003", "Invalid URL format."),
    },
    StatusCode.INVALID_MESSAGE_CONTENT: {
        "badParameters": SubStatus("0x60000001", "Incorrect parameter."),
        "badXmlContent": SubStatus("0x60000003", "Incorrect XML message content."),
        "badPort": SubStatus("0x6000000B", "Port number conflicted."),
        "portError": SubStatus("0x6000000C", "Invalid port number."),
        "badVersion": SubStatus("0x6000000F", "Version mismatches."),
        "requestMemoryNULL": SubStatus("0x6000003F", "No memory is requested."),
        "tokenTimeout": SubStatus("0x60000040", "The token timed out."),
        "passwordLenNoMoreThan16": SubStatus("0x6000005F", "Up to 16 characters are allowed in the password."),
        "eventCodeExist": SubStatus("0x60000060", "The event code already exists."),
        "diskError": SubStatus("0x60001009", "HDD error."),
    },
    StatusCode.REBOOT_REQUIRED: {
        "rebootRequired": SubStatus("0x70000001", "Reboot device to take effect."),
    }
}

def get_status_description(status_code: StatusCode, sub_status_name: str) -> Optional[str]:
    """Retrieve the description for a given status and substatus."""
    sub_status = STATUS_CODES.get(status_code, {}).get(sub_status_name)
    return sub_status.description if sub_status else None
