"""
Translation of SWMREG subroutine
"""

from __future__ import absolute_import, division, print_function

import numpy as np


__all__ = ['SWMREG']


#      SUBROUTINE SWMREG(TEST,IPRN,NR,KSMP,FNO,X,W,ISKP,KF,KZ,XMEAN,
#     &  B,Y,BSE,AF,ONF,FLIM)

def SWMREG(X, W, KSMP, FNO, ISKP, KF, KZ,
			f_crit=2., f_crit_divisor=4., verbose=False):
	"""
	------- COMPUTE GEIGER ADJUSTMENTS BY STEP-WISE MULTIPLE REGRESSION OF
			TRAVEL TIME RESIDUALS -----------------------------------------

	:param X:
		2D array, travel time derivatives and phase residuals [4, num_phases]
		0 = X
		1 = Y
		2 = Z
		3 = Time
	:param W:
		1D array, phase weights [num_phases]
	:param KSMP:
		1D array indicating whether residuals are S-P intervals (1) or not (0)
		[num_phases]
	:param FNO:
		float, number of non-zero-weight phases
	:param ISKP:
		1D array [4], containing 0 or 1
		whether or not to skip a particular type of residual
	:param KF:
		int, ?
		0 =
		2 = solve full normal equation
	:param KZ:
		int, whether or not depth is fixed
		0 = free depth
		1 = fixed depth
	:param f_crit:
		float, critical F-value for the stepwise multiple regression.
		Should be set according to the number and quality of P- and S-
		arrivals. A value between 0.5 and 2 is recommended.
		If set to zero, a simple multiple regression is performed
		regardless of whether the matrix is ill-conditioned. This is
		not desirable because the hypocenter solution may be meaningless.
		On the other hand, if it is set to 2 or greater, then Geiger's
		iteration may be terminated prematurely, before a good hypocenter
		is found.
		Corresponds to TEST[03] option in original program
		(default: 2.)
	:param f_crit_divisor:
		float, division factor for :param:`f_crit` if no significant
		variable is found in the stepwise multiple regression. In that
		case, f_crit is reduced to f_crit / f_crit_divisor, and the
		regression is repeated. If it is <= 1, then the regression is
		repeated to find one variable, and the adjustment is made only
		if it is greater than f_crit_divisor * standard error.
		If :param:`f_crit` is set to less than 2, then f_crit_divisor
		should be set to 1.
		Corresponds to TEST[06] option in original program
		(default: 4.)
	:param verbose:
		bool, whether or not to print details about stepwise multiple
		regression.
		Corresponds to IPRN=3 option in original program.
		(default: False)

	:return:
		(XMEAN, Y, BSE, FLIM):
		- XMEAN: 1D array [4], means (of what?)
		- Y: 1D array [4], XYZ (and time) adjustments
		- BSE: 1D array [4], standard errors?
		- FLIM: float, final value of f_crit
	"""
	## Not explicitly initialized in original program
	SIGMA = np.zeros(4, dtype='f')
	T = np.zeros((7,7), dtype='f')
	V = np.zeros(3, dtype='f')
	PF = np.zeros(3, dtype='f')

	#      DATA L,M,MM,M1/3,4,7,5/

	L, M, MM, M1 = 3, 4, 7, 5
	NR = X.shape[-1]

	#      KFLAG=0
	#      SVTEST = TEST(3)
	#      ONF=0.0
	#      FLIM = TEST(3)
	#      DO 2 I=1,3
	#      AF(I)=-1.00
	#    2 CONTINUE
	#      DO 5 I=1,NR
	#      ONF=ONF + W(I)*(1-KSMP(I))
	#    5 CONTINUE
	#      DO 10 I=1,MM
	#      DO 10 J=1,MM
	#   10 A(I,J)=0.

	KFLAG = 0
	SVTEST = f_crit
	FLIM = f_crit
	AF = -np.ones(3, dtype='f')
	ONF = np.sum(W * (1 - KSMP))
	A = np.zeros((MM, MM), dtype='f')

	#C-----COMPUTE MEANS,STANDARD DEVIATIONS,AND CORRECTED SUMS OF SQUARE
	#      DO 40 I=1,M
	#      XSUM(I)=0.
	#      XMEAN(I)=0.
	#      DO 40 J=1,M
	#   40 S(I,J)=0.

	#      DO 50 K=1,NR
	#      DO 50 I=1,M
	#      TEMP=X(I,K)*W(K)
	#      ETMP=TEMP*(1-KSMP(K))
	#      XSUM(I)=XSUM(I)+ETMP
	#      DO 50 J=I,M
	#   50 S(I,J)=S(I,J)+TEMP*X(J,K)

	#      DO 70 I=1,M
	#      IF (ONF .EQ. 0.) GO TO 65
	#      XMEAN(I)=XSUM(I)/ONF
	#      DO 60 J=I,M
	#   60 S(I,J)=S(I,J)-XSUM(I)*XSUM(J)/ONF
	#   65 A(I,I)=1.
	#      IF (S(I,I) .LT. 0.000001) S(I,I)=0.000001
	#      SIGMA(I)=SQRT(S(I,I))
	#   70 CONTINUE

	## -----COMPUTE MEANS,STANDARD DEVIATIONS,AND CORRECTED SUMS OF SQUARE
	XSUM = np.zeros(M, dtype='f')
	XMEAN = np.zeros(M, dtype='f')
	S = np.zeros((M, M), dtype='f')

	for K in range(NR):
		for I in range(M):
			TEMP = X[I,K] * W[K]
			ETMP = TEMP * (1 - KSMP[K])
			XSUM[I] += ETMP
			for J in range(I, M):
				S[I,J] += (TEMP * X[J,K])

	for I in range(M):
		if ONF != 0:
			XMEAN[I] = XSUM[I] / ONF
			for J in range(I, M):
				S[I,J] -= (XSUM[I] * XSUM[J] / ONF)
		A[I,I] = 1.
		S[I,I] = max(S[I,I], 0.000001)
		SIGMA[I] = np.sqrt(S[I,I])

	#C-----COMPUTE AND AUGMENT CORRELATION MATRIX A
	#      DO 80 I=1,L
	#      I1=I+1
	#      DO 80 J=I1,M
	#      A(I,J)=S(I,J)/(SIGMA(I)*SIGMA(J))
	#   80 A(J,I)=A(I,J)
	#      PHI=FNO-1.
	#      DO 120 I=M1,MM
	#      A(I-M,I)=1.
	#  120 A(I,I-M)=-1.
	#      DO 140 I=1,M
	#      B(I)=0.
	#      Y(I)=0.
	#      BSE(I)=0.
	#  140 IDX(I)=0

	## -----COMPUTE AND AUGMENT CORRELATION MATRIX A
	for I in range(L):
		I1 = I + 1
		for J in range(I1, M):
			A[I,J] = S[I,J] / (SIGMA[I] * SIGMA[J])
			A[J,I] = A[I,J]

	PHI = FNO - 1.
	for I in range(M1-1, MM):
		A[I-M,I] = 1
		A[I,I-M] = -1

	B = np.zeros(M, dtype='f')
	Y = np.zeros(M, dtype='f')
	BSE = np.zeros(M, dtype='f')
	IDX = np.zeros(M, dtype=np.int64)

	if verbose:
		print('***** DATA *****')
		print('    K        W              X1'
			'              X2              X3              X4')
		for K in range(NR):
			print('%5d%16.8E%s'
				% (K, W[K], ''.join(['%16.8E' % val for val in X[:,K]])))
		print(' MEAN                %s'
				% ''.join(['%16.8E' % XMEAN[I] for I in range(M)]))
		print(' SIGMA               %s'
				% (''.join(['%16.8E' % SIGMA[I] for I in range(M)])))
		print(' ***** CORRECTED SUMS OF SQUARES MATRIX *****')
		for I in range(M):
			print(''.join(['%18.8E' % S[I,J] for J in range(M)]))
		print(' ***** CORRELATION MATRIX R *****')
		for I in range(M):
			print(''.join(['%18.8E' % A[I,J] for J in range(M)]))
		print('********** STEPWISE MULTIPLE REGRESSION ANALYSIS **********')
		print(' NUMBER OF DATA....................%5d' % NR)
		print(' NUMBER OF INDEPENDENT VARIABLES...%5d' % L)
		print(' CRITICAL F-VALUE..................%8.2f' % f_crit)

	#  150 DO 300 NSTEP=1,L
	#      NU=0
	#      MU=0
	#      IF (IPRN .LT. 3) GO TO 155
	#      WRITE(8,154) NSTEP,KZ,KF
	#  154 FORMAT(//,' ***** STEP NO.',I2,' *****',5X,'KZ =',I2,5X,'KF =',I2)
	#C-----FIND VARIABLE TO ENTER REGRESSION
	#  155 VMAX=0.
	#      MAX=NSTEP
	#      DO 160 I=1,L
	#      IF(ISKP(I).EQ.1) GO TO 160
	#      IF (IDX(I) .EQ. 1) GO TO 160
	#      IF ((I.EQ.3).AND.(KZ.EQ.1)) GO TO 160
	#      V(I)=A(I,M)*A(M,I)/A(I,I)
	#      IF (V(I) .LE. VMAX) GO TO 160
	#      VMAX=V(I)
	#      MAX=I
	#  160 CONTINUE
	#      F=0.0
	#      IF(VMAX.EQ.0.0) GO TO 163
	#      IF(VMAX.EQ.A(M,M)) THEN
	#         F=1000.
	#      ELSE
	#         F=(PHI-1.)*VMAX/(A(M,M)-VMAX)
	#      END IF
	#      IF(F .GE. 1000.) F=999.99
	#  163 AF(MAX)=F

	#      IF(KF .GE. 2) GO TO 165
	#      IF (F .LT. TEST(3)) GO TO 400
	#  165 IF ((MAX.EQ.3).AND.(KZ.EQ.1)) GO TO 300
	#      NU=MAX
	#      IDX(NU)=1
	#      PHI=PHI-1.

	while True:
		GOTO450 = False
		for NSTEP in range(L):
			## -----FIND VARIABLE TO ENTER REGRESSION
			#NU, MU = 0, 0
			NU, MU = -1, -1
			if verbose:
				print(' ***** STEP NO.%2d *****    KZ =%2d     KF =%2d'
						% (NSTEP, KZ, KF))
			VMAX = 0.
			MAX = NSTEP
			for I in range(L):
				#if ISKP[I] == 1:
				#	continue
				#if IDX[I] == 1:
				#	continue
				#if (I == 2 and KZ == 1):
				#	continue
				if not (ISKP[I] == 1 or IDX[I] == 1 or (I == 2 and KZ == 1)):
					V[I] = A[I,M-1] * A[M-1,I] / A[I,I]
					if V[I] > VMAX:
						VMAX = V[I]
						MAX = I
			F = 0.
			if not np.isclose(VMAX, 0):
				if np.isclose(VMAX, A[M-1,M-1]):
					F = 1000.
				else:
					F = (PHI - 1.) * VMAX / (A[M-1,M-1] - VMAX)
				if F >= 1000:
					F = 999.99
			AF[MAX] = F

			#GOTO400 = False
			if KF < 2:
				if F < f_crit:
					# GOTO 400
					#GOTO400 = True
					GOTO450 = False
					break

			#if not GOTO400:
			if (MAX == 2 and KZ == 1):
				# GOTO 300
				continue

			NU = MAX
			IDX[NU] = 1
			PHI -= 1.

			#C-----COMPUTE MATRIX T FOR THE ENTRANCE OF VARIABLE X(NU)
			#      DO 170 J=1,MM
			#  170 T(NU,J)=A(NU,J)/A(NU,NU)
			#      DO 180 I=1,MM
			#      IF (I .EQ. NU) GO TO 180
			#      DO 175 J=1,MM
			#  175 T(I,J)=A(I,J)-A(I,NU)*A(NU,J)/A(NU,NU)
			#  180 CONTINUE
			#      DO 190 I=1,MM
			#      DO 190 J=1,MM
			#  190 A(I,J)=T(I,J)
			#      DO 200 I=1,L
			#      IF (IDX(I) .EQ. 0) GO TO 200
			#      IF (ABS(A(M,M)*A(I+M,I+M)) .LT. .000001 ) GO TO 195
			#      PF(I)=PHI*A(I,M)**2/(A(M,M)*A(I+M,I+M))
			#      IF(PF(I) .GE. 1000.0) PF(I)=999.99
			#      AF(I) = PF(I)
			#      GO TO 200
			#  195 PF(I) = 999.99
			#  200 CONTINUE
			#      IF (IPRN .LT. 3) GO TO 210
			#      CALL ANSWER(A,S,XMEAN,SIGMA,IDX,PHI,L,M,MM,PF,NU,'ENTERING')
			#  210 IF (KF .EQ. 2) GO TO 300
			#      IF(KF .GE. 3) GO TO 450

			## -----COMPUTE MATRIX T FOR THE ENTRANCE OF VARIABLE X(NU)
			for J in range(MM):
				T[NU,J] = A[NU,J] / A[NU,NU]
			for I in range(MM):
				if I != NU:
					for J in range(MM):
						T[I,J] = A[I,J] - A[I,NU] * A[NU,J] / A[NU,NU]
			A[:] = T
			for I in range(L):
				if IDX[I] != 0:
					if abs(A[M-1,M-1] * A[I+M,I+M]) >= .000001:
						PF[I] = PHI * A[I,M-1]**2 / (A[M-1,M-1] * A[I+M,I+M])
						PF[I] = min(PF[I], 999.99)
						AF[I] = PF[I]
					else:
						PF[I] = 999.99

			if verbose:
				ANSWER(A, S, XMEAN, SIGMA, IDX, PHI, L, M, MM, PF, NU, 'ENTERING')

			if KF == 2:
				continue
			if KF >= 3:
				# GOTO 450 = break out of while loop
				GOTO450 = True
				break

			#C-----FIND VARIABLE TO LEAVE REGRESSION
			#      DO 250 K=1,L
			#      IF (IDX(K) .EQ. 0) GO TO 250
			#      IF (PF(K) .GE. TEST(3)) GO TO 250
			#      MU=K
			#      F=PF(MU)
			#      IDX(MU)=0
			#      PHI=PHI+1.
			#      DO 220 J=1,MM
			#  220 T(MU,J)=A(MU,J)/A(MU+M,MU+M)
			#      DO 230 I=1,MM
			#      IF (I .EQ. MU) GO TO 230
			#      DO 225 J=1,MM
			#      IF (J .EQ. MU) GO TO 225
			#      T(I,J)=A(I,J)-A(I,MU+M)*A(MU+M,J)/A(MU+M,MU+M)
			#  225 CONTINUE
			#  230 CONTINUE
			#      DO 240 I=1,MM
			#      IF (I .EQ. MU) GO TO 240
			#      T(I,MU)=A(I,MU)-A(I,MU+M)/A(MU+M,MU+M)
			#  240 CONTINUE
			#      DO 245 I=1,MM
			#      DO 245 J=1,MM
			#  245 A(I,J)=T(I,J)
			#      IF (IPRN .LT. 3) GO TO 250
			#      CALL ANSWER(A,S,XMEAN,SIGMA,IDX,PHI,L,M,MM,PF,MU,'LEAVING')
			#  250 CONTINUE
			#  300 CONTINUE

			## -----FIND VARIABLE TO LEAVE REGRESSION
			for K in range(L):
				if IDX[K] == 0:
					continue
				if PF[K] >= f_crit:
					continue

				MU = K
				F = PF[MU]
				IDX[MU] = 0
				PHI += 1.
				for J in range(MM):
					T[MU,J] = A[MU,J] / A[MU+M,MU+M]

				for I in range(MM):
					if I != MU:
						for J in range(MM):
							if J != MU:
								T[I,J] = A[I,J] - A[I,MU+M] * A[MU+M,J] / A[MU+M,MU+M]

				for I in range(MM):
					if I != MU:
						T[I,MU] = A[I,MU] - A[I,MU+M] / A[MU+M,MU+M]

				A[:] = T

				if verbose:
					ANSWER(A, S, XMEAN, SIGMA, IDX, PHI, L, M, MM, PF, MU, 'LEAVING')

		## If for loop was broken because KF >= 3, break out of while loop
		if GOTO450:
			break

		#C-----CHECK TERMINATION CONDITION
		#  400 KOUT=0
		#      DO 410 I=1,L
		#  410 KOUT=KOUT+IDX(I)
		#      B(4)=XMEAN(M)
		#      IF (KOUT .NE. 0) GO TO 450
		#      IF(KF .NE. 1) GO TO 420
		#      KF = 3
		#      GO TO 150
		#  420 TEST(3)= TEST(3)/TEST(6)
		#      FLIM=TEST(3)
		#      KF=1
		#      KFLAG = 0
		#      IF(TEST(6) .GT. 1.) GO TO 150
		#      KFLAG = 1
		#      KF = 4
		#      GO TO 150

		## -----CHECK TERMINATION CONDITION
		KOUT = np.sum(IDX[:L])
		#print('KOUT', KOUT)
		B[3] = XMEAN[M-1]
		if KOUT != 0:
			break
		if KF == 1:
			KF = 3
			continue
		f_crit /= float(f_crit_divisor)
		FLIM = f_crit
		KF = 1
		KFLAG = 0
		if f_crit_divisor > 1:
			continue
		KFLAG = 1
		KF = 4

	#C-----COMPUTE REGRESSION CONSTANT,COEFFICIENTS,AND STANDARD ERRORS
	#  450 YSE=77.7
	#      IF (PHI .GE. 1) YSE=SIGMA(M)*SQRT(ABS(A(M,M)/PHI))
	#      DO 500 I=1,L
	#      IF (IDX(I) .EQ. 0) GO TO 500
	#      B(I)=A(I,M)*SQRT(S(M,M)/S(I,I))
	#      BSE(I)=YSE*SQRT(ABS(A(I+M,I+M)/S(I,I)))
	#      IF(KF .NE. 3) Y(I)=B(I)
	#      IF(KFLAG .EQ. 0) GO TO 480
	#      IF(ABS(B(I)) .LE. TEST(6)*BSE(I)) Y(I)=0.
	#  480 IF(PHI .LT. 1.) BSE(I) = 0.
	#      B(4)=B(4)-Y(I)*XMEAN(I)
	#  500 CONTINUE
	#      IF(KF .NE. 3) Y(4)=B(4)
	#      TEST(3)=SVTEST
	#      RETURN
	#      END

	## ----COMPUTE REGRESSION CONSTANT,COEFFICIENTS,AND STANDARD ERRORS
	YSE = 77.7
	if PHI >= 1:
		YSE = SIGMA[M-1] * np.sqrt(abs(A[M-1,M-1] / PHI))
	for I in range(L):
		if IDX[I] != 0:
			B[I] = A[I,M-1] * np.sqrt(S[M-1,M-1] / S[I,I])
			BSE[I] = YSE * np.sqrt(abs(A[I+M,I+M] / S[I,I]))
			if KF != 3:
				Y[I] = B[I]
			if KFLAG != 0:
				if abs(B[I]) <= f_crit_divisor * BSE[I]:
					Y[I] = 0
			if PHI < 1:
				BSE[I] = 0
			B[3] -= (Y[I] * XMEAN[I])

	if KF != 3:
		Y[3] = B[3]
	f_crit = SVTEST

	#return (XMEAN, B, Y, BSE, AF, ONF, FLIM)
	#if np.allclose(Y, 0):
	#	print('B', B)
	return (XMEAN, Y, BSE, FLIM)


