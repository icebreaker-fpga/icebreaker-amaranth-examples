from amaranth import *
from amaranth.build import *
from amaranth.lib.io import Pin
from amaranth_boards.icebreaker import ICEBreakerPlatform

# This resource has a single 'oe' signal for all the pins.
# If we want individually controllable 'oe' signals for each pin,
# then we would need to define a Subsignal for each pin.
# The triled Pmod is connected to PMOD1A connector.
triled_pmod = [
    Resource("triled", 0, Pins("1 2 3 4 7 8 9 10", dir="oe", conn=("pmod", 0)),
             Attrs(IO_STANDARD="SB_LVCMOS")),
]


class Blinker(Elaboratable):
    def __init__(self, leds, maxperiod):
        self.maxperiod = maxperiod
        self.counter = Signal(range(maxperiod+1))
        self.period = Signal(range(maxperiod+1))
        self.state_counter = Signal(2)
        self.leds = leds

    def elaborate(self, _platform: Platform) -> Module:
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
        m.d.comb += self.leds.oe.eq(~self.state_counter[0])
        for i in range(len(self.leds.o)):
            m.d.comb += self.leds.o[i].eq(self.state_counter[1])

        return m


if __name__ == "__main__":
    plat = ICEBreakerPlatform()
    plat.add_resources(triled_pmod)
    leds = plat.request("triled")
    my_blinker = Blinker(leds, 10000000)

    plan = plat.build(my_blinker, do_program=True)
