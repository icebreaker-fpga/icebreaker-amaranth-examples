from nmigen import *
from nmigen.build import *
from nmigen.lib.io import Pin
from nmigen_boards.icebreaker import *

triled_pmod = [
    Resource("triled", 0, Pins("1 2 3 4 7 8 9 10", dir="oe",
                               conn=("pmod", 1)), Attrs(IO_STANDARD="SB_LVCMOS")),
]


class Blinker(Elaboratable):
    def __init__(self, led, maxperiod):
        self.maxperiod = maxperiod
        self.counter = Signal(range(maxperiod+1))
        self.period = Signal(range(maxperiod+1))
        self.state_counter = Signal(2)
        self.led = led

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        # Timer
        m.d.comb += self.period.eq(self.maxperiod)
        with m.If(self.counter == 0):
            m.d.sync += [
                self.state_counter.eq(self.state_counter + 1),
                self.counter.eq(self.period)
            ]
        with m.Else():
            m.d.sync += self.counter.eq(self.counter - 1)

        # LEDs
        for i in range(len(self.led)):
            m.d.comb += self.led.oe.eq(~self.state_counter[0])
            m.d.comb += self.led.o.eq(self.state_counter[1])

        return m


if __name__ == "__main__":
    plat = ICEBreakerPlatform()
    plat.add_resources(triled_pmod)
    led = plat.request("triled")
    my_blinker = Blinker(led, 10000000)

    plan = plat.build(my_blinker, do_program=True)
