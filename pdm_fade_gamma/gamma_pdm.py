import argparse

from amaranth import *
from amaranth import sim
from amaranth_boards.icebreaker import ICEBreakerPlatform

# This example is based on the PDM module by Tommy Thorn, and
# was written from esden's reimplementation.
# You can find him on GitHub as @tommythorn
# The original is here:
# https://github.com/tommythorn/yari/blob/master/shared/rtl/soclib/pdm.v
# Esden can be found on Github as @esden
# His reimplementation is here:
# https://github.com/icebreaker-fpga/icebreaker-examples/blob/master/pdm_fade_gamma/gamma_pdm.v
# Comments are copied as-is.
# Also includes an example simulation I used for debugging signal width
# problems in PDMDriver!

# This example generates PDM (Pulse Density Modulation) to fade LEDs
# The intended result is opposite pulsating Red and Green LEDs
# on the iCEBreaker. The intended effect is that the two LED "breathe" in
# brigtness up and down in opposite directions.


class Top(Elaboratable):
    def __init__(self, width=16, gamma=2.2):
        self.width = width
        self.gamma = gamma

        self.pdm_g = PDMDriver()
        self.pdm_r = PDMDriver()
        self.cnt = PDMCounter(gamma=gamma)

    def elaborate(self, platform):
        ledr_n = platform.request("led_r")
        ledg_n = platform.request("led_g")

        m = Module()

        m.submodules.pdm_g = self.pdm_g
        m.submodules.pdm_r = self.pdm_r
        m.submodules.cnt = self.cnt

        m.d.comb += [
            self.pdm_g.pdm_in.eq(self.cnt.pdm_level1),
            self.pdm_r.pdm_in.eq(self.cnt.pdm_level2),
            ledg_n.eq(self.pdm_g.pdm_out),
            ledr_n.eq(self.pdm_r.pdm_out)
        ]

        return m


# PDM generator
#
# Pulse Density Modulation for controlling LED intensity.
# The theory is as follows:
# given a desired target level 0 <= T <= 1, control the output pdm_out
# in {1,0}, such that pdm_out on average is T. Do this by integrating the
# error T - pdm_out over time and switch pdm_out such that the sum of
# (T - pdm_out) is finite.
#
# pdm_sigma = 0, pdm_out = 0
# forever
#   pdm_sigma = pdm_sigma + (T - pdm_out)
#   if (pdm_sigma >= 0)
#     pdm_out = 1
#   else
#     pdm_out = 0
#
# Check: T = 0, pdm_out is never turned on; T = 1, pdm_out is olways on;
#        T = 0.5, pdm_out toggles
#
# In fixed point arithmetic this becomes the following (assume N-bit arith)
# pdm_sigma = pdm_sigma_float * 2^N = pdm_sigma_float << N.
# As |pdm_sigma| <= 1, N+2 bits is sufficient
#
# pdm_sigma = 0, pdm_out = 0
# forever
#   D = T + (~pdm_out + 1) << N === T + (pdm_out << N) + (pdm_out << (N+1))
#   pdm_sigma = pdm_sigma + D
#   pdm_out = 1 & (pdm_sigma >> (N+1))
class PDMDriver(Elaboratable):
    def __init__(self, in_width=16):
        self.pdm_out = Signal(1)
        self.pdm_in = Signal(in_width)
        self.in_width = in_width

    def elaborate(self, _platform):
        m = Module()

        pdm_sigma = Signal(self.in_width + 2)

        m.d.comb += self.pdm_out.eq(~pdm_sigma[-1])
        m.d.sync += [
            pdm_sigma.eq(pdm_sigma + Cat(self.pdm_in, self.pdm_out, self.pdm_out))
        ]

        return m


class PDMCounter(Elaboratable):
    def __init__(self, in_width=8, out_width=16, gamma=2.2):
        # Somewhat matter of preference whether to put submodules/Memory in
        # __init__() or elaborate, esp if submodule depends on other parameters
        # sent to __init__(). Contrast to Blinker, where Signals get maxperiod
        # in elaborate from self.maxperiod; there is no "self.gamma" here.
        gamma_init = [int(pow(1 / 255.0 * i, gamma) * 0xFFFF)
                      for i in range(256)]
        self.gamma_table = Memory(width=out_width, depth=2**in_width, init=gamma_init)
        self.in_width = in_width
        self.out_width = out_width
        self.pdm_level1 = Signal(out_width)
        self.pdm_level2 = Signal.like(self.pdm_level1)

    def elaborate(self, _platform) -> Module:
        m = Module()

        m.submodules.gamma_rd_p = gamma_rd_p = self.gamma_table.read_port()
        m.submodules.gamma_rd_n = gamma_rd_n = self.gamma_table.read_port()

        pdm_level_gamma_p = Signal.like(self.pdm_level2)
        pdm_level_gamma_n = Signal.like(pdm_level_gamma_p)
        pdm_count = Signal(self.out_width + 1)
        pdm_level = Signal(self.in_width + 1)

        m.d.sync += [
            pdm_count.eq(pdm_count + 1)
        ]

        with m.If(pdm_count[-1] == 1):
            m.d.sync += [
                pdm_count.eq(0),
                pdm_level.eq(pdm_level + 1)
            ]

        # In the Verilog version, the output data from the gamma table is in an
        # explicit always/sync block. The default memory in amaranth has a
        # synchronous read port (asynchronous=False), so data appears one clock
        # cycle after addr is put on the bus. Therefore we connect nets
        # directly.
        m.d.comb += [
            gamma_rd_p.addr.eq(pdm_level),
            gamma_rd_n.addr.eq(~pdm_level),
            pdm_level_gamma_p.eq(gamma_rd_p.data),
            pdm_level_gamma_n.eq(gamma_rd_n.data)
        ]

        with m.If(pdm_level[-1]):
            m.d.comb += [
                self.pdm_level1.eq(pdm_level_gamma_p),
                self.pdm_level2.eq(pdm_level_gamma_n)
            ]
        with m.Else():
            m.d.comb += [
                self.pdm_level1.eq(pdm_level_gamma_n),
                self.pdm_level2.eq(pdm_level_gamma_p)
            ]

        return m


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", action="store_true", help="Simulate PDMDriver (for debugging).")
    parser.add_argument("-g", type=float, default=2.2, help="Gamma exponent (default 2.2)")
    args = parser.parse_args()

    if args.s:
        p = PDMDriver(8)
        s = sim.Simulator(p)
        s.add_clock(1.0 / 12e6)

        def out_proc():
            for i in range(256):
                yield p.pdm_in.eq(i)
                yield
                yield
                yield
                yield

        s.add_sync_process(out_proc)
        with s.write_vcd("drv.vcd", "drv.gtkw", traces=[p.pdm_in, p.pdm_out]):
            s.run()
    else:
        plat = ICEBreakerPlatform()
        plat.build(Top(gamma=args.g), do_program=True)
