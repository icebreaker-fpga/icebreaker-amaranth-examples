from nmigen import *
from nmigen.build import *
from nmigen_boards.icebreaker import *

# This PMOD is provided with your icebreaker, and should be attached
# to PMOD1A.
seven_seg_pmod = [
    Resource("seven_seg", 0,
             Subsignal("aa", PinsN("1", dir="o", conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS33")),
             Subsignal("ab", PinsN("2", dir="o", conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS33")),
             Subsignal("ac", PinsN("3", dir="o", conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS33")),
             Subsignal("ad", PinsN("4", dir="o", conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS33")),
             Subsignal("ae", PinsN("7", dir="o", conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS33")),
             Subsignal("af", PinsN("8", dir="o", conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS33")),
             Subsignal("ag", PinsN("9", dir="o", conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS33")),
             Subsignal("ca", PinsN("10", dir="o", conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS33")))
]


class Top(Elaboratable):
    def __init__(self):
        # TODO: Figure out how to expose the P1A{1-4, 7-10} pins in the
        # constructor so Top can be built in a potentially platform-agnostic
        # way using nmigen.cli.main. For now, only put child modules in
        # constructor.
        self.ones_to_segs = DigitToSegments()
        self.tens_to_segs = DigitToSegments()

    def elaborate(self, platform):
        seg_pins = platform.request("seven_seg")

        m = Module()

        seg_pins_cat = Signal(7)

        counter = Signal(30)
        ones_counter = Signal(4)
        tens_counter = Signal(4)
        display_state = Signal(3)

        # ones_segment = Signal(7)
        # tens_segment = Signal(7)

        m.submodules.ones_to_segs = self.ones_to_segs
        m.submodules.tens_to_segs = self.tens_to_segs

        m.d.comb += [
            Cat([seg_pins.aa, seg_pins.ab, seg_pins.ac, seg_pins.ad,
                 seg_pins.ae, seg_pins.af, seg_pins.ag]).eq(seg_pins_cat),
            ones_counter.eq(counter[21:25]),
            tens_counter.eq(counter[25:29]),
            display_state.eq(counter[2:5]),
            self.ones_to_segs.digit.eq(ones_counter),
            self.tens_to_segs.digit.eq(tens_counter)
        ]

        m.d.sync += counter.eq(counter + 1)

        with m.Switch(display_state):
            with m.Case("00-"):
                m.d.sync += seg_pins_cat.eq(self.ones_to_segs.segments)
            with m.Case("010"):
                m.d.sync += seg_pins_cat.eq(0)
            with m.Case("011"):
                m.d.sync += seg_pins.ca.eq(1)
            with m.Case("10-"):
                m.d.sync += seg_pins_cat.eq(self.tens_to_segs.segments)
            with m.Case("110"):
                m.d.sync += seg_pins_cat.eq(0)
            with m.Case("111"):
                m.d.sync += seg_pins.ca.eq(0)

        return m


class DigitToSegments(Elaboratable):
    def __init__(self):
        self.digit = Signal(4)
        self.segments = Signal(7)

    def elaborate(self, platform):
        m = Module()

        with m.Switch(self.digit):
            for n, seg_val in enumerate([
                    0b0111111,
                    0b0000110,
                    0b1011011,
                    0b1001111,
                    0b1100110,
                    0b1101101,
                    0b1111101,
                    0b0000111,
                    0b1111111,
                    0b1101111,
                    0b1110111,
                    0b1111100,
                    0b0111001,
                    0b1011110,
                    0b1111001,
                    0b1110001]):
                with m.Case(n):
                    m.d.sync += self.segments.eq(seg_val)

        return m


if __name__ == "__main__":
    # In this example, explicitly show the intermediate classes used to
    # execute build() to demonstrate that a user can inspect
    # each part of the build process (create files, execute, program,
    # and create a zip file if you have a BuildPlan instance).
    plat = ICEBreakerPlatform()
    plat.add_resources(seven_seg_pmod)

    # BuildPlan if do_build=False
    # BuildProducts if do_build=True and do_program=False
    # None otherwise.
    plan = plat.build(Top(), do_build=False, do_program=False)  # BuildPlan
    products = plan.execute()  # BuildProducts
    plat.toolchain_program(products, "top")  # Manally run the programmer.
