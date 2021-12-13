from amaranth import *
from amaranth import sim


class DfuHelper(Elaboratable):
    """Trigger reboot from application into DFU Bootloader or bootloader to
    application by pressing the `btn_in` for at least `2^long_tw` cycles.

    The boot mode, app->boot/boot->app is selected through `bootloader_mode`.

    You have to set `btn_in` to the button input signal.

    * Samples the button every `2^sample_tw` or every `btn_tick` if
      `use_btn_tick` is enabled.
    * 4 sample cycle debouncing on input button down and up.
    * Prevents reboot when the button is pressed right after startup by
      asserting `armed` after reset only if `btn_in` is released for at least
      `2^(sample_tw - 2)` cycles.
    * Provides a strobe `btn_press` signal when button is released before
      `2^sample_tw` cycles.

    In application mode:
        Button release after a long press triggers reboot into bootloader image.
        Button release after a short press strobes `btn_press`

    In bootloader mode:
        Any button press triggers reboot into application image.
    """

    def __init__(self,
                 sample_tw = 7,
                 long_tw = 17,
                 btn_use_tick = False,
                 btn_invert = False,
                 bootloader_mode = False,
                 boot_img = 0b01,
                 user_image = 0b10):
        self.sample_tw = sample_tw
        self.long_tw = long_tw
        self.btn_use_tick = btn_use_tick
        self.btn_invert = btn_invert
        self.bootloader_mode = bootloader_mode
        self.boot_img = boot_img
        self.user_img = user_image

        # Inputs
        self.boot_sel = Signal()
        self.boot_now = Signal()
        self.btn_in = Signal()
        self.btn_tick = Signal()

        # Outputs
        self.btn_val = Signal()
        self.btn_press = Signal()
        self.will_reboot = Signal()

    def elaborate(self, platform):
        m = Module()

        # Signals
        # -------

        # Input Stage
        btn_cur = Signal()
        btn_raw = Signal()

        # Sampling
        btn_sample_now = Signal()

        # Debounce
        btn_debounce = Signal(3)
        btn_fall = Signal()

        # Long timer
        long_cnt = Signal(self.long_tw + 1)
        long_inc = Signal.like(long_cnt)
        long_msk = Signal.like(long_cnt)

        armed = Signal()

        # Boot logic
        wb_sel = Signal(2)
        wb_req = Signal()
        wb_now = Signal()

        # Button
        # ------

        # Note: Here is where we could instantiate the IOB
        m.d.comb += btn_raw.eq(self.btn_in)

        if self.btn_invert:
            m.d.sync += btn_cur.eq(~btn_raw)
        else:
            m.d.sync += btn_cur.eq(btn_raw)

        # Sampling tick
        if self.btn_use_tick:
            m.d.comb += btn_sample_now.eq(self.btn_tick)
        else:
            btn_sample_cnt = Signal(self.sample_tw + 1)
            with m.If(btn_sample_cnt[-1]):
                m.d.sync += btn_sample_cnt.eq(0)
            with m.Else():
                m.d.sync += btn_sample_cnt.eq(btn_sample_cnt + 1)
            m.d.comb += btn_sample_now.eq(btn_sample_cnt[-1])

        # Debounce
        with m.If(btn_sample_now):
            with m.Switch(Cat(btn_cur, btn_debounce)):
                with m.Case('0--0'):
                    m.d.sync += btn_debounce.eq(0b000)
                with m.Case('0001'):
                    m.d.sync += btn_debounce.eq(0b001)
                with m.Case('0011'):
                    m.d.sync += btn_debounce.eq(0b010)
                with m.Case('0101'):
                    m.d.sync += btn_debounce.eq(0b011)
                with m.Case('0111', '1--1'):
                    m.d.sync += btn_debounce.eq(0b111)
                with m.Case('1110'):
                    m.d.sync += btn_debounce.eq(0b110)
                with m.Case('1100'):
                    m.d.sync += btn_debounce.eq(0b101)
                with m.Case('1010'):
                    m.d.sync += btn_debounce.eq(0b100)
                with m.Case('1000'):
                    m.d.sync += btn_debounce.eq(0b000)
                with m.Default():
                    m.d.sync += btn_debounce.eq(0b000)

        m.d.comb += self.btn_val.eq(btn_debounce[-1])

        m.d.sync += btn_fall.eq((btn_debounce == 0b100) & ~btn_cur & btn_sample_now)

        # Long-press / Arming
        # -------------------
        m.d.sync += armed.eq(armed | long_cnt[-3])

        m.d.comb += [
            long_inc.eq(Cat(~long_cnt[-1], Repl(0, self.long_tw))),
            long_msk.eq(Repl(~(armed ^ self.btn_val), self.long_tw + 1))
        ]

        with m.If(btn_sample_now):
            m.d.sync += long_cnt.eq((long_cnt + long_inc) & long_msk)

        # Command logic
        # -------------

        with m.If(self.boot_now):
            # External boot request
            m.d.sync += [
                wb_sel.eq(self.boot_sel),
                wb_req.eq(1),
                self.btn_press.eq(0)
            ]
        with m.Else():
            if self.bootloader_mode:
                # We are in a DFU bootloader, any button press results in
                # application boot
                print("bootloader mode")
                m.d.sync += [
                    wb_sel.eq(self.user_img),
                    wb_req.eq((armed & btn_fall) | wb_req),
                    self.btn_press.eq(0)
                ]
            else:
                # We are in user application, short press resets the
                # logic, long press triggers DFU reboot
                print("application mode")
                m.d.sync += [
                    wb_sel.eq(self.boot_img),
                    wb_req.eq((armed & btn_fall & long_cnt[-1]) | wb_req),
                    self.btn_press.eq(armed & btn_fall & (~long_cnt[-1]))
                ]

        # Boot
        # ----

        m.d.sync += wb_now.eq(wb_req)

        # Instantiate the warmboot technology block when not in sim
        if platform is not None:
            m.submodules += Instance(
                'SB_WARMBOOT',
                i_BOOT = wb_now,
                i_S0 = wb_sel[0],
                i_S1 = wb_sel[1]
            )

        m.d.comb += self.will_reboot.eq(armed & long_cnt[-1])

        return m

if __name__ == "__main__":
    dfu_helper = DfuHelper(sample_tw=2, long_tw=5)
    s = sim.Simulator(dfu_helper)
    s.add_clock(1.0 / 12e6)

    def proc():
        # Leaving bootloader with the button depressed
        yield dfu_helper.btn_in.eq(1)
        for _ in range(50):
            yield
        # Button released, allowing dfu_helper to arm
        yield dfu_helper.btn_in.eq(0)
        for _ in range(100):
            yield
        # Super short button glitch to test debounce
        yield dfu_helper.btn_in.eq(1)
        for _ in range(10):
            yield
        yield dfu_helper.btn_in.eq(0)
        for _ in range(10):
            yield
        assert (yield dfu_helper.btn_val) == 0
        # Short button press, not enough to trigger reboot
        yield dfu_helper.btn_in.eq(1)
        for _ in range(50):
            yield
        yield dfu_helper.btn_in.eq(0)
        for _ in range(50):
            yield
        # Long button press, enough to trigger reboot
        yield dfu_helper.btn_in.eq(1)
        for _ in range(200):
            yield
        yield dfu_helper.btn_in.eq(0)
        for _ in range(50):
            yield

    s.add_sync_process(proc)
    with s.write_vcd("dfu_helper.vcd", "dfu_helper.gtkw",
                     traces=[dfu_helper.btn_in,
                             dfu_helper.btn_val]):
        s.run()

    print("Simulation finished. Open dfu_helper.gtkw")