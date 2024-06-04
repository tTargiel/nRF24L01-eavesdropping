def is_key_event_packet(payload: list[int]) -> bool:
    # Microsoft's key event packet (not idle) always satisfies condition below
    return payload[0] == 0x0a and payload[1] == 0x78 and len(payload) > 8
