-----------------------------------------------------------------------------

                   --- CAEN SpA - Computing Division ---

                                www.caen.it

  -----------------------------------------------------------------------------

  Program: WaveDump


  -----------------------------------------------------------------------------


  Content
  -----------------------------------------------------------------------------

  - README        :  This file.
  - INSTALL       : Installation guide
  - ReleaseNotes  :  Revision History and notes.
  - src           :  Source files.
  - include       :  Include files.


  System Requirements
  -----------------------------------------------------------------------------
  - CAENVME library Ver 4.0.2 or above
  - CAENComm library Ver 1.7.0 or above
  - CAEN Digitizer Library Ver 2.16.2 or above
  - glibc 2.19 or above
  - GNUplot >=4.2 (www.gnuplot.org)
  - CAEN toolbox (suggested, not compulsory)
  - USB drivers for v1718 https://caen.it/wp-content/uploads/2026/06/CAENUSBdrvB-v1.6.2.tar.gz


  Syntax
  -----------------------------------------------------------------------------
  - wavedump [ConfigFile]
  - Default config file is "/etc/wavedump/WaveDumpConfig.txt"
  - or "/etc/wavedump/WaveDumpConfig_X742.txt" for X742 boards [THIS ONE USED IN THIS REPO!]
  - or "/etc/wavedump/WaveDumpConfig_X740.txt" for X740 boards.

  Keyword list and syntax for the configuration file:
  -----------------------------------------------------------------------------
  - For configuration file syntax please refer to the Wavedump Manual.

  -----------------------------------------------------------------------------
  How to get support
  -----------------------------------------------------------------------------
  - For technical support, go to https://www.caen.it/mycaen/support/ (login and MyCAEN+ account required).

  -----------------------------------------------------------------------------

  Test with pulses
  -----------------------------------------------------------------------------
  - See picture in Wiki
  - Follow requirements list and installation guide
  - 100-ns width, 200 mV Vpp and <450 Hz rate lemo-mcx (50 Ohm exit impedance) from pulser to ch0 TRG in V1742
  - pulse TTL TRG OUT in TRG IN LEMO input connector in the V1742 front panel
  - trigger/output delay to 0 in the pulser (simulates realistic situations)
  - post-trigger size of acquisition window at 0% (already setup in the pushed config), can be tuned from 0% to 100%
  - Front panel of V1742 set to TTL (already setup in the pushed config), MAKE SURE the green TTL led is switched on on V1742!
  - run: wavedump
  - then "s" (start), and "W" (continuos writing enabled), then "s" to stop acquisition and "q" to exit
  - Using V1718 connected with USB to PC, and put in slot 1 of VME crate, with V1742 in one of the first 16 slots
