import nrf24
import pigpio

from nrf_wrapper import NRF24Wrapper


class NRFConfigurator:
    @staticmethod
    def configure_for_mac_cracking(pi):
        addr = b'\xAA\x00'

        nrf = NRF24Wrapper(
            pi,
            ce=25,
            payload_size=32,
            channel=3,
            data_rate=nrf24.RF24_DATA_RATE.RATE_2MBPS,
            pa_level=nrf24.RF24_PA.MIN)

        # poniżej sekwencja resetująca urządzenie https://devzone.nordicsemi.com/f/nordic-q-a/1894/is-there-any-way-to-reset-nrf24l01
        nrf.power_down()
        nrf.clear_rx_dr_ts_ds()
        nrf.flush_rx()
        nrf.flush_tx()
        nrf.set_status()
        nrf.power_up()
        
        # nrf.set_auto_ack(False)
        # nrf.set_pa_level(nrf24.RF24_PA.MIN)
        # nrf.set_data_rate(nrf24.RF24_DATA_RATE.RATE_2MBPS)
        # nrf.set_payload_size(32)
        # nrf.set_channel(3)
        nrf.set_address(nrf24.RF24_RX_ADDR.P0, [0, 0, 0, 0, 0])
        # nrf.reset_rx_address()
        nrf.set_address_bytes(2)
        nrf.flush_rx()
        nrf.open_reading_pipe(
            nrf24.RF24_RX_ADDR.P0,
            address=addr,
            # auto_ack=False
        )
        nrf.disable_crc()
        nrf.set_auto_ack(False)
        nrf.show_registers()

        return nrf

    @staticmethod
    def configure_for_sniffing(pi, mac_address: str, chan: int, gpio_interrupt):
        usable_mac = [
            int(x, 16) for x in mac_address.split(":")
        ]

        print(usable_mac)

        pi.callback(24, pigpio.FALLING_EDGE, gpio_interrupt)

        nrf = NRF24Wrapper(
            pi,
            ce=25,
            payload_size=nrf24.RF24_PAYLOAD.DYNAMIC,
            channel=chan,
            data_rate=nrf24.RF24_DATA_RATE.RATE_2MBPS,
            pa_level=nrf24.RF24_PA.MIN
        )

        nrf.open_reading_pipe(nrf24.RF24_RX_ADDR.P0, address=usable_mac)
        nrf.enable_crc()
        nrf.set_auto_ack(False)
        nrf.show_registers()

        return nrf
