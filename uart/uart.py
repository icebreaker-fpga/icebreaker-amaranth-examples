from argparse import ArgumentParser
from ctypes import ArgumentError
from amaranth import *
from amaranth.build import *
from amaranth import sim
from amaranth_boards.icebreaker import *


def _divisor(freq_in, freq_out, max_ppm=None):
    divisor = freq_in // freq_out
    if divisor <= 0:
        raise ArgumentError("Output frequency is too high.")

    ppm = 100000 * ((freq_in / divisor) - freq_out) / freq_out
    if max_ppm is not None and ppm > max_ppm:
        raise ArgumentError("Output frequency deviation is too high.")

    return divisor


class UART(Elaboratable):
    def __init__(self, serial, clk_freq, baud_rate):
        self.rx_data = Signal(8)
        self.rx_ready = Signal()
        self.rx_ack = Signal()
        self.rx_error = Signal()
        self.rx_strobe = Signal()
        self.rx_bitno = None
        self.rx_fsm = None

        self.tx_data = Signal(8)
        self.tx_ready = Signal()
        self.tx_ack = Signal()
        self.tx_strobe = Signal()
        self.tx_bitno = None
        self.tx_latch = None
        self.tx_fsm = None

        self.serial = serial

        self.divisor = _divisor(
            freq_in=clk_freq, freq_out=baud_rate, max_ppm=50000)

    def elaborate(self, _platform: Platform) -> Module:
        m = Module()

        # RX

        rx_counter = Signal(range(self.divisor))
        m.d.comb += self.rx_strobe.eq(rx_counter == 0)
        with m.If(rx_counter == 0):
            m.d.sync += rx_counter.eq(self.divisor - 1)
        with m.Else():
            m.d.sync += rx_counter.eq(rx_counter - 1)

        self.rx_bitno = rx_bitno = Signal(3)
        with m.FSM(reset="IDLE") as self.rx_fsm:
            with m.State("IDLE"):
                with m.If(~self.serial.rx):
                    m.d.sync += rx_counter.eq(self.divisor // 2)
                    m.next = "START"

            with m.State("START"):
                with m.If(self.rx_strobe):
                    m.next = "DATA"

            with m.State("DATA"):
                with m.If(self.rx_strobe):
                    m.d.sync += [
                        self.rx_data.eq(
                            Cat(self.rx_data[1:8], self.serial.rx)),
                        rx_bitno.eq(rx_bitno + 1)
                    ]
                    with m.If(rx_bitno == 7):
                        m.next = "STOP"

            with m.State("STOP"):
                with m.If(self.rx_strobe):
                    with m.If(~self.serial.rx):
                        m.next = "ERROR"
                    with m.Else():
                        m.next = "FULL"

            with m.State("FULL"):
                m.d.comb += self.rx_ready.eq(1)
                with m.If(self.rx_ack):
                    m.next = "IDLE"
                with m.Elif(~self.serial.rx):
                    m.next = "ERROR"

            with m.State("ERROR"):
                m.d.comb += self.rx_error.eq(1)

        # TX

        tx_counter = Signal(range(self.divisor))
        m.d.comb += self.tx_strobe.eq(tx_counter == 0)
        with m.If(tx_counter == 0):
            m.d.sync += tx_counter.eq(self.divisor - 1)
        with m.Else():
            m.d.sync += tx_counter.eq(tx_counter - 1)

        self.tx_bitno = tx_bitno = Signal(3)
        self.tx_latch = tx_latch = Signal(8)
        with m.FSM(reset="IDLE") as self.tx_fsm:
            with m.State("IDLE"):
                m.d.comb += self.tx_ack.eq(1)
                with m.If(self.tx_ready):
                    m.d.sync += [
                        tx_counter.eq(self.divisor - 1),
                        tx_latch.eq(self.tx_data)
                    ]
                    m.next = "START"
                with m.Else():
                    m.d.sync += self.serial.tx.eq(1)

            with m.State("START"):
                with m.If(self.tx_strobe):
                    m.d.sync += self.serial.tx.eq(0)
                    m.next = "DATA"

            with m.State("DATA"):
                with m.If(self.tx_strobe):
                    m.d.sync += [
                        self.serial.tx.eq(tx_latch[0]),
                        tx_latch.eq(Cat(tx_latch[1:8], 0)),
                        tx_bitno.eq(tx_bitno + 1)
                    ]
                    with m.If(self.tx_bitno == 7):
                        m.next = "STOP"

            with m.State("STOP"):
                with m.If(self.tx_strobe):
                    m.d.sync += self.serial.tx.eq(1)
                    m.next = "IDLE"

        return m


class _TestPads(Elaboratable):
    def __init__(self):
        self.rx = Signal(reset=1)
        self.tx = Signal()

    def elaborate(self, _platform: Platform) -> Module:
        m = Module()
        return m


def _test_rx(rx, dut):
    def T():
        yield
        yield
        yield
        yield

    def B(bit):
        yield rx.eq(bit)
        yield from T()

    def S():
        yield from B(0)
        assert (yield dut.rx_error) == 0
        assert (yield dut.rx_ready) == 0

    def D(bit):
        yield from B(bit)
        assert (yield dut.rx_error) == 0
        assert (yield dut.rx_ready) == 0

    def E():
        yield from B(1)
        assert (yield dut.rx_error) == 0

    def O(bits):
        yield from S()
        for bit in bits:
            yield from D(bit)
        yield from E()

    def A(octet):
        yield from T()
        assert (yield dut.rx_data) == octet
        yield dut.rx_ack.eq(1)
        while (yield dut.rx_ready) == 1:
            yield
        yield dut.rx_ack.eq(0)

    def F():
        yield from T()
        assert (yield dut.rx_error) == 1
        yield rx.eq(1)
        yield ResetSignal("sync").eq(1)
        yield
        yield
        yield ResetSignal("sync").eq(0)
        yield
        yield
        assert (yield dut.rx_error) == 0

    # bit patterns
    yield from O([1, 0, 1, 0, 1, 0, 1, 0])
    yield from A(0x55)
    yield from O([1, 1, 0, 0, 0, 0, 1, 1])
    yield from A(0xC3)
    yield from O([1, 0, 0, 0, 0, 0, 0, 1])
    yield from A(0x81)
    yield from O([1, 0, 1, 0, 0, 1, 0, 1])
    yield from A(0xA5)
    yield from O([1, 1, 1, 1, 1, 1, 1, 1])
    yield from A(0xFF)

    # framing error
    yield from S()
    for bit in [1, 1, 1, 1, 1, 1, 1, 1]:
        yield from D(bit)
    yield from S()
    yield from F()

    # overflow error
    yield from O([1, 1, 1, 1, 1, 1, 1, 1])
    yield from B(0)
    yield from F()


def _test_tx(tx, dut):
    def Th():
        yield
        yield

    def T():
        yield
        yield
        yield
        yield

    def B(bit):
        yield from T()
        assert (yield tx) == bit

    def S(octet):
        assert (yield tx) == 1
        assert (yield dut.tx_ack) == 1
        yield dut.tx_data.eq(octet)
        yield dut.tx_ready.eq(1)
        while (yield tx) == 1:
            yield
        yield dut.tx_ready.eq(0)
        assert (yield tx) == 0
        assert (yield dut.tx_ack) == 0
        yield from Th()

    def D(bit):
        assert (yield dut.tx_ack) == 0
        yield from B(bit)

    def E():
        assert (yield dut.tx_ack) == 0
        yield from B(1)
        yield from Th()

    def O(octet, bits):
        yield from S(octet)
        for bit in bits:
            yield from D(bit)
        yield from E()

    yield from O(0x55, [1, 0, 1, 0, 1, 0, 1, 0])
    yield from O(0x81, [1, 0, 0, 0, 0, 0, 0, 1])
    yield from O(0xFF, [1, 1, 1, 1, 1, 1, 1, 1])
    yield from O(0x00, [0, 0, 0, 0, 0, 0, 0, 0])


def _test(tx, rx, dut, _cd=None):
    yield from _test_rx(rx, dut)
    yield from _test_tx(tx, dut)


class _LoopbackTest(Elaboratable):
    def __init__(self):
        self.empty = Signal(reset=1)
        self.data = Signal(8)
        self.rx_strobe = Signal()
        self.tx_strobe = Signal()
        self.uart = None

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        serial = platform.request("uart")
        leds = Cat([platform.request("led_r"), platform.request("led_g")])
        debug = platform.request("debug")

        self.uart = UART(serial, clk_freq=12000000, baud_rate=115200)
        m.submodules.uart = self.uart

        m.d.comb += [
            self.rx_strobe.eq(self.uart.rx_ready & self.empty),
            self.tx_strobe.eq(self.uart.tx_ack & ~self.empty),
            self.uart.rx_ack.eq(self.rx_strobe),
            self.uart.tx_data.eq(self.data),
            self.uart.tx_ready.eq(self.tx_strobe)
        ]

        with m.If(self.rx_strobe):
            m.d.sync += [
                self.data.eq(self.uart.rx_data),
                self.empty.eq(0)
            ]
        with m.If(self.tx_strobe):
            m.d.sync += self.empty.eq(1)

        m.d.comb += [
            leds.eq(self.uart.rx_data[0:2]),
            debug.eq(Cat(
                serial.rx,
                serial.tx,
                self.uart.rx_strobe,
                self.uart.tx_strobe,
            ))
        ]

        return m


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-s", action="store_true", help="Simulate Rotary Encoder (for debugging).")
    args = parser.parse_args()

    if args.s:
        pads = _TestPads()

        dut = UART(pads, clk_freq=4800, baud_rate=1200)
        s = sim.Simulator(dut)
        s.add_clock(1.0 / 12e6)

        s.add_sync_process(_test(pads.tx, pads.rx, dut))
        with s.write_vcd("uart.vcd", "uart.gtkw", traces=[pads.tx, pads.rx]):
            s.run()
    else:
        plat = ICEBreakerPlatform()

        # The debug pins are on the PMOD1A in the following order on the connector:
        # 7 8 9 10 1 2 3 4
        # Yes that means that the pins at the edge of the board come first
        # and the pins further away from the edge second
        plat.add_resources([
            Resource("debug", 0, Pins("7 8 9 10 1 2 3 4", dir="o",
                                      conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS"))
        ])

        plat.build(_LoopbackTest(), do_program=True)
