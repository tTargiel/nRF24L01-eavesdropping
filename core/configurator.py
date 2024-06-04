import nrf24
import pigpio

from core.nrf_wrapper import NRF24Wrapper


class NRFConfigurator:
    @staticmethod
    def configure_for_mac_cracking(pi, power: int):
        # Keyboard MAC address is known to start with 0xcd byte, thus preamble has to alternate
        addr = b'\xaa\x00'

        nrf = NRF24Wrapper(
            pi,
            ce=25,
            payload_size=32,
            channel=3,
            data_rate=nrf24.RF24_DATA_RATE.RATE_2MBPS,
            pa_level=power
        )

        # Device resetting sequence below, source: https://devzone.nordicsemi.com/f/nordic-q-a/1894/is-there-any-way-to-reset-nrf24l01
        nrf.power_down()
        nrf.clear_rx_dr_ts_ds()
        nrf.flush_rx()
        nrf.flush_tx()
        nrf.set_status()
        nrf.power_up()

        # Set MAC address to the reset value
        nrf.set_address(nrf24.RF24_RX_ADDR.P0, [0, 0, 0, 0, 0])
        nrf.set_address_bytes(2)  # Set address width to the illegal option
        nrf.flush_rx()
        # Open reading pipe with MAC address mismatched to the preamble value
        nrf.open_reading_pipe(
            nrf24.RF24_RX_ADDR.P0,
            address=addr
        )
        nrf.disable_crc()
        nrf.set_auto_ack(False)
        nrf.show_registers()

        return nrf

    @staticmethod
    def configure_for_sniffing(pi, mac_address: str, chan: int, gpio_interrupt, power: int):
        # Convert MAC address to the integer (according to the requirements)
        usable_mac = [
            int(x, 16) for x in mac_address.split(":")
        ]

        print(usable_mac)

        # Set up a callback function for GPIO pin 24, triggered on falling edge, with the provided interrupt handler
        pi.callback(24, pigpio.FALLING_EDGE, gpio_interrupt)

        nrf = NRF24Wrapper(
            pi,
            ce=25,
            payload_size=nrf24.RF24_PAYLOAD.DYNAMIC,
            channel=chan,
            data_rate=nrf24.RF24_DATA_RATE.RATE_2MBPS,
            pa_level=power
        )

        # Open reading pipe with previously leaked MAC address
        nrf.open_reading_pipe(nrf24.RF24_RX_ADDR.P0, address=usable_mac)
        nrf.enable_crc()
        nrf.set_auto_ack(False)
        nrf.show_registers()

        return nrf
