#!/usr/bin/env python3

from argparse import ArgumentParser

from nmigen import *
from nmigen.build import *
from nmigen.back import pysim
from nmigen_boards.icebreaker import ICEBreakerPlatform


# | rotary encoder pins | PMOD 1A pins |
# |---------------------|--------------|
# | GND                 | GND          |
# | A                   | 1            |
# | B                   | 2            |
rotary_encoder_pmod = [
    Resource("rotary_encoder", 0,
             Subsignal("quadrature", PinsN("1", dir="i", conn=("pmod", 0)),
                       Attrs(IO_STANDARD="SB_LVCMOS33", PULLUP=1)),
             Subsignal("in_phase", PinsN("2", dir="i", conn=("pmod", 0)),
                       Attrs(IO_STANDARD="SB_LVCMOS33", PULLUP=1)),
             Subsignal("switch", PinsN("3", dir="i", conn=("pmod", 0)),
                       Attrs(IO_STANDARD="SB_LVCMOS33", PULLUP=1)))
]

class Top(Elaboratable):
    def __init__(self):
        self.iq_to_step_dir = IQToStepDir()
        self.state = Signal(unsigned(4), reset=0b0001)

    def elaborate(self, platform):
        encoder_pins = platform.request("rotary_encoder")
        red = platform.request("led_r", 0)
        green = platform.request("led_g", 0)
        leds = Cat(
            # leds in ccw order
            platform.request("led_g", 1),
            platform.request("led_g", 4),
            platform.request("led_g", 2),
            platform.request("led_g", 3),
        )

        m = Module()

        m.submodules.iq_to_step_dir = self.iq_to_step_dir

        # only change state when step happened
        with m.If(self.iq_to_step_dir.step):
            m.d.sync += [
                # on = cw, off = ccw
                red.eq(self.iq_to_step_dir.direction),
                # toggle led
                green.eq(1-green),
            ]
            # shift with wrap around
            with m.If(self.iq_to_step_dir.direction == 0):
                m.d.sync += self.state.eq(Cat(self.state[-1:], self.state[:-1]))
            with m.Else():
                m.d.sync += self.state.eq(Cat(self.state[1:], self.state[:1]))

        m.d.comb += [
            self.iq_to_step_dir.iq.eq(Cat(encoder_pins.in_phase, encoder_pins.quadrature)),
            leds.eq(self.state),
        ]

        return m

class IQToStepDir(Elaboratable):
    def __init__(self):
        # two incoming bits for in-phase and quadrature (A and B) inputs
        self.iq = Signal(2)
        # create storage for inputs
        self.iq_history = Array(Signal(2) for _ in range(2))
        # outgoing signals
        self.step = Signal(1)
        self.direction = Signal(1)

    def elaborate(self, _platform):
        m = Module()

        m.d.comb += [
            # a step is only taken when either I or Q flip.
            # if none flip, no step is taken
            # if both flip, an error happend
            self.step.eq(Cat(self.iq_history).xor()),
            # if the former value of I is the current value of Q, we move counter clockwise
            self.direction.eq(Cat(self.iq_history[1][0], self.iq_history[0][1]).xor()),
        ]

        m.d.sync += [
            # store the current and former state
            self.iq_history[1].eq(self.iq_history[0]),
            self.iq_history[0].eq(self.iq),
        ]

        return m

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-s", action="store_true", help="Simulate Rotary Encoder (for debugging).")
    args = parser.parse_args()

    if args.s:
        iq_to_step_dir = IQToStepDir()
        sim = pysim.Simulator(iq_to_step_dir)
        sim.add_clock(1.0 / 12e6)

        def out_proc():
            seq = (0b00, 0b01, 0b11, 0b10)
            yield iq_to_step_dir.iq.eq(0b00)
            for _ in range(16):
                for _ in range(4):
                    for iq in seq:
                        yield iq_to_step_dir.iq.eq(iq)
                        yield
                        yield
                        yield
                        yield
                for _ in range(4):
                    for iq in seq[::-1]:
                        yield iq_to_step_dir.iq.eq(iq)
                        yield
                        yield
                        yield
                        yield

        sim.add_sync_process(out_proc)
        with sim.write_vcd("rotary_encoder.vcd", "rotary_encoder.gtkw",
                           traces=[iq_to_step_dir.iq,
                                   iq_to_step_dir.step,
                                   iq_to_step_dir.direction]):
            sim.run()
    else:
        plat = ICEBreakerPlatform()
        plat.add_resources(plat.break_off_pmod)
        plat.add_resources(rotary_encoder_pmod)
        plat.build(Top(), do_program=True)
