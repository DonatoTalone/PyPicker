"""
Translation of TRVDRV subroutine
"""

from __future__ import absolute_import, division, print_function

import numpy as np


__all__ = ['TRVDRV']


"""
Hypo71PC
ISW,V,D,DEPTH,VSQ,NL,THK,H,G,F,TID,DID,FLT,
     &  DELTA,DX,DY,NR,KDX,KNO,FLTEP,z,ZSQ,X,T,ANIN

Hypopy:
ISW,V,D,DEPTH,VSQ,NL,THK,H,G,F,TID,DID,FLT,
     &  DELTA,DX,DY,NR,KDX,KNO,FLTEP,Z,ZSQ,X,T,ANIN,NRP,ISMODEL

ISW: selection card, str:
	- blank: use station delay model
	- '1': use variable first layer model
V: velocities (in km/s) [num_layers]
D: depths to top of layers (in km) [num_layers]
DEPTH: copy of D [num_layers]
VSQ: V**2
NL: number of layers [num_layers]
THK: layer thicknesses (in km) [num_layers]
H: copy of THK [num_layers]
G: G factor, computed from V and VSQ in input1.f [4, num_layers]
F: F factor, 1 or 2, set in input1.f [num_layers, num_layers]
TID: ?, computed in input1.f [num_layers, num_layers]
DID: ?, computed in input1.f [num_layers, num_layers]
FLT: ? used for variable first layer model [2, num_stations]
DELTA: epicentral distances, computed in single.f [num_phases]
DX: longitudinal component of DELTA, computed in single.f [num_phases]
DY: latitudinal component of DELTA, computed in single.f [num_phases]
NR: number of phases
KDX: station index [num_phases]
KNO: index of preferred crustal model of nearest station
FLTEP: ? computed from FLT in single.f
Z: hypocentral depth
ZSQ: Z**2

X: travel time derivatives [4, num_phases]
T: travel times [num_phases]
ANIN: angles of incidence [num_phases]

NRP: number of P phases
ISMODEL: number of velocity profiles in model (1 = P only, 2 = P + S)
"""

#      SUBROUTINE TRVDRV(ISW,V,D,DEPTH,VSQ,NL,THK,H,G,F,TID,DID,FLT,
#     &  DELTA,DX,DY,NR,KDX,KNO,FLTEP,z,ZSQ,X,T,ANIN)

## Note: KNO, FLTEP, FLT: related to variable first layer model (ISW='1'),
## which is not implemented (yet)

