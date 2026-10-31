"""
Wrapper for Fortran version of SWMREG
"""

import numpy as np

from .swmreg import swmreg


def SWMREG(X, W, KSMP, FNO, ISKP, KF, KZ,
			f_crit=2., f_crit_divisor=4., verbose=False):
	"""
	"""
	test = np.zeros(15, dtype='f')
	test[2] = f_crit
	test[5] = f_crit_divisor

	if verbose:
		iprn = 3
	else:
		iprn = 0

	NSMAX = 201
	NRMAX = 501

	assert len(KSMP) <= NSMAX
	ksmp = np.zeros(NSMAX, 'i')
	ksmp[:len(KSMP)] = KSMP

	nr = X.shape[-1]
	assert nr <= NRMAX
	x = np.zeros((4, NRMAX), dtype='f')
	x[:,:nr] = X
	w = np.zeros(NRMAX, dtype='f')
	w[:nr] = W

	fno = FNO
	iskp = ISKP.astype('i')
	kf, kz = KF, KZ

	xmean = np.zeros(4, dtype='f')
	b = np.zeros(4, dtype='f')
	y = np.zeros(4, dtype='f')
	bse = np.zeros(4, dtype='f')
	af = np.zeros(3, dtype='f')
	onf = 0.

	flim = swmreg(test, iprn, nr, ksmp, fno, x, w, iskp, kf, kz,
					xmean, b, y, bse, af, onf)

	return (xmean, y, bse, flim)
