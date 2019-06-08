# iCEBreaker nmigen examples

This repository contains examples for the [nmigen](https://github.com/m-labs/nmigen) Python toolbox for building complex digital hardware.
nmigen is a refresh of [migen](https://github.com/m-labs/migen) and is expected to be the future direction for migen in general.

As wth the migen [examples](https://github.com/icebreaker-fpga/icebreaker-migen-examples), you will need to have python3, nmigen
and icestorm/nextpnr/yosys (master branch) installed on your system. Additionally, you will need to have the
[nmigen-boards](https://github.com/m-labs/nmigen-boards) package installed for the board description file for iCEBreaker.

After that all you need to do is connect your iCEBreaker to the computer and run the python script in an example directory.

The scripts are by default set to synthesize and upload the bitstream to the iCEBreaker board.

## Warning
Nmigen is currently unstable. Expect examples to occassionally break until nmigen fully stabilizes.
