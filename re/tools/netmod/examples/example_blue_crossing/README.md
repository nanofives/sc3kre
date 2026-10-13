# example_blue_crossing

Test fixture for netbridge, needs `example_blue_road` installed (it declares 20029). Level crossing 69 cloned as
variant 20069 with the `blue` tint; inheritance puts it in both Sets that hold 69 (ROAD and RAIL), so it gets 69's
class. The `crossings` entry makes sc3netmod.dll (XCROSS) build 20069 instead of 69 when a rail line crosses an
existing 20029 tile. Results: `verify/netbridge/RESULTS.md`.