def TRVDRV(velocity_model, Z, DELTA, ELEV, VIDXS, ISW='', verbose=False):
	"""
	------- COMPUTE TRAVEL TIME AND DERIVATIVES FROM CRUSTAL MODEL --------

	:param velocity_model:
		instance of :class:`CrustalVelocityModel`
	:param Z:
		float, hypocentral depth
	:param DELTA:
		1D array, epicentral distances (in km) [num_phases]
	:param ELEV:
		1D array, negative station elevations (or depths) (in km) [num_phases]
	:param VIDXS:
		1D int array, velocity indexes [num_phases]
	:param ISW:
		str, selection card:
		- blank: use station delay model
		- '1': use variable first layer model (not yet implemented)
		(default: '')
	:param verbose:
		bool, whether or not to print travel-time info for direct
		and refracted wave
		(default: False)

	:return:
		(T, X, ANIN) tuple
		- T: travel times [num_phases]
		- X: partial derivatives in X, Y and Z [3, num_phases]
		Note: horizontal derivatives still need to be multiplied by DX / DY
		- ANIN: angle of incidence (in degrees) [num_phases]
	"""
	## From input1.f:
	#      N1=NL-1
	#C-----LAYER THICKNESS THK,F & G TERMS
	#      DO 145 L=1,N1
	#      THK(L)=D(L+1)-D(L)
	#  145 H(L)=THK(L)

	#C---- COMPUTE TID AND DID
	#      DO 150 J=1,NL
	#      G(1,J)=SQRT(ABS(VSQ(J)-VSQ(1)))/(V(1)*V(J))
	#      G(2,J)=SQRT(ABS(VSQ(J)-VSQ(2)))/(V(2)*V(J))
	#      G(3,J)=V(1)/SQRT(ABS(VSQ(J)-VSQ(1))+0.000001)
	#      G(4,J)=V(2)/SQRT(ABS(VSQ(J)-VSQ(2))+0.000001)
	#      IF (J .LE. 1) G(1,J)=0.
	#      IF (J .LE. 2) G(2,J)=0.
	#      IF (J .LE. 1) G(3,J)=0.
	#      IF (J .LE. 2) G(4,J)=0.
	#      DO 150 L=1,NL
	#      F(L,J)=1.
	#      IF (L .GE. J) F(L,J)=2.
	#  150 CONTINUE

	#      DO 165 J=1,NL
	#      DO 165 M=1,NL
	#      TID(J,M)=0.
	#  165 DID(J,M)=0.

	#      DO 170 J=1,NL
	#      DO 170 M=J,NL
	#      IF (M .EQ. 1) GO TO 170
	#      M1=M-1
	#      DO 160 L=1,M1
	#      SQT=SQRT(VSQ(M)-VSQ(L))
	#      TIM=THK(L)*SQT/(V(L)*V(M))
	#      DIM=THK(L)*V(L)/SQT
	#      TID(J,M)=TID(J,M)+F(L,J)*TIM
	#  160 DID(J,M)=DID(J,M)+F(L,J)*DIM
	#  170 CONTINUE

	D = velocity_model.depths
	V = np.vstack([velocity_model.VP, velocity_model.VS])
	VSQ = V * V
	NV = 2

	## Compute layer thicknesses
	NL = len(D)
	THK = velocity_model.thicknesses
	#print('THK', THK)

	## F and G terms
	F = np.zeros((NL, NL), dtype='int8')
	for J in range(NL):
		for L in range(NL):
			F[L,J] = 1
			if L >= J:
				F[L,J] = 2
	#print('F', F)

	# TODO: G only necessary for variable first layer model
	"""
	if ISW.strip() == '1':
		G = np.zeros((NV, 4, NL))
		for J in range(NL):
			G[:,0,J] = np.sqrt(np.abs(VSQ[:,J] - VSQ[:,0])) / (V[:,0] * V[:,J])
			G[:,1,J] = np.sqrt(np.abs(VSQ[:,J] - VSQ[:,1])) / (V[:,1] * V[:,J])
			G[:,2,J] = V[:,0] / np.sqrt(np.abs(VSQ[:,J] - VSQ[:,0]) + 0.000001)
			G[:,3,J] = V[:,1] / np.sqrt(np.abs(VSQ[:,J] - VSQ[:,1]) + 0.000001)
			if J == 0:
				G[:,0,J] = 0
			if J <= 1:
				G[:,1,J] = 0
			if J <= 2:
				G[:,2,J] = 0
			if J <= 3:
				G[:,3,J] = 0
		print('G', G)
	"""

	## TID and DID
	#TID = np.zeros((NV, NL, NL))
	#DID = np.zeros((NV, NL, NL))
	#for KV in range(NV):
	#	for J in range(NL):
	#		for M in range(J, NL):
	#			if M > 0:
	#				M1 = M - 1
	#				for L in range(M1):
	#					SQT = np.sqrt(VSQ[KV,M] - VSQ[KV,L])
	#					TIM = THK[L] * SQT / (V[KV,L] * V[KV,M])
	#					DIM = THK[L] * V[KV,L] / SQT
	#					TID[KV,J,M] += F[L,J] * TIM
	#					DID[KV,J,M] += F[L,J] * DIM

	#        if(indr.eq.0) then
	#        do lr=2,nl
	#                do ls=1,nl
	#                        dxd(ls,lr)=0
	#                        txd(ls,lr)=0
	#                enddo
	#                do ls=1,nl
	#                        do ll=ls,lr-1
	#                              sqt=sqrt(vsq(lr)-vsq(ll))
	#                              tim=thk(ll)/v(ll)*v(lr)/sqt
	#                              dim=thk(ll)*v(ll)/sqt
	#                dxd(ls,lr)= dxd(ls,lr) + dim
	#                txd(ls,lr)= txd(ls,lr) + tim
	#c                print *,lr,ls,ll,txd(ls,lr),dxd(ls,lr),tim,dim
	#                        enddo
	#                enddo
	#        enddo
	#        indr=1
	#c        print *, 'init done'
	#        endif
	#        thk0=thk(1)

	TXD = np.zeros((NV, NL, NL), dtype='f')
	DXD = np.zeros((NV, NL, NL), dtype='f')
	for KV in range(NV):
		for LR in range(1, NL):
			## LR: index of layer below bottom layer
			for LS in range(NL):
				## LS: index of top layer
				for LL in range(LS, LR):
					## LL: layers in between
					SQT = np.sqrt(VSQ[KV,LR] - VSQ[KV,LL])
					TIM = THK[LL] / V[KV,LL] * V[KV,LR] / SQT
					DIM = THK[LL] * V[KV,LL] / SQT
					TXD[KV,LS,LR] += TIM
					DXD[KV,LS,LR] += DIM

	#print('TXD', TXD[1])
	#print('DXD', DXD[1])

	#      IF (ISW .NE. '1   ') GO TO 200
	#C---- VARIABLE FIRST LAYER
	#      VC=V(1,1)*V(1,2)/SQRT(VSQ(1,2)-VSQ(1,1))
	#      DO 180 I=1,NS
	#      FLT(1,I)=DLY(1,I)*VC+D(2)
	#  180 FLT(2,I)=DLY(2,I)*VC+D(2)

	if ISW.strip() == '1':
		print('the variable first layer not implemented')
		return
		## Note: requires NS
		VC = V[0] * V[1] / np.sqrt(VSQ[1] - VSQ[0])
		FLT = np.zeros((2, NS))
		FLT[0] = DLY[0] * VC + D[1]
		FLT[1] = DLY[1] * VC + D[1]

	#ZSQ = Z * Z

	#        thk0=thk(1)
	#      IF (ISW .EQ. '1   ') GO TO 6
	#        call prep1(nl,z,d,v,vsq,txd,dxd,tinf,didf,xomaxf,jf,tkjf)
	#                                      endif

	THK0 = THK[0]

	## Find focus layer and compute time and distance for downgoing rays
	if ISW.strip() != '1':
		JF, TKJF, TINF, DIDF, XOMAXF = [], [], [], [], []
		for KV in range(NV):
			(jf, tkjf, tinf, didf, xomaxf) = PREP1(Z, D, V[KV], VSQ[KV],
													TXD[KV], DXD[KV])
			JF.append(jf)
			TKJF.append(tkjf)
			TINF.append(tinf)
			DIDF.append(didf)
			XOMAXF.append(xomaxf)
		#print(JF[0])
		#print(TKJF[0])
		#print(TINF[0])
		#print(DIDF[0])
		#print(XOMAXF[0])

	#c---------------  loop over stations --------------------------------
	#      DO 300 I=1,NR
	#        ji = kdx(i)
	#        zstat=elev(ji)
	#        delti=delta(i)
	#        if(delti.lt.0.01) delti=0.01
	#c        thk(1)=thk0-zstat +d(1)
	#c                                     IF (ISW .eq. '1   ') goto 701
	#c------ find station layer
	#        call prep1(nl,zstat,d,v,vsq,txd,dxd,tins,dids,xomaxs,js,tkjs)
	#c        print *,'---> ',z,zstat,delti,js,jf,xomaxs,xomaxf
	#        tmin=9999
	#        jm=21
	#        tr(21)=tmin

	## Loop over phases
	NR = len(DELTA)
	T = np.zeros(NR, dtype='f')
	ANIN = np.zeros(NR, dtype='f')
	X = np.zeros((4, NR), dtype='f')
	for I in range(NR):
		ZSTAT = ELEV[I]
		DELTI = max(DELTA[I], 0.01)
		KV = VIDXS[I]
		VI, VSQI = V[KV], VSQ[KV]
		TXDI, DXDI = TXD[KV], DXD[KV]

		JFI, TKJFI = JF[KV], TKJF[KV]
		TINFI, DIDFI = TINF[KV], DIDF[KV]
		XOMAXFI = XOMAXF[KV]

		## Find station layer
		(JS, TKJS, TINS, DIDS, XOMAXS) = PREP1(ZSTAT, D, VI, VSQI, TXDI, DXDI)

		## Minimum epicentral distance required to get refracted wave
		XOMAX = XOMAXS + XOMAXFI
		if verbose:
			print('XOMAX', XOMAX, XOMAXFI, XOMAXS)
			#print('XOMAX', XOMAX, DELTI, KV)

		TMIN = 9999
		JM = NL - 1
		TR = np.zeros(NL, dtype='f')
		TR[JM] = TMIN

		#              IF (Jf .EQ. NL) GO TO 90
		#         if(delti.lt.xomaxs+xomaxf) goto 90
		#C-----TRAVEL TIME & DERIVATIVES FOR REFRACTED WAVE
		#80         continue
		#        call refwav(nl,jf,tinf,didf,js,tins,dids,v,delti,tr,tmin,jm)
		#        goto 90
		#82    T(I)=TR(jm)
		#      DTDD=1.0/V(jm)
		#      DTDH=-SQRT(VSQ(jm)-VSQ(jf))/(V(jm)*V(jf))
		#      ANIN(I)=-V(jf)/V(jm)
		#      GO TO 260
		#90         continue
		#        if(z.gt.zstat) then
		#        call dirwav(z,jf,tkjf,zstat,js,tkjs,tins,dids,delti,tmin,1.,thk
		#     1 ,v,vsq,dtdd,dtdh,anin(i),t(i))
		#        else
		#        call dirwav(zstat,js,tkjs,z,jf,tkjf,tinf,didf,delti,tmin,-1.,thk
		#     1 ,v,vsq,dtdd,dtdh,anin(i),t(i))
		#        endif
		#        if(t(i).gt.tmin) goto 82

		if JFI < NL:
			if DELTI >= XOMAX:
				## -----TRAVEL TIME (& DERIVATIVES) FOR REFRACTED WAVE
				(TR, TMIN, JM) = REFWAV(JFI, TINFI, DIDFI, JS, TINS, DIDS, VI,
										DELTI)
				if verbose:
					print('REFWAV', TMIN, JM)
				#print(TINFI[JM], DIDFI[JM], TINS[JM], DIDS[JM])

		## -----TRAVEL TIME & DERIVATIVES FOR DIRECT WAVE
		if Z > ZSTAT:
			(t, DTDD, DTDH, anin) = DIRWAV(Z, JFI, TKJFI, ZSTAT, JS, TKJS, TINS,
										DIDS, DELTI, TMIN, 1., THK, VI, VSQI)
		else:
			(t, DTDD, DTDH, anin) = DIRWAV(ZSTAT, JS, TKJS, Z, JFI, TKJFI, TINFI,
										DIDFI, DELTI, TMIN, -1., THK, VI, VSQI)
		if verbose:
			print('DIRWAV', t)
		T[I] = t
		ANIN[I] = anin

		if T[I] > TMIN:
			## Refracted wave is faster
			#82    T(I)=TR(jm)
			#      DTDD=1.0/V(jm)
			#      DTDH=-SQRT(VSQ(jm)-VSQ(jf))/(V(jm)*V(jf))
			#      ANIN(I)=-V(jf)/V(jm)
			#      GO TO 260
			T[I] = TR[JM]
			DTDD = 1. / VI[JM]
			DTDH = -np.sqrt(VSQI[JM] - VSQI[JFI]) / (VI[JM] * VI[JFI])
			ANIN[I]= -VI[JFI] / VI[JM]

		#C-----SET UP PARTIAL DERIVATIVES FOR REGRESSION ANALYSIS ---------------
		#c-------------- c'est bien -px,-py,-pz       d'apres les formules
		#  260         continue
		#                X(1,I)=-DTDD*DX(I)/DELTI
		#                      X(2,I)=-DTDD*DY(I)/DELTI
		#      X(3,I)=DTDH
		#  300 CONTINUE

		## -----SET UP PARTIAL DERIVATIVES FOR REGRESSION ANALYSIS ---------------
		## This has been moved to calling function, to remove dependency on DX, DY
		#X[0,I] = -DTDD * DX[I] / DELTI
		#X[1,I] = -DTDD * DY[I] / DELTI
		X[0,I] = -DTDD / float(DELTI)
		X[1,I] = -DTDD / float(DELTI)
		X[2,I] = DTDH

	#        thk(1)=thk0
	#      RETURN

	THK[0] = THK0


	## From OUTPUT subroutine
	#      AIN(I)=ASIN(ANIN(I))*57.29578
	#      IF (AIN(I) .LT. 0.) AIN(I)=180.+AIN(I)
	#      AIN(I)=180.-AIN(I)

	AIN = np.degrees(np.arcsin(ANIN))
	AIN[AIN < 0] = 180 + AIN[AIN < 0]
	AIN = 180 - AIN

	return (T, X, AIN)


