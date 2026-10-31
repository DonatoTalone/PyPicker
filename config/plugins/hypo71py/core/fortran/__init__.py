"""
HYPO71PC (Version: SC3/ROB)

Modified HYPO71PC fortran code of LEE AND LAHR
(USGS OPEN-FILE REPORT 75-311, 1975) in order to:
- get rid of input files and associated restrictions (P and S phases
in each station musth have common time base in minutes, all stations
must have common date and hour, not possible to have S phase without
P phase)
- implement the core subroutine SINGLE (to locate one earthquake) as
a stand-alone subroutine getting all required information from its
arguments rather than from the INPUT1 and INPUT2 subroutines)
- combine advantages of different fortran versions (see below)
- strip redundant parameters (mainly those related with magnitude
calculation)
- allow it to be compiled with f2py into a module that can be called
directly from python without intermediary files

It is based on:
- ROB version modified by HPM, amongst other things to allow crustal
velocity models with independent S-wave velocities;
- version distributed with seiscomp3, modified by Alexandre Nercessian
(IPGP - France), and available at:
https://github.com/SeisComP3/seiscomp3/tree/master/src/ipgp/apps/3rd-party/Hypo71PC

It consists of the following files

azwtos.f:
Contains AZWTOS and SORT subroutines
Implements azimuthal weighting and calculation of azimuthal gap
Based on seiscomp version (but almost identical to ROB version)

swmreg.f:
Contains SWMREG and ANSWER subroutines
Implements stepwise multiple regression of phase residuals
Based on seiscomp version (but almost identical to ROB version)

trvdrv.f:
Contains TRVDRV, REFWAV, DIRWAV and PREP1 subroutines
Implements calculation of travel times and partial derivatives
Based on seiscomp version, but incorporating ROB modifications,
and leaving out code to model velocity gradient

single.f:
Contains SINGLE and OUTPUT subroutines
Implements location of a single earthquake
Mainly based on seiscomp version, but heavily modified

tinorm.f:
Contains TINORM subroutine
Implements approximation of the inverse CDF of the standard normal
distribution, used to perform MC sampling of arrival times
Based on ROB version

The signature files (.pyf) required to compile with f2py are
included. They can be regenerated with the following commands:
- to create separate python-callable modules:
f2py azwtos.f -m azwtos -h azwtos.pyf
- to create a single python-callable module containing all subroutines:
f2py single.f -m hypo71 -h hypo71.pyf

In order to compile:
- to create separate python-callable modules:
f2py -c azwtos.pyf azwtos.f
- to create a single python-callable module:
f2py -c hypo71.pyf single.f
On Windows, the following additional command-line arguments may be
required:
 --compiler=mingw32 --fcompiler=gnu95

All modifications by Kris Vanneste, Royal Observatory of Belgium
AD 2020
"""
