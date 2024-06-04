from typing import Any

import nrf24


class NRF24Wrapper:
    __nrf: nrf24.NRF24

    # Create an instance of NRF24Wrapper with the following parameters:
    # - pi: Raspberry Pi object
    # - ce: GPIO pin connected to the CE pin of the NRF24 module
    # - payload_size: maximum payload size in bytes
    # - channel: RF channel to use for communication
    # - data_rate: data rate for communication
    # - pa_level: power amplifier level for transmission
    def __init__(
        self,
        pi,
        ce: int,
        payload_size: int = 32,
        channel: int = 3,
        data_rate: int = 2,
        pa_level: int = 0
    ):
        self.__nrf = nrf24.NRF24(
            pi,
            ce=ce,
            payload_size=payload_size,
            channel=channel,
            data_rate=data_rate,
            pa_level=pa_level
        )

    # Define own function to set MAC address width, bypassing the one defined in py-nrf24 library
    def set_address_bytes(self, address_bytes: int):
        # Allow to set illegal width option of 2 bytes
        assert (
            address_bytes == 2 or 3 <= address_bytes <= 5
        ), "Address must be 2 or between 3 and 5 bytes wide"

        self.__nrf._address_width = address_bytes

        self.__nrf.unset_ce()
        self.__nrf._nrf_write_reg(
            nrf24.NRF24.SETUP_AW, self.__nrf._address_width - 2)
        self.__nrf.set_ce()

    def set_auto_ack(self, enable: bool):
        self.__nrf.unset_ce()
        self.__nrf._nrf_write_reg(nrf24.NRF24.EN_AA, 0x3f if enable else 0x00)
        self.__nrf.set_ce()

    def reset_rx_address(self):
        self.__nrf.unset_ce()
        self.__nrf._nrf_write_reg(self.__nrf.EN_RXADDR, 0)
        self.__nrf.set_ce()

    def enable_crc(self):
        self.__nrf.enable_crc()

    def set_address(self, pipe, address):
        self.__nrf.unset_ce()
        self.__nrf._nrf_write_reg(pipe, address)
        self.__nrf.set_ce()

    def clear_rx_dr_ts_ds(self):
        self.__nrf.unset_ce()
        self.__nrf._nrf_write_reg(0x07, [0, 0, 0, 0, 0, 1, 1, 0])
        self.__nrf.set_ce()

    def set_status(self):
        self.__nrf.unset_ce()
        self.__nrf._nrf_write_reg(0x07, 0x0e)
        self.__nrf.set_ce()

    def disable_crc(self):
        self.__nrf.disable_crc()

    def set_payload_size(self, payload_size: int):
        self.__nrf.set_payload_size(payload_size)

    def set_data_rate(self, data_rate: int):
        self.__nrf.set_data_rate(data_rate)

    def set_pa_level(self, pa_level: int):
        self.__nrf.set_pa_level(pa_level)

    def set_channel(self, channel: int):
        self.__nrf.set_channel(channel)

    def show_registers(self):
        self.__nrf.show_registers()

    def get_payload(self):
        return self.__nrf.get_payload()

    def flush_rx(self):
        self.__nrf.flush_rx()

    def flush_tx(self):
        self.__nrf.flush_tx()

    def data_ready(self):
        return self.__nrf.data_ready()

    def power_down(self):
        self.__nrf.power_down()

    def power_up(self):
        self.__nrf.unset_ce()
        self.__nrf._nrf_write_reg(0x00, 0x07)
        self.__nrf.set_ce()

    def close_reading_pipe(self, pipe: int):
        self.__nrf.close_reading_pipe(pipe)

    def open_reading_pipe(
        self,
        pipe: int,
        address: Any,
        size=None,
        auto_ack=True
    ):
        # Validate pipe input.
        if not (isinstance(pipe, int) or isinstance(pipe, nrf24.RF24_RX_ADDR)):
            raise ValueError(f"pipe must be int or RF24_RX_ADDR enum.")

        # If a pipe is given as 0..5 add the 0x0a value corresponding to
        # RX_ADDR_P0
        if 0 <= pipe <= 5:
            pipe = pipe + nrf24.NRF24.RX_ADDR_P0

        if pipe < nrf24.NRF24.RX_ADDR_P0 or pipe > nrf24.NRF24.RX_ADDR_P5:
            raise ValueError(
                f"pipe out of range ({nrf24.NRF24.RX_ADDR_P0:02x} <= pipe <= "
                f"and "
                f"{nrf24.NRF24.RX_ADDR_P5:02x})."
            )

        # Adjust address.
        addr = self.__nrf.make_address(address)
        assert len(addr) == self.__nrf._address_width, (
            f"Invalid address length {len(addr)} of " f"address {address} ({addr})."
        )

        # If the address is greater that RF24_RX_ADDR.P1, we use only the
        # first byte of the address.
        if pipe > nrf24.RF24_RX_ADDR.P1:
            addr = addr[:1]

        self.__nrf.unset_ce()
        self._open_reading_pipe(pipe, addr, size, auto_ack)
        self.__nrf.set_ce()

    def _open_reading_pipe(
        self,
        pipe,
        address,
        size=None,
        auto_ack=True
    ):
        # If no payload size is specified, use the default one.
        if not size:
            size = self.__nrf._payload_size
        else:
            # If a payload size is specified, verify that it is within valid
            # range.
            assert nrf24.RF24_PAYLOAD.ACK <= size <= nrf24.RF24_PAYLOAD.MAX, (
                "Payload size must be between RF24_PAYLOAD.ACK and " "RF24_PAYLOAD.MAX"
            )

        en_rxaddr = self.__nrf._nrf_read_reg(nrf24.NRF24.EN_RXADDR, 1)[
            0
        ]  # Get currently enabled pipes.
        dynpd = self.__nrf._nrf_read_reg(nrf24.NRF24.DYNPD, 1)[
            0
        ]  # Get currently enabled dynamic payload.
        en_aa = self.__nrf._nrf_read_reg(nrf24.NRF24.EN_AA, 1)[
            0
        ]  # Get currently enabled auto-acknowledgement.

        # Calculate "enable" value
        enable = 1 << (pipe - nrf24.NRF24.RX_ADDR_P0)
        disable = ~enable & 0xFF  # Calculate "disable" mask.

        if nrf24.RF24_PAYLOAD.MIN <= size <= nrf24.RF24_PAYLOAD.MAX:
            # Static payload size.
            self.__nrf._nrf_write_reg(
                nrf24.NRF24.DYNPD, dynpd & disable
            )  # Disable dynamic payload.
            self.__nrf._nrf_write_reg(
                nrf24.NRF24.FEATURE, 0
            )  # Disable dynamic payload.
            self.__nrf._nrf_write_reg(
                nrf24.NRF24.RX_PW_P0 + (pipe - nrf24.NRF24.RX_ADDR_P0), size
            )  # Set size of payload.
        elif size == nrf24.RF24_PAYLOAD.DYNAMIC or nrf24.RF24_PAYLOAD.ACK:
            # Dynamic payload size / dynamic payload size with
            # acknowledgement payload.
            self.__nrf._nrf_write_reg(
                nrf24.NRF24.RX_PW_P0 + (pipe - nrf24.NRF24.RX_ADDR_P0), 0
            )  # Set size of payload to 0.
            self.__nrf._nrf_write_reg(
                nrf24.NRF24.DYNPD, dynpd | enable
            )  # Enable dynamic payload.
            if size == nrf24.RF24_PAYLOAD.DYNAMIC:
                self.__nrf._nrf_write_reg(
                    nrf24.NRF24.FEATURE, nrf24.NRF24.EN_DPL
                )  # Enable dynamic payload.
            else:
                self.__nrf._nrf_write_reg(
                    nrf24.NRF24.FEATURE, nrf24.NRF24.EN_DPL | nrf24.NRF24.EN_ACK_PAY
                )  # Enable dynamic payload and acknowledgement payload feature.

        self.__nrf._nrf_write_reg(pipe, address)  # Set address for pipe.
        self.__nrf._nrf_write_reg(
            nrf24.NRF24.EN_AA, en_aa | enable if auto_ack else en_aa & disable
        )  # Enable auto-acknowledgement.
        self.__nrf._nrf_write_reg(
            nrf24.NRF24.EN_RXADDR, en_rxaddr | enable
        )  # Enable reception on pipe.
