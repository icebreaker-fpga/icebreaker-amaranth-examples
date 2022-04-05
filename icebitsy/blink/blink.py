#!/usr/bin/env python3

from amaranth import *
from amaranth_boards.icebreaker_bitsy import ICEBreakerBitsyPlatform

# Import the ICEBitsyDfuWrapper
import sys
import os
if __package__:
    from ..common.dfu_helper import ICEBitsyDfuWrapper
else:
    sys.path.append(os.path.dirname(__file__) + '/..')
    from common.dfu_helper import ICEBitsyDfuWrapper


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

        return m


plat = ICEBreakerBitsyPlatform()
blinker = Blinker(10000000)
plat.build(ICEBitsyDfuWrapper(blinker), do_program=True)
