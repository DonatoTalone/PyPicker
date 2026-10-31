"""
Wrapper for Fortran version of SINGLE
"""

import numpy as np
from obspy import UTCDateTime

from ...station_phase import Station, StationPhases
from .hypo71 import single


def SINGLE(stations, pick_dict, velocity_model,
			ZTR, origin=(), vp_vs_ratio=1.73,
			ISW='',
			max_num_iterations=100, min_hypocentral_adjustment=0.05,
			use_s_picks=True,
			fix_depth=False, fix_origin=False, max_altitude=2.,
			azimuthal_weighting=True, XNEAR=50., XFAR=200.,
			min_rms_jeffrey=0.1, max_horizontal_adjustment=100.,
			max_horizontal_adjustment_for_depth_adjustment=10.,
			max_depth_adjustment=5., depth_above_max_altitude_adjustment=0.5,
			f_crit=2., f_crit_divisor=4.,
			compute_auxilliary_rms=False,
			apply_al_lindh_mod=True, min_num_phases=4,
			use_fortran_speedups=True, station_elevation='absolute',
			verbose=0):
	"""
	:param use_fortran_speedups:
		bool, dummy argument added for compatibility with full python version
	:param verbose:
		int, verbosity level
		If 2 or higher, output file HYPO71.PRN will be written!
	"""
	from ....time import parse_datetime

	#TODO: remove or rename ISW
	## Options: TEST,ISW,KNO,INST,KNST,POS,XNEAR,XFAR,KAZ,KTEST,SINGMD,IPRN
	IPRN = verbose - 1

	if fix_origin:
		INST = 9
	elif fix_depth:
		INST = 1
	else:
		INST = 0

	KAZ = azimuthal_weighting
	KNST = use_s_picks
	KTEST = compute_auxilliary_rms
	SINGMD = apply_al_lindh_mod

	POS = vp_vs_ratio

	KNO = 1

	TEST = np.zeros(20, dtype='f')
	TEST[0] = min_rms_jeffrey
	TEST[1] = max_horizontal_adjustment_for_depth_adjustment
	TEST[2] = f_crit
	TEST[3] = min_hypocentral_adjustment
	TEST[4] = max_depth_adjustment
	TEST[5] = f_crit_divisor
	## TEST[6,7,8] are related to magnitude calculation, not used here
	TEST[9] = max_horizontal_adjustment
	TEST[10] = max_num_iterations
	TEST[11] = depth_above_max_altitude_adjustment
	TEST[12] = 1.  ## radius for calculation of auxilliary RMS
	TEST[13] = min_num_phases	## new option
	TEST[14] = -max_altitude  ## seiscomp only
	TEST[19] = 1  ## seiscomp option for scaling station elevations, not used here

	## Crustal velocity model: NL,V,D,(G,F,TID,DID)
	NL = len(velocity_model)
	NLMAX = 21
	assert NL <= NLMAX

	D = np.zeros(NLMAX, dtype='f')
	D[:NL] = velocity_model.depths

	NV = 2
	V = np.asfortranarray(np.zeros((NV, NLMAX), dtype='f'))
	for W, wave in enumerate(('P', 'S')):
		V[W,:NL] = velocity_model.get_velocities(wave=wave)

	## Create structured array with station and phase data
	station_phases = StationPhases(stations, pick_dict, use_s_picks=True)

	## Station information: NS,IW,NSTA,LAT,LON,INS,IEW,elev,MNO,DLY,FLT,JDX
	NSMAX = 201
	NRMAX = 501
	NS = station_phases.num_stations
	assert NS <= NSMAX

	IW = np.zeros(NSMAX, dtype='|S1')  ## if '*', station has zero weight
	IW[:] = b' '
	for s in range(len(stations)):
		if not s in station_phases.IDXS:
			IW[s] = b'*'

	NSTA = np.zeros((NSMAX, 4), dtype='|S1')
	NSTA[:NS] = ' '
	for s, code in enumerate(station_phases.stat_codes):
		code = str(code)
		#code = bytes(code, encoding='ascii')
		## Remove country code
		code = code[code.find('.')+1:]
		NSTA[s,:min(4,len(code))] = list(code[:4])
	#print('NSTA', NSTA[:NS])

	## Note: lon, lat in (signed!) degrees, negative elevations
	LON = np.zeros(NSMAX, dtype='f')
	LON[:NS] = station_phases.stat_lons * 60
	LAT = np.zeros(NSMAX, dtype='f')
	LAT[:NS] = station_phases.stat_lats * 60

	## Different ways to handle station elevation/depth
	ELEV = np.zeros(NRMAX, dtype='f')
	if station_elevation == 'absolute':
		ELEV[:NS] = -station_phases.stat_elevs
	elif station_elevation == 'relative':
		mean_elev = np.mean(station_phases.stat_elevs)
		ELEV[:NS] = mean_elev - station_phases.stat_elevs
	elif station_elevation == 'depth':
		ELEV[:NS] = station_phases.stat_depths
	elif station_elevation == 'zero':
		ELEV[:NS] = np.zeros(NS)
	#print('ELEV', ELEV[:NS])

	## N/S E/W only used for printing
	INS = np.zeros(NSMAX, dtype='|S1')
	INS[:] = b'N'
	INS[LAT < 0] = b'S'
	IEW = np.zeros(NSMAX, dtype='|S1')
	IEW[:] = b'E'
	IEW[LON < 0] = b'W'

	MNO = np.ones(NSMAX, dtype='f')
	DLY = np.asfortranarray(np.zeros((2, NSMAX)))
	FLT = np.asfortranarray(np.zeros((2, NSMAX), dtype='f'))  ## not used
	JDX = np.ones(NSMAX, dtype='int')  ## not used

	## Phase information: NR,KDX,LDX,MSTA,JMIN,PRMK,W,P,NRP,SRMK,WS,S,DT,WRK,KSMP
	NR = station_phases.num_phases
	assert NR <= NRMAX
	NRP = station_phases.num_p_phases
	NRS = station_phases.num_s_phases
	if verbose:
		print('Using %d phases: %d P + %d S' % (NR, NRP, NRS))

	PIDXS = station_phases.PIDXS
	SIDXS = station_phases.SIDXS

	KDX = np.zeros(NRMAX, dtype='int')
	KDX[:NR] = station_phases.IDXS + 1
	#print('KDX', KDX[:NR])

	LDX = np.zeros(NRMAX, dtype='int')
	#LDX[:NRP] = SIDXS
	LDX[NRP:NR] = 1
	#print('LDX', LDX[:NR])

	PMIN = UTCDateTime(np.nanmin(station_phases.Ptimes))
	PMIN = PMIN - (PMIN.minute * 60 + PMIN.second + PMIN.microsecond * 1E-6)
	#print('PMIN', PMIN)
	KDATE = (PMIN.year - (PMIN.year // 100)) * 100 + PMIN.month * 100 + PMIN.day
	KHR = PMIN.hour
	Ptimes = [UTCDateTime(t) for t in station_phases.Ptimes[PIDXS]]
	Stimes = [UTCDateTime(t) for t in station_phases.Stimes[SIDXS]]
	Pdiffs = np.array([t - PMIN for t in Ptimes])
	Sdiffs = np.array([t - PMIN for t in Stimes])
	#print('Pdiffs', Pdiffs[:NR])
	#print('Sdiffs', Sdiffs[:NR])
	JMIN = np.zeros(NRMAX, dtype='int')
	JMIN[:NRP] = [dt // 60 for dt in Pdiffs]
	JMIN[NRP:NR] = [dt // 60 for dt in Sdiffs]
	#print('JMIN', JMIN[:NR])
	P = np.zeros(NRMAX, dtype='f')
	S = np.zeros(NRMAX, dtype='f')
	P[:NRP] = Pdiffs - JMIN[:NRP] * 60
	S[:NRS] = Sdiffs - JMIN[NRP:NR] * 60
	#print('P', P[:NRP])
	#print('S', S[:NRS])

	W = np.zeros(NRMAX, dtype='f')
	W[:NRP] = station_phases.stat_weights[PIDXS] * station_phases.data['Pweight'][PIDXS]
	#print('W', W[:NRP])
	WS = np.zeros(NRMAX, dtype='f')
	WS[:NRS] = station_phases.stat_weights[SIDXS] * station_phases.data['Sweight'][SIDXS]
	#print('WS', WS[:NRS])

	## Note: 4th character is weight code (not used)
	PRMK = np.zeros((NRMAX, 4), dtype='|S1')
	PRMK[:] = b'    '
	PRMK[:NRP,1] = b'P'
	PRMK[:NRP,3] = b'0'
	SRMK = np.zeros((NRMAX, 4), dtype='|S1')
	SRMK[:] = b'    '
	SRMK[:NRS,1] = b'S'
	SRMK[:NRS,3] = b'0'

	DT = np.zeros(NRMAX, dtype='f')
	KSMP = np.zeros(NSMAX, dtype='int')
	WRK = np.zeros((NRMAX, 4), dtype='|S1')

	## Calculated in single.f
	#TP = np.zeros(NSMAX, dtype='f')
	#TS = np.zeros(NSMAX, dtype='f')
	#TP[:NRP] = 60 * JMIN[:NRP] + P[:NRP] + DT[:NRP]
	#TS[:NRS] = 60 * JMIN[NRP:NR] + S[:NRS] + DT[NRP:NR]

	## Summary of residuals: NRES,SR,SRSQ,SRWT,QNO
	NRES = np.asfortranarray(np.zeros((2, NSMAX), dtype='f'))
	SR = np.asfortranarray(np.zeros((2, NSMAX), dtype='f'))
	SRSQ = np.asfortranarray(np.zeros((2, NSMAX), dtype='f'))
	SRWT = np.asfortranarray(np.zeros((2, NSMAX), dtype='f'))
	QNO = np.zeros(4, dtype='f')

	## ORG1,ORG2,LAT1,LAT2,LON1,LON2,ZTR
	ORG1 = ORG2 = 0.
	LON1 = LON2 = LAT1 = LAT2 = 0.
	if origin:
		LONEP, LATEP, _ORG = origin
		## LON1/LAT1: degrees, LON2/LAT2: minutes
		LON1 = np.floor(LONEP)
		LON2 = (LONEP - LON1) * 60
		LAT1 = np.floor(LATEP)
		LAT2 = (LATEP - LAT1) * 60
		if _ORG:
			ORG = parse_datetime(_ORG)
			dt = ORG - PMIN
			## ORG1: minutes, ORG2: seconds
			ORG1 = dt // 60
			ORG2 = dt - ORG1 * 60

	## Output results: LATEP,LONEP,Z,ORG,SE,RMS,QSD,X,DELTA,AZ,AIN,WT
	SE = np.zeros(4, dtype='f')
	#QSD = np.zeros(2, dtype='|S1')
	X = np.asfortranarray(np.zeros((4, NRMAX), dtype='f'))
	DELTA = np.zeros(NRMAX, dtype='f')
	AZ = np.zeros(NRMAX, dtype='f')
	AIN = np.zeros(NRMAX, dtype='f')
	WT = np.zeros(NRMAX, dtype='f')
	AZWT = np.zeros(NRMAX, dtype='f')

	(LATEP,LONEP,Z,ORG,RMS,QSD,NI) = single(
					NS,IW,NSTA,LAT,LON,INS,IEW,ELEV,MNO,DLY,FLT,JDX,
					NL,V,D,
					KDATE,KHR,
					NR,KDX,LDX,JMIN,PRMK,W,P,NRP,SRMK,WS,S,DT,WRK,KSMP,
					NRES,SR,SRSQ,SRWT,QNO,
					ORG1,ORG2,LAT1,LAT2,LON1,LON2,ZTR,
					TEST,ISW,KNO,INST,KNST,POS,XNEAR,XFAR,KAZ,KTEST,SINGMD,IPRN,
					SE,X,DELTA,AZ,AIN,WT,AZWT)

	LONEP /= 60.
	LATEP /= 60.
	ORG = PMIN + ORG
	QSD = ''.join([c.decode('ascii') for c in QSD[:,0]])

	#print(LONEP, LATEP, Z, ORG)
	#print('NI: ', NI)

	station_phases.data.loc[PIDXS, 'takeoff_angle'] = AIN[:NRP]
	station_phases.data.loc[SIDXS, 'takeoff_angle'] = AIN[NRP:NR]
	station_phases.data.loc[PIDXS, 'azimuth'] = np.round(AZ[:NRP])
	station_phases.data.loc[SIDXS, 'azimuth'] = np.round(AZ[NRP:NR])
	station_phases.data.loc[PIDXS, 'Repi'] = DELTA[:NRP]
	station_phases.data.loc[SIDXS, 'Repi'] = DELTA[NRP:NR]
	station_phases.data.loc[PIDXS, 'Rhypo'] = np.hypot(DELTA[:NRP], Z)
	station_phases.data.loc[SIDXS, 'Rhypo'] = np.hypot(DELTA[NRP:NR], Z)
	station_phases.data.loc[PIDXS, 'az_weight'] = AZWT[:NRP]
	station_phases.data.loc[SIDXS, 'az_weight'] = AZWT[NRP:NR]
	#station_phases.data.loc['dist_weight'][IDXS] = DWT
	station_phases.data.loc[PIDXS, 'Pres'] = X[3][:NRP]
	station_phases.data.loc[SIDXS, 'Sres'] = X[3][NRP:NR]
	station_phases.data.loc[PIDXS, 'Ptot_weight'] = WT[:NRP]
	station_phases.data.loc[SIDXS, 'Stot_weight'] = WT[NRP:NR]

	ERH = np.sqrt(SE[0]**2 + SE[1]**2)

	return (LONEP, LATEP, Z, ORG, SE, station_phases, QSD, NI)
