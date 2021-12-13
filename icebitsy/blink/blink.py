from amaranth import *
from amaranth_boards.icebreaker_bitsy import ICEBreakerBitsyPlatform

# Import the common DfuHelper
import sys, os
if __package__:
    from ..common import dfu_helper
else:
    sys.path.append(os.path.dirname(__file__) + '/..')
    from common.dfu_helper import DfuHelper


class Blinker(Elaboratable):
    def __init__(self, maxperiod):
        self.maxperiod = maxperiod

    def elaborate(self, platform):
        led = platform.request("led_r")

        m = Module()

        counter = Signal(range(self.maxperiod + 1))

        with m.If(counter == 0):
            m.d.sync += [
                led.eq(~led),
                counter.eq(self.maxperiod)
            ]
        with m.Else():
            m.d.sync += counter.eq(counter - 1)

        # Hold user button until green LED
        # goes out, upon release the bitsy
        # will reboot into the DFU bootloader
        dfu = DfuHelper()
        dfu.btn_in = platform.request("button")
        m.submodules += dfu
        ledg = platform.request("led_g")
        m.d.comb += ledg.eq(~dfu.will_reboot)

        return m


plat = ICEBreakerBitsyPlatform()
plat.build(Blinker(10000000), do_program=True)