def PREP1(Z, D, V, VSQ, TID, DID):
	"""
	-----INITIALIZATION FOR FIXED LAYER MODEL -------------------------

	:param Z:
		float, depth of focus or station
	:param D:
		1D array, layer tops
	:param V:
		1D array, layer velocities
	:param VSQ:
		1D array, squared layer velocities
	:param TID:
		2D array, ? [num_layers, num_layers]
	:param DID:
		2D array, ? [num_layers, num_layers]

	:return:
		tuple of (JL, TKJ, TINJ, DIDJ, XOMAX)
		- JL: index of layer
		- TKJ: depth inside layer
		- TINJ: 1D array, downgoing rays time [num_layers]
		- DINJ: 1D array, downgoing rays distance [num_layers]
		- XOMAX: float, max. distance (= minimum horizontal distance for downgoing rays)
	"""
	#c-------------- determine layer -------------------------
	#         DO   L=2,NL
	#            IF (D(L) .GT. Z) then
	#               jj=l
	#               jl=l-1
	#               goto 3
	#            endif
	#         enddo
	#         JL=NL
	#    3    TKJ=Z-D(JL)
	#c-------------- downgoing rays time and distance --------
	#        xomax=9999.
	#         IF (JL .ne. NL) then
	#            DO  L=JJ,NL
	#               SQT=SQRT(VSQ(L)-VSQ(JL))
	#               TINJ(L)=TID(JL,L)-TKJ/SQT*V(L)/V(JL)
	#               DIDJ(L)=DID(JL,L)-TKJ*V(JL)/SQT
	#               if(didj(l).lt.xomax) xomax=didj(l)
	#            enddo
	#c           XOMAX=V(JJ)*V(JL)*(TINJ(JJ)-TID(JL,JL))/(V(JJ)-V(JL))
	#         endif
	#        return
	#        end

	NL = len(D)

	## Determine layer
	for L in range(1, NL):
		if D[L] > Z:
			JJ = L
			## JL corresponds to index of layer in which Z is situated
			JL = L - 1
			break
	else:
		JL = NL - 1
	TKJ = Z - D[JL]

	## Compute time and distance for downgoing refracted rays
	XOMAX = 9999.
	TINJ = np.zeros(NL, dtype='f')
	DIDJ = np.zeros(NL, dtype='f')

	if JL != NL - 1:
		for L in range(JJ, NL):
			## L corresponds to layer below bottom layer
			SQT = np.sqrt(VSQ[L] - VSQ[JL])
			TINJ[L] = TID[JL,L] - TKJ / SQT * V[L] / V[JL]
			DIDJ[L] = DID[JL,L] - TKJ * V[JL] / SQT
			if DIDJ[L] < XOMAX:
				XOMAX = DIDJ[L]
	#print('TINJ', TINJ)

	return (JL, TKJ, TINJ, DIDJ, XOMAX)


