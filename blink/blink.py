from amaranth import *
from amaranth_boards.icebreaker import ICEBreakerPlatform


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


plat = ICEBreakerPlatform()
plat.build(Blinker(10000000), do_program=True)
