def is_key_event_packet(payload: list[int]) -> bool:
    return payload[0] == 0xa and payload[1] == 0x78 and len(payload) > 8