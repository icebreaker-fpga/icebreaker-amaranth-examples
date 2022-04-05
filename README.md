# iCEBreaker amaranth examples

This repository contains examples for the [amaranth HDL](https://github.com/amaranth-lang/amaranth)
Python library for register transfer level modeling of synchronous logic. Ordinary Python code is
used to construct a netlist of a digital circuit, which can be simulated, directly synthesized via
Yosys, or converted to human-readable Verilog code for use with industry-standard toolchains.

To install [amaranth](https://amaranth-lang.org/docs/amaranth/latest/install.html) and
[amaranth-boards](https://github.com/amaranth-lang/amaranth-boards) and the necessary dependencies
follow the [amaranth installation instructions](https://amaranth-lang.org/docs/amaranth/latest/install.html).

After that all you need to do is connect your iCEBreaker to the computer and run the python script
in an example directory.

The scripts are by default set to synthesize and upload the bitstream to the iCEBreaker board.

## Repository structure

This repository contains examples for multiple iCEBreaker development boards.
The examples for each dev board can be found inside their respective
subdirectories.

## Warning
Amaranth is still a work in progress project. Expect examples to occasionally break until amaranth
fully stabilizes.
