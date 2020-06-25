from nmigen import *
from nmigen_boards.icebreaker import *


class Blinker(Elaboratable):
    def __init__(self, maxperiod):
        self.maxperiod = maxperiod

    def elaborate(self, platform):
        clk12 = platform.request("clk12")
        led = platform.request("led_r")

        m = Module()
        m.domains.sync = ClockDomain()
        m.d.comb += ClockSignal().eq(clk12)

        counter = Signal(range(self.maxperiod + 1))
        period = Signal(range(self.maxperiod + 1))

        m.d.comb += period.eq(self.maxperiod)

        with m.If(counter == 0):
            m.d.sync += [
                led.eq(~led),
                counter.eq(period)
            ]
        with m.Else():
            m.d.sync += [
                counter.eq(counter - 1)
            ]

        return m


plat = ICEBreakerPlatform()
plat.build(Blinker(10000000), do_program=True)