#      SUBROUTINE ANSWER(A,S,XMEAN,SIGMA,IDX,PHI,L,M,MM,PF,NDX,ADX)

def ANSWER(A, S, XMEAN, SIGMA, IDX, PHI, L, M, MM, PF, NDX, ADX):
	"""
	------- PRINT INTERMEDIATE RESULTS OF REGRESSION ANALYSIS (SWMREG) ---
	"""

	#      DO 410 I=1,MM
	#      WRITE(8,400) (A(I,J),J=1,MM)
	#  400 FORMAT(7E18.8)
	#  410 CONTINUE
	#      FVE=1.-A(M,M)
	#      B0=XMEAN(M)
	#      YSE=77.7
	#      IF (PHI .GE. 1) YSE=SIGMA(M)*SQRT(ABS(A(M,M)/PHI))
	#      DO  5 I=1,L
	#      IF (IDX(I).EQ.0) GO TO  5
	#      B(I)=A(I,M)* SQRT(ABS(S(M,M)/S(I,I)))
	#      BSE(I)=YSE* SQRT(ABS(A(I+M,I+M)/S(I,I)))
	#      B0=B0-B(I)*XMEAN(I)
	#    5 CONTINUE

	B = np.zeros(4, dtype='f')
	BSE = np.zeros(4, dtype='f')

	for I in range(MM):
		print('%s' % ''.join(['%18.8E' % A[I,J] for J in range(MM)]))

	FVE = 1. - A[M-1,M-1]
	B0 = XMEAN[M-1]
	YSE = 77.7
	if PHI >= 1:
		YSE = SIGMA[M-1] * np.sqrt(np.abs(A[M-1,M-1] / PHI))
	for I in range(L):
		if IDX[I] != 0:
			B[I] = A[I,M-1] * np.sqrt(np.abs(S[M-1,M-1] / S[I,I]))
			BSE[I] = YSE * np.sqrt(np.abs(A[I+M,I+M] / S[I,I]))
			B0 -= (B[I] * XMEAN[I])

	#      WRITE(8,10) ADX,NDX,FVE,YSE,B0
	#   10 FORMAT(/,' VARIABLE ', A8, '................',I5
	#     2,      /,' FRACTION OF VARIATION EXPLAINED..',E18.8
	#     3,      /,' STANDARD ERROR OF Y..............',E18.8
	#     4,      /,' CONSTANT IN REGRESSION EQUATION..',E18.8)
	#      WRITE(8,20)
	#   20 FORMAT(/,' VARIABLE     COEFFICIENT      STANDARD ERROR'
	#     1,'     PARTIAL F-VALUE')

	print(' VARIABLE %s................%5d' % (ADX, NDX))
	print(' FRACTION OF VARIATION EXPLAINED..%18.8E' % FVE)
	print(' STANDARD ERROR OF Y..............%18.8E' % YSE)
	print(' CONSTANT IN REGRESSION EQUATION..%18.8E' % B0)
	print(' VARIABLE     COEFFICIENT      STANDARD ERROR     PARTIAL F-VALUE')
	for I in range(L):
		if IDX[I] != 0:
			print('%5d%20.6E%20.6E%20.6E' % (I, B[I], BSE[I], PF[I]))