def REFWAV(JF, TINF, DIDF, JS, TINS, DIDS, V, DELTA):
	"""
	-----CALCULATION FOR REFRACTED WAVE

	:param JF:
		int, layer index for focus
	:param TINF:
		1D array, downgoing rays time for focus [num_layers]
	:param DIDF:
		1D array, downgoing rays distance for focus [num_layers]
	:param JS:
	:param TINS:
	:param DIDS:
		like JF, TINF and DIDF, but for station
	:param V:
		1D array, layer velocities [num_layers]
	:param DELTA:
		float, epicentral distance (in km)

	:return:
		tuple of (TR, TMIN, JM)
		- TR: 1D float array, travel times corresponding to each
			layer [num_layers]
		- TMIN: float, minimum travel time
		- JM: int, index of layer (below bottom layer) corresponding
		  to minimum travel time
	"""
	NL = len(V)
	FDX = np.zeros(NL, dtype='f')
	TMIN = 9999
	TR = np.ones(NL, dtype='f') * TMIN
	#TR[-1] = TMIN

	#        jj=max(jf,js)+1
	#      DO M=JJ,NL
	#        fdx(m)=didf(m)+dids(m)
	#        tr(m)=tmin
	#        if(fdx(m).le.delta) TR(M)=TINs(M)+tinf(m)+(DELTA-fdx(m))/V(M)
	#      enddo
	#      DO M=JJ,NL
	#         IF (TR(M) .lt. TMIN) then
	#               jm=M
	#               TMIN=TR(M)
	#         endif
	#      enddo
	#        return
	#        end

	## JJ corresponds to index of layer below shallowest bottom layer
	JJ = max(JF, JS) + 1
	#JJ = max(JF, JS)
	for M in range(JJ, NL):
		FDX[M] = DIDF[M] + DIDS[M]
		TR[M] = TMIN
		if FDX[M] <= DELTA:
			TR[M] = TINS[M] + TINF[M] + (DELTA - FDX[M]) / V[M]

	JM = NL - 1
	for M in range(JJ, NL):
		if TR[M] < TMIN:
			JM = M
			TMIN = TR[M]

	return (TR, TMIN, JM)


