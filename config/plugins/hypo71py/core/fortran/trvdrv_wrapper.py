"""
Wrapper for Fortran version of TRVDRV
"""

import numpy as np

from .trvdrv import trvdrv


def TRVDRV(velocity_model, Z, DELTA, ELEV, VIDXS, ISW='', verbose=False):
	"""
	Same arguments as python version
	"""
	isw = ISW

	## Velocity model
	nl = len(velocity_model)
	NLMAX = 21
	assert nl <= NLMAX

	d = np.zeros(NLMAX, dtype='f')
	d[:nl] = velocity_model.depths
	depth = d.copy()
	thk = np.zeros(NLMAX, dtype='f')
	thk[:nl-1] = velocity_model.thicknesses
	h = thk.copy()

	nv = 2
	v = np.asfortranarray(np.zeros((nv, NLMAX), dtype='f'))
	for W, wave in enumerate(('P', 'S')):
		v[W,:nl] = velocity_model.get_velocities(wave=wave)
	vsq = v * v

	## F and G terms
	g = np.asfortranarray(np.zeros((nv, 4, NLMAX), dtype='f'))  ## not used
	f = np.asfortranarray(np.zeros((NLMAX, NLMAX), dtype='f'))
	for J in range(NLMAX):
		for L in range(NLMAX):
			f[L,J] = 1
			if L >= J:
				f[L,J] = 2

	NSMAX = 201
	flt = np.asfortranarray(np.zeros((2, NSMAX), dtype='f'))
	kno = 1
	fltep = 0.

	z = Z
	zsq = z * z

	## TID and DID
	## Not necessary to populate:
	## seiscomp version of TRVDRV recomputes these arrays as txd and dxd
	tid = np.asfortranarray(np.zeros((nv, NLMAX, NLMAX), dtype='f'))
	did = np.asfortranarray(np.zeros((nv, NLMAX, NLMAX), dtype='f'))
	"""
	for KV in range(nv):
		for LR in range(1, nl):
			## LR: index of layer below bottom layer
			for LS in range(nl):
				## LS: index of top layer
				for LL in range(LS, LR):
					## LL: layers in between
					SQT = np.sqrt(vsq[KV,LR] - vsq[KV,LL])
					TIM = thk[LL] / v[KV,LL] * v[KV,LR] / SQT
					DIM = thk[LL] * v[KV,LL] / SQT
					tid[KV,LS,LR] += TIM
					did[KV,LS,LR] += DIM
	"""

	## Station (= phase) distances and elevations
	NRMAX = 501
	nr = len(DELTA)
	assert nr <= NRMAX
	kdx = np.arange(1, NRMAX+1, dtype='i')
	nrp = np.sum(VIDXS == 0)

	## Note: TRVDRV assumes that S phases follow P phases
	pidxs = (VIDXS == 0)
	sidxs = (VIDXS == 1)

	delta = np.zeros(NRMAX, dtype='f')
	delta[:nrp] = DELTA[pidxs]
	delta[nrp:nr] = DELTA[sidxs]

	dx = np.ones(NRMAX, dtype='f')
	dy = np.ones(NRMAX, dtype='f')

	elev = np.zeros(NRMAX, dtype='f')
	elev[:nrp] = ELEV[pidxs]
	elev[nrp:nr] = ELEV[sidxs]

	## Result arrays
	x = np.asfortranarray(np.zeros((4, NRMAX), dtype='f'))
	t = np.zeros(NRMAX, dtype='f')
	anin = np.zeros(NRMAX, dtype='f')

	trvdrv(isw, v, d, depth, vsq, nl, thk, h, g, f, tid, did, flt,
			delta, dx, dy, elev, nr, kdx, kno, fltep, z, zsq,
			nv, nrp, x, t, anin)

	## Reorder output to match input
	T = np.zeros(nr, dtype='f')
	X = np.zeros((4, nr), dtype='f')
	ANIN = np.zeros(nr, dtype='f')

	X[:3, pidxs] = x[:3, :nrp]
	X[:3, sidxs] = x[:3, nrp:nr]
	T[pidxs] = t[:nrp]
	T[sidxs] = t[nrp:nr]
	ANIN[pidxs] = anin[:nrp]
	ANIN[sidxs] = anin[nrp:nr]

	## Convert ANIN to angle of incidence in degrees
	AIN = np.degrees(np.arcsin(ANIN))
	AIN[AIN < 0] = 180 + AIN[AIN < 0]
	AIN = 180 - AIN

	return (T, X, AIN)
