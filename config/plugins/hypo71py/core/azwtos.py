"""
"""

import numpy as np


__all__ = ['AZWTOS']


def AZWTOS(AZ, normalize=True):
	"""
	------- AZIMUTHAL WEIGHTING OF STATIONS BY QUADRANTS ---------------
	Phases in less populated quadrants receive higher weight

	:param AZ:
		1D array, phase azimuths, in decimal degrees
	:param normalize:
		bool, whether or not azimuthal weights should be normalized
		(default: True)

	:return:
		(AZWT, GAP) tuple
		- AZWT: 1D array, azimuthal weights
		  (need to be multiplied with prior weights)
		- GAP: float, azimuthal gap (in degrees)
	"""
	## Note: compared to the Fortran version, we compute azimuths
	## in the calling function, and we only pass azimuths of phases
	## with non-zero weights. This reduces the number of arguments to 1.

#      SUBROUTINE AZWTOS(DX,DY,NR,WT,KDX,AZ,TEMP,KEY,INS,IEW)
#C------- AZIMUTHAL WEIGHTING OF STATIONS BY QUADRANTS ------------------
#	include 'H_param.f'
#      CHARACTER*1 INS(N_s),IEW(N_s)
#      INTEGER*4 KTX(4),KEMP(N_d),KEY(N_d),KDX(N_d)
#      REAL*4 TX(4),TXN(4),DX(N_d),DY(N_d),WT(N_d),AZ(N_d),TEMP(N_d)
#C-----------------------------------------------------------------------
#      J=0
#      DO 10 I=1,NR
#      IF (WT(I) .EQ. 0.) GO TO 10
#      DXI=DX(I)
#      DYI=DY(I)
#      IF ((DXI.EQ.0.).AND.(DYI.EQ.0.)) GO TO 6
#      JI=KDX(I)
#      IF (INS(JI) .EQ. 'S') DYI=-DYI
#      IF (IEW(JI) .EQ. 'W') DXI=-DXI
#      AZ(I)=AMOD(ATAN2(DXI,DYI)*57.29578 + 360., 360.)
#      GO TO 7
#    6 AZ(I)=999.
#    7 J=J+1
#      TEMP(J)=AZ(I)
#   10 CONTINUE

	## Move this to calling function
	#AZ = np.mod(np.degrees(np.arctan2(DX, DY)) + 360., 360.)
	#AZ[(DX == 0) & (DY == 0)] = 999.
	#AZ[WT == 0] = 0.
	#J = np.sum(non_zero_weight_idxs)
	J = len(AZ)

#      CALL SORT(TEMP,KEY,J)
#      GAP=TEMP(1)+360.-TEMP(J)
#      IG=1
#      DO 20 I=2,J
#      DTEMP=TEMP(I)-TEMP(I-1)
#      IF (DTEMP .LE. GAP) GO TO 20
#      GAP=DTEMP
#      IG=I
#   20 CONTINUE

	## Determine azimuthal gap
	AZ_SORTED = np.sort(AZ)
	GAP = AZ_SORTED[0] + 360 - AZ_SORTED[-1]
	DAZ = np.hstack([[GAP], np.diff(AZ_SORTED)])
	IG = np.argmax(DAZ)
	GAP = DAZ[IG]
	#print('GAP', GAP)
	#print('IG', IG, AZ_SORTED[IG])

#      TX(1)=TEMP(IG)-0.5*GAP
#      TX(2)=TX(1)+90.
#      TX(3)=TX(1)+180.
#      TX(4)=TX(1)+270.
#      DO 124 I=1,4
#      TXN(I)=0.
#      IF (TX(I) .LT. 0.) TX(I)=TX(I)+360.
#      IF (TX(I).GT.360.) TX(I)=TX(I)-360.
#  124 CONTINUE
#      CALL SORT(TX,KTX,4)

	## Define azimuth quadrants
	TX = np.array([0., 90., 180., 270.])
	TX += AZ_SORTED[IG] - 0.5 * GAP
	TX[TX < 0] += 360
	TX[TX > 360] -= 360
	TX = np.sort(TX)
	#print('TX', TX)

#      DO 130 I=1,NR
#      IF (WT(I) .EQ. 0.) GO TO 130
#      IF (AZ(I) .GT. TX(1)) GO TO 126
#  125 TXN(1)=TXN(1)+1.
#      KEMP(I)=1
#      GO TO 130
#  126 IF (AZ(I) .GT. TX(2)) GO TO 127
#      TXN(2)=TXN(2)+1.
#      KEMP(I)=2
#      GO TO 130
#  127 IF (AZ(I) .GT. TX(3)) GO TO 128
#      TXN(3)=TXN(3)+1.
#      KEMP(I)=3
#      GO TO 130
#  128 IF (AZ(I) .GT. TX(4)) GO TO 125
#      TXN(4)=TXN(4)+1.
#      KEMP(I)=4
#  130 CONTINUE

	## Determine quadrant for each phase
	## and count number of phases in each quadrant
	#NR = len(AZ)
	#TXN = np.zeros(4)
	#KEMP = np.zeros(NR, 'int8')
	#for I in range(NR):
		#if WT[I] > 0:
	#		if AZ[I] <= TX[0] or AZ[I] > TX[3]:
	#			KEMP[I] = 0
	#			TXN[0] += 1
	#		elif AZ[I] <= TX[1]:
	#			KEMP[I] = 1
	#			TXN[1] += 1
	#		elif AZ[I] <= TX[2]:
	#			KEMP[I] = 2
	#			TXN[2] += 1
	#		elif AZ[I] <= TX[3]:
	#			KEMP[I] = 3
	#			TXN[3] += 1
	KEMP = np.digitize(AZ, TX)
	KEMP[KEMP==4] = 0
	#print('KEMP', KEMP)
	TXN = np.bincount(KEMP, minlength=4)
	#print('TXN', TXN)

#      XN=4
#      IF (TXN(1).EQ.0.) XN=XN-1
#      IF (TXN(2).EQ.0.) XN=XN-1
#      IF (TXN(3).EQ.0.) XN=XN-1
#      IF (TXN(4).EQ.0.) XN=XN-1
#      FJ=J/XN
#      DO 150 I=1,NR
#      IF (WT(I) .EQ. 0.) GO TO 150
#      KI=KEMP(I)
#      WT(I)=WT(I)*FJ/TXN(KI)
#  150 CONTINUE
#      RETURN
#      END

	XN = np.sum(TXN > 0)
	FJ = float(J) / XN
	#print('J', J, 'XN', XN, 'FJ', FJ)
	#AZWT[non_zero_weight_idxs] = (FJ / TXN[KEMP[non_zero_weight_idxs]])
	AZWT = (FJ / TXN[KEMP])

	## Note: normalization of weights not in original version
	if normalize:
		AZWT /= AZWT.max()

	return (AZWT, GAP)



if __name__ == "__main__":
	az = np.array([5,10,15,25,75,95,105,145,195,205,225,270,290,345])
	#az = np.random.uniform(0, 360, 15)

	az_wt, gap = AZWTOS(az, normalize=True)
	print('gap: ', gap)
	print('az_wt: ', az_wt)