def DIRWAV(Z, JL, TKJ, ZSTAT, JS, TKJS, TINS, DIDS, DELTA, TMIN, FF,
			THK, V, VSQ):
	"""
	-----CALCULATION FOR DIRECT WAVE

	:param Z:
		float, hypocentral depth
	:param JL:
		int, layer index of focus
	:param TKJ:
		float, depth of focus inside layer
	:param ZSTAT:
		float, station elevation (or rather depth)
	:param JS:
		int, layer index of station
	:param TKJS:
		float, depth of station inside layer
	:param TINS:
		1D array, downgoing rays time for station [num_layers]
	:param DIDS:
		1D array, downgoing rays distance for station [num_layers]
	:param DELTA:
		float, epicentral distance (in km)
	:param TMIN:
		float, minimum travel time
	:param FF:
		int, factor indicating if ray is traced from focus to station,
		i.e. Zf > Zs (1) or the other way around (-1)
	:param THK:
		1D array, layer thicknesses [num_layers]
	:param V:
		1D array, layer velocities [num_layers]
	:param VSQ:
		1D array, squared layer velocities [num_layers]

	:return:
		(T, DTDD, DTDH, ANIN)
		T: float, travel time
		DTDD: float, horizontal derivative
		DTDH: float, vertical derivative
		ANIN: float, angle of incidence?
	"""
	#C-----CALCULATION FOR DIRECT WAVE --focus and station in the same layer
	#        thk0=thk(js)
	#        ddz=z-zstat
	#        if(ddz.lt.0.01) ddz=0.01
	#c         print *,'dirwav ',delta,ddz,jl,js,tkj,tkjs
	#      IF (JL .eq.js) then
	#         SQT=SQRT((ddz)**2+DELTA**2)
	#         TDJ1=SQT/V(js)
	#C-----TRAVEL TIME & DERIVATIVES FOR DIRECT WAVE IN FIRST LAYER
	#         T=TDJ1
	#c        IF (TDJ1 .GE. TMIN) goto 800
	#         DTDD=DELTA/(V(js)*SQT)
	#         DTDH=(ddz) /(V(js)*SQT) *ff
	#         ANIN=DELTA/SQT
	#                goto 800
	#      endif

	## Take copy to avoid modifying array in calling function
	THK = THK.copy()

	## Focus and station in the same layer
	THK0 = THK[JS]
	DDZ = max(Z - ZSTAT, 0.01)
	if JL == JS:
		SQT = np.sqrt(DDZ * DDZ + DELTA * DELTA)
		TDJ1 = SQT / V[JS]
		## -----TRAVEL TIME & DERIVATIVES FOR DIRECT WAVE IN FIRST LAYER
		T = TDJ1
		if TDJ1 < TMIN:
			DTDD = DELTA / (V[JS] * SQT)
			DTDH = DDZ / (V[JS] * SQT) * FF
			ANIN = DELTA / SQT
		else:
			## These values are probably never used anyway
			DTDD, DTDH = 1., 1.
			ANIN = 0.
		#goto 800

		#        thk(js)=thk0-tkjs
		#C-----FIND A DIRECT WAVE THAT WILL EMERGE AT THE STATION
		#  100 XBIG=DELTA
		#        TKJSQ=TKJ**2+0.000001
		#              XLIT=DELTA*TKJ/ddz
		#        if(xlit.gt.delta) then
		#                xlit=0.
		#                print *,'biz ',tkj,delta,ddz
		#        endif
		#      UB=XBIG/SQRT(XBIG**2+TKJSQ)
		#      UL=XLIT/SQRT(XLIT**2+TKJSQ)
		#      UBSQ=UB**2
		#      ULSQ=UL**2
		#      DELBIG=TKJ*UB/SQRT(1.000001-UBSQ)
		#      DELLIT=TKJ*UL/SQRT(1.000001-ULSQ)
		#cn        print *,'< ',delbig,' - ',dellit,'=',delbig-dellit
		#      J1=JL-1
		#      DO L=js,J1
		#cn        print *,l,ub,ul,ubsq,ulsq,thk(l),vsq(jl),vsq(l)
		#         DELBIG=DELBIG+(THK(L)*UB)/SQRT(VSQ(JL)/VSQ(L)-UBSQ)
		#         DELLIT=DELLIT+(THK(L)*UL)/SQRT(VSQ(JL)/VSQ(L)-ULSQ)
		#cn        print *,'< ',delbig,' - ',dellit,'=',delbig-dellit
		#      enddo

	else:
		THK[JS] = THK0 - TKJS

		## -----FIND A DIRECT WAVE THAT WILL EMERGE AT THE STATION
		XBIG = float(DELTA)
		TKJSQ = TKJ * TKJ + 0.000001
		XLIT = DELTA * TKJ / float(DDZ)
		if XLIT > DELTA:
			XLIT = 0.

		UB = XBIG / np.sqrt(XBIG * XBIG + TKJSQ)
		UL = XLIT / np.sqrt(XLIT * XLIT + TKJSQ)
		UBSQ = UB * UB
		ULSQ = UL * UL
		DELBIG = TKJ * UB / np.sqrt(1.000001 - UBSQ)
		DELLIT = TKJ * UL / np.sqrt(1.000001 - ULSQ)

		#J1 = JL - 1
		J1 = JL
		for L in range(JS, J1):
			DELBIG += (THK[L] * UB) / np.sqrt(VSQ[JL] / VSQ[L] - UBSQ)
			DELLIT += (THK[L] * UL) / np.sqrt(VSQ[JL] / VSQ[L] - ULSQ)

		#      DO LL=1,25
		#cn        print *,'< ',delbig,' - ',dellit,'=',delbig-dellit
		#         if (DELBIG-DELLIT .LT. 0.02) then
		#            XTR=0.5*(XBIG+XLIT)
		#            U=XTR/SQRT(XTR**2+TKJSQ)
		#            USQ=U**2
		#        else
		#            XTR=XLIT+(DELTA-DELLIT)*(XBIG-XLIT)/(DELBIG-DELLIT)
		#            U=XTR/SQRT(XTR**2+TKJSQ)
		#            USQ=U**2
		#         endif
		#         DELXTR=TKJ*U/SQRT(1.000001-USQ)
		#         do L=js,J1
		#            DELXTR=DELXTR+(THK(L)*U)/SQRT(VSQ(JL)/VSQ(L)-USQ)
		#         enddo
		#         XTEST=DELTA-DELXTR
		#         IF (ABS(XTEST) .LE. 0.02) GO TO 190
		#         IF (XTEST.lt.0.) then
		#            XBIG=XTR
		#            DELBIG=DELXTR
		#         else
		#            XLIT=XTR
		#            DELLIT=DELXTR
		#         endif
		#        if(ll.gt.10) then
		#            IF (1.0-U .LT. 0.0002) GO TO 190
		#        endif
		#      enddo

		## Note: why 25? (num_layers + 4??)
		for LL in range(25):
			if DELBIG - DELLIT < 0.02:
				XTR = 0.5 * (XBIG + XLIT)
				U = XTR / np.sqrt(XTR * XTR + TKJSQ)
				USQ = U * U
				## Note: original version of hypo71 has a GO TO 180 statement,
				## (i.e., break out of for loop), but seiscomp version hasn't!
				break
			else:
				XTR = XLIT + (DELTA - DELLIT) * (XBIG - XLIT) / float(DELBIG - DELLIT)
				U = XTR / np.sqrt(XTR * XTR + TKJSQ)
				USQ = U * U
				DELXTR = TKJ * U / np.sqrt(1.000001 - USQ)
				for L in range(JS, J1):
					DELXTR += (THK[L] * U) / np.sqrt(VSQ[JL] / VSQ[L] - USQ)
				XTEST = DELTA - DELXTR
				if abs(XTEST) <= 0.02:
					break
				if XTEST < 0:
					XBIG = XTR
					DELBIG = DELXTR
				else:
					XLIT = XTR
					DELLIT = DELXTR
				if LL >= 10:
					if 1.0 - U < 0.0002:
						break

		#  190 IF (1.0-U .le. 0.0002) then
		#C-----IF U IS TOO NEAR 1, COMPUTE TDIR AS WAVE ALONG THE TOP OF LAYER JL
		#cn        print *,u
		#c        IF (ISW .EQ. '1   ') then
		#c--- fossile
		#c           TIX=F(1,JL)*DH1*G(1,JL)+F(2,JL)*DH2*G(2,JL)+TID(JL,JL)
		#c           TDC=TIX+DELTA/V(JL)
		#c--- fin fossile
		#c        else
		#            TDC=tins(JL)+(DELTA-dids(jl))/V(JL)
		#c        endif
		#            T=TDC
		#            DTDD=1.0/V(JL)
		#            DTDH=0.0
		#cn        print *,'fine ',delta,t,dtdd,dtdh
		#            ANIN=0.9999999
		#                goto 800
		#      endif

		## IF U IS TOO NEAR 1, COMPUTE TDIR AS WAVE ALONG THE TOP OF LAYER JL
		if 1.0 - U <= 0.0002:
			TDC = TINS[JL] + (DELTA - DIDS[JL]) / V[JL]
			T = TDC
			DTDD = 1. / V[JL]
			DTDH = 0.
			ANIN = 0.9999999
			#goto 800

		#C-----TRAVEL TIME & DERIVATIVES FOR DIRECT WAVE BELOW FIRST LAYER
		#c--------------- travel time ---------------
		#      TDIR=TKJ/(V(JL)*SQRT(1.0-USQ))
		#cn        print *,tdir
		#      DO L=js,J1
		#         TDIR=TDIR+(THK(L)*V(JL))/(VSQ(L)*SQRT(VSQ(JL)/VSQ(L)-USQ))
		#c        print *,delta,tdir
		#      enddo
		#      T=TDIR
		#        if(tdir.gt.tmin) then
		#                dtdd=1.
		#                dtdh=1.
		#                goto 800
		#        endif
		#c---------------- derivatives --------------
		#      SRR=SQRT(1.-USQ)
		#      SRT=SRR**3
		#        if(srr.lt.0.001) then
		#                dtdd=0.
		#                dtdh=0.
		#                anin=0.
		#                goto 800
		#        endif

		## -----TRAVEL TIME & DERIVATIVES FOR DIRECT WAVE BELOW FIRST LAYER
		else:
			## Travel time
			TDIR = TKJ / (V[JL] * np.sqrt(1.0 - USQ))
			for L in range(JS, J1):
				TDIR += (THK[L] * V[JL]) / (VSQ[L] * np.sqrt(VSQ[JL] / VSQ[L] - USQ))
			T = TDIR

			## Derivatives
			if TDIR > TMIN:
				DTDD, DTDH = 1., 1.
				# TODO: ANIN for this case??
				ANIN = 0.
				#goto 800
			else:
				SRR = np.sqrt(1. - USQ)
				SRT = SRR * SRR * SRR
				if SRR < 0.001:
					DTDD, DTDH = 0., 0.
					ANIN = 0.
					#goto 800

		#      ALFA=TKJ/SRT
		#      BETA=TKJ*U/(V(JL)*SRT)
		#      DO L=js,J1
		#         STK=(SQRT(VSQ(JL)/VSQ(L)-USQ))**3
		#         VTK=THK(L)/(VSQ(L)*STK)
		#         ALFA=ALFA+VTK*VSQ(JL)
		#         BETA=BETA+VTK*V(JL)*U
		#      enddo
		#      DTDD=BETA/ALFA
		#        if(ff.gt.0.) then
		#                jfo=jl
		#                else
		#                jfo=js
		#        endif
		#      DTDH=(1.0-V(Jfo)*U*DTDD)/(V(Jfo)*SRR)*ff
		#      ANIN=U

				else:
					ALFA = TKJ / SRT
					BETA = TKJ * U / (V[JL] * SRT)
					for L in range(JS, J1):
						STK = (np.sqrt(VSQ[JL] / VSQ[L] - USQ))**3
						VTK = THK[L] / (VSQ[L] * STK)
						ALFA += (VTK * VSQ[JL])
						BETA += (VTK * V[JL] * U)
					DTDD = BETA / ALFA
					JFO = JL if FF > 0 else JS
					DTDH = (1.0 - V[JFO] * U * DTDD) / (V[JFO] * SRR) * FF
					ANIN = U

	#800        continue
	#        thk(js)=thk0
	#c        print *,'der ',t,dtdh,dtdd
	#c        print *,'dir*-',(thk(k),k=1,5)
	#        return
	#        end

	THK[JS] = THK0

	return (T, DTDD, DTDH, ANIN)



if __name__ == '__main__':
	from robspy.rob.velocity_model import BEL as vmodel

	vmodel.recalc_vs_from_vp(1.73)

	theta_crit = vmodel.calc_critical_angles(wave='P')
	#print(np.degrees(theta_crit))
	#for L, theta in enumerate(theta_crit):
	#	layer_angles = vmodel.calc_layer_angles_above(L, theta)
	#	print(np.degrees(layer_angles))
	#	print(np.sum(vmodel.calc_travel_times(layer_angles, wave='P')))
	#	print(np.sum(vmodel.calc_horizontal_distances(layer_angles)))
	#print(vmodel.calc_refraction_matrices()[0][0])
	#print(vmodel.calc_downgoing_ray_tt_and_hd(10.))

	#DELTA = np.array([5., 33., 45., 67.])
	DELTA = np.array([24, 16, 20, 25, 30, 80])
	ELEV = np.zeros_like(DELTA)
	VIDXS = np.array([1,1,1,1,1,1])
	Z = 0.

	(T, X, ANIN) = TRVDRV(vmodel, Z, DELTA, ELEV, VIDXS, verbose=True)
	print('T', T)
	print('X', X)
	print('ANIN', ANIN)
