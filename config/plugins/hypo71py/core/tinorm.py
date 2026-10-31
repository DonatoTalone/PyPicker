"""
"""

import numpy as np


def TINORM(ALPHA):
	"""
	APPROXIMATION TO INVERSE CDF OF STANDARD NORMAL DISTRIBUTION
	"""
	A = np.array([.010328, .802853, 2.515517])
	B = np.array([.0010308, .189269, 1.432788])

	ALPHA = np.asarray(ALPHA)

	assert ((ALPHA > 0) & (ALPHA < 1)).all()

	X = ALPHA.copy()
	over_half_idxs = ALPHA > .5
	X[over_half_idxs] = 1 - X[over_half_idxs]
	X = np.sqrt(-2 * np.log(X))

	TINORM = X - (A[2]+X*(A[1]+X*A[0])) / (1.+X*(B[2]+X*(B[1]+X* B[0])))
	TINORM = np.asarray(TINORM)
	below_half_idxs = ALPHA < .5
	TINORM[below_half_idxs] = -TINORM[below_half_idxs]

	return TINORM



if __name__ == "__main__":
	import pylab

	alpha1 = np.linspace(0, 1, 1000)[1:-1]
	tinorm1 = TINORM(alpha1)
	pylab.plot(alpha1, tinorm1)
	alpha2 = np.random.sample(1000)
	tinorm2 = TINORM(alpha2)
	pylab.plot(alpha2, tinorm2, 'ro')
	pylab.show()
