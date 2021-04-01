# Ubirch Testkit - Changelog

## [1.2.0] - 2021-03-31
### Added
- This changelog and a patch level in versioning.
- Handling of unsolicited messages from modem as needed with the newer pycom firmware.

### Changed
- Update pycom firmware dependency to version v1.20.2.r4. This version is tested with modem firmware version 41019 and 41065 (NB-IoT).

### Fixed
- Rework of modem communication module.

### Known issues
- When network coverage is low the modem gets quite busy leading to flaws in the communication between modem and esp. A solution to this problem could be to position the device in a place with better network coverage.

## [1.1] - 2020-07-06
### Added
- First version of Ubirch Testkit application, which works on a GPy and a PySense or PyTrack from PyCom together with a NB-IoT SIM card with connectivity from 1nce. This application can be used to test the "Ubirch protocol" in general, and espacially to test "Ubirch on a SIM". You can build your own ubirch application based on this.
- This Version runs with pycom firmware version 1.20.2.rc10 and modem firmware version 41019 (NB-IoT).
