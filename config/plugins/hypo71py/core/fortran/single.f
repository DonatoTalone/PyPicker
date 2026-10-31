      include 'azwtos.f'
      include 'trvdrv.f'
      include 'swmreg.f'
C TODO: remove FLT, JDX, KSMP, WRK, ISW
C TODO: add option to write output file or not
      SUBROUTINE SINGLE(NS,IW,NSTA,LAT,LON,INS,IEW,elev,MNO,DLY,FLT,JDX,
c     &  FMGC,XMGC,KLAS,PRR,CALR,ICAL,
     &  NL,V,D,
c     &  G,F,TID,DID,DEPTH,VSQ,THK,H
     &  KDATE,KHR,
     &  NR,KDX,LDX,JMIN,PRMK,W,P,NRP,SRMK,WS,S,DT,WRK,KSMP,
c     &  TP,TS
c     &  AZRES,SYM,QRMK,FMP,AMX,PRX,CALX,RMK,
c     &  QSPA,TIME1,TIME2,
c     &  AVXM,AVFM,XMAG,FMAG,
     &  NRES,SR,SRSQ,SRWT,QNO,
     &  ORG1,ORG2,LAT1,LAT2,LON1,LON2,ZTR,
     &  TEST,ISW,KNO,INST,KNST,POS,XNEAR,XFAR,KAZ,KTEST,SINGMD,IPRN,
     &  LATEP,LONEP,Z,ORG,SE,RMS,QSD,X,DELTA,AZ,AIN,WT,AZWT,NI)
C-------- SOLUTION FOR A SINGLE EARTHQUAKE ----------------------------
      include 'H_param.f'
      CHARACTER*1 SYM(NRMAX),QRMK(NRMAX)
      CHARACTER*1 IW(NSMAX),INS(NSMAX),IEW(NSMAX)
      CHARACTER*3 RMK(NRMAX)
      CHARACTER*4 ISW,IPRO,CHECK,NSTA(NSMAX)
      CHARACTER*4 PRMK(NRMAX),SRMK(NRMAX)
      CHARACTER*4 WRK(NRMAX),AZRES(NRMAX)
      CHARACTER*48 AHEAD
      CHARACTER*80 SUCARD
      CHARACTER*1 QS,QD,QSD(2)
      INTEGER*4 ISKP(4),LA(10),LO(10)
      INTEGER*4 KDX(NRMAX),KEY(NRMAX),JMIN(NRMAX),LDX(NRMAX),KDX2(NRMAX)
      INTEGER*4 ICAL(NSMAX),KLAS(NSMAX),MNO(NSMAX),KSMP(NSMAX)
      INTEGER*4 JDX(NSMAX),NRES(2,NSMAX)
      INTEGER*4 NI,NS,NR,NV,KV,NL,INST,KNST,KAZ,KTEST,IPRN,NEAR,SINGMD
      INTEGER*4 KDATE,KHR,KSORT
c      INTEGER*4 NXM(NSMAX),NFM(NSMAX)
      REAL*4 LATRT,LONRT,LATSV,LONSV
      REAL*4 LAT1,LON1,LAT2,LON2,LATEP,LONEP,MAG,LATR,LONR
      REAL*4 QNO(4),XMEAN(4),SUM(5),WF(41),ALZ(10)
      REAL*4 V(2,21),D(21),VSQ(2,21),THK(21),H(21),DEPTH(21)
      REAL*4 TID(2,21,21),DID(2,21,21),F(21,21),G(2,4,21)
      REAL*4 SR(2,NSMAX),SRSQ(2,NSMAX),SRWT(2,NSMAX)
      REAL*4 AF(3),B(4),Y(4),SE(4),TEST(20),X(4,NRMAX),QSPA(9,40)
      REAL*4 FLT(2,NSMAX),DLY(2,NSMAX)
      REAL*4 AMX(NRMAX),PRX(NRMAX),CALX(NRMAX),XMAG(NRMAX)
      REAL*4 FMP(NRMAX),FMAG(NRMAX),TEMP(NRMAX),W(NRMAX),WS(NRMAX)
      REAL*4 DELTA(NRMAX),DX(NRMAX),DY(NRMAX),ANIN(NRMAX),AIN(NRMAX)
      REAL*4 AZ(NRMAX),WT(NRMAX),T(NRMAX),P(NRMAX),TP(NRMAX),DT(NRMAX)
      REAL*4 S(NRMAX),TS(NRMAX),FMGC(NSMAX),XMGC(NSMAX),PRR(NSMAX)
      REAL*4 CALR(NSMAX),LAT(NSMAX),LON(NSMAX)
      REAL*4 elev(NRMAX),AZWT(NRMAX),ELEV2(NRMAX)
      REAL*4 ORG1,ORG2,ORG,ZTR,XFAR,XNEAR,XFN,POS,PMIN,RMSSQ,GAP
c      REAL*4 SXM(NSMAX),SXMSQ(NSMAX),SFM(NSMAX),SFMSQ(NSMAX)
      REAL*8 TIME1,TIME2
      COMMON/C1/ IQ,KMS,KFM,IPUN,IMAG,IR,KPAPER,KSORT,KSEL
      COMMON/C2/ LATR,LONR,ONF,FLIM
      COMMON/C3/ AHEAD,IPRO
      COMMON/C4/ NEAR,IEXIT,IDXS
c      COMMON/C5/ PMIN,XFN
      COMMON/O1/ IPH,JPH,NDEC,JMAX,JAV,KF,KP,KZ,KKF
      COMMON/O2/ AVRPS,DMIN,RMSSQ,ADJSQ,ZSQ,AVR,AAR
      COMMON/O3/ SUCARD
c      COMMON/O4/ delta
      COMMON/O5/ QS,QD
c******** besoin de iheter pour refroidir le calcul de trvhet si iheter=
c      common/heter2/iheter,xorgh,yorgh,cphih,sphih,xlatc,xlonc
c      common/provi/epsob,iflag,elev(NSMAX)
c      common/gradi/nlecp
Cf2py intent(out) LONEP,LATEP,Z,ORG,RMS,QSD,NI
Cf2py intent(inout) SE,X,DELTA,AZ,AIN,WT,AZWT
c
      DATA WF/.95,0.95,0.95,0.95,0.95,0.95,0.94,0.94,0.94,0.93,
     1       0.92,0.92,0.91,0.90,0.88,0.87,0.85,0.83,0.80,0.77,
     2       0.73,0.69,0.64,0.59,0.53,0.47,0.41,0.34,0.28,0.23,
     3       0.18,0.14,0.11,0.08,0.06,0.04,0.03,0.02,0.01,0.01,0./
      DATA LA/1,1,1,1,0,0,-1,-1,-1,-1/,
     1     LO/+1,-1,+1,-1,0,0,+1,-1,+1,-1/,
     2     ALZ/-1.0,-1.0,+1.0,+1.0,-1.732,+1.732,-1.0,-1.0,+1.0,+1.0/
c************** on modifie iheter pour la premiere passe iflag=0 durant
c     ihetol=iheter
c     iheter=0
C-----------------------------------------------------------------------
      IF (IPRN .GE. 1) THEN
        write(*,15)
   15   FORMAT(///,' **** RUNNING HYPO71PC (Version: SC3/ROB) **** ',/)
      END IF
C
C------- FROM input2.f -------------------------------------------------
C-- Moved in front of input1.f because IDXS needs to be set correctly
      DO 84 L=1,NRP
      TP(L)=60.*JMIN(L)+P(L)+DT(L)
   84 CONTINUE
      NOS=NR-NRP
      IDXS=0
      IF (NOS .GT. 0) IDXS=1
      DO 88 L=1,NOS
      TS(L)=60.*JMIN(L+NRP)+S(L)+DT(L+NRP)
   88 CONTINUE
      PMIN=9999.
      DO 89 L=1,NRP
      IF(TP(L).GE.PMIN) GO TO 89
      PMIN=TP(L)
      NEAR=L
   89 CONTINUE
      TIME2=1.D+06*KDATE+1.D+04*KHR+1.D+02*JMIN(NEAR)
C
C------- FROM input1.f -------------------------------------------------
C
    2 FORMAT(///,13X,'TEST(1)  TEST(2)  TEST(3)  TEST(4)  TEST(5)  TEST(6
     1)  TEST(7)  TEST(8)  TEST(9) TEST(10) TEST(11) TEST(12) TEST(13)')
    3 FORMAT(' STANDARD ',13F9.4)
      IF (IPRN .GE. 1) THEN
          WRITE(*,2)
          WRITE(*,3) (TEST(I),I=1,13)
      END IF
C------- SQUARE SOME TEST-VARIABLES FOR LATER USE ----------------------
      TEST(1)=TEST(1)**2
      TEST(2)=TEST(2)**2
      TEST(4)=TEST(4)**2
C------- INPUT CRUSTAL MODEL -------------------------------------------
      DO 109 L=1,NL
      DEPTH(L)=D(L)
      VSQ(1,L)=V(1,L)**2
      VSQ(2,L)=V(2,L)**2
  109 CONTINUE
C-----LAYER THICKNESS THK
      N1=NL-1
      DO 345 L=1,N1
      THK(L)=D(L+1)-D(L)
  345 H(L)=THK(L)
C---- COMPUTE F & G TERMS
      NV=2
      IF (KNST .EQ. 0 .or. IDXS .EQ. 0) NV=1
      DO 350 KV=1,NV
      DO 350 J=1,NL
      G(KV,1,J)=SQRT(ABS(VSQ(KV,J)-VSQ(KV,1)))/(V(KV,1)*V(KV,J))
      G(KV,2,J)=SQRT(ABS(VSQ(KV,J)-VSQ(KV,2)))/(V(KV,2)*V(KV,J))
      G(KV,3,J)=V(KV,1)/SQRT(ABS(VSQ(KV,J)-VSQ(KV,1))+0.000001)
      G(KV,4,J)=V(KV,2)/SQRT(ABS(VSQ(KV,J)-VSQ(KV,2))+0.000001)
      IF (J .LE. 1) G(KV,1,J)=0.
      IF (J .LE. 2) G(KV,2,J)=0.
      IF (J .LE. 1) G(KV,3,J)=0.
      IF (J .LE. 2) G(KV,4,J)=0.
      DO 350 L=1,NL
      F(L,J)=1.
      IF (L .GE. J) F(L,J)=2.
  350 CONTINUE
C---- COMPUTE TID AND DID
      DO 365 KV=1,NV
      DO 365 J=1,NL
      DO 365 M=1,NL
      TID(KV,J,M)=0.
  365 DID(KV,J,M)=0.
      DO 370 KV=1,NV
      DO 370 J=1,NL
      DO 370 M=J,NL
      IF (M .EQ. 1) GO TO 370
      M1=M-1
      DO 360 L=1,M1
      SQT=SQRT(VSQ(KV,M)-VSQ(KV,L))
      TIM=THK(L)*SQT/(V(KV,L)*V(KV,M))
      DIM=THK(L)*V(KV,L)/SQT
      TID(KV,J,M)=TID(KV,J,M)+F(L,J)*TIM
  360 DID(KV,J,M)=DID(KV,J,M)+F(L,J)*DIM
  370 CONTINUE
      IF (ISW .NE. '1   ') GO TO 200
C---- VARIABLE FIRST LAYER
c      VC=V(1,1)*V(1,2)/SQRT(VSQ(1,2)-VSQ(1,1))
c      DO 180 I=1,NS
c      FLT(1,I)=DLY(1,I)*VC+D(2)
c  180 FLT(2,I)=DLY(2,I)*VC+D(2)
      print *,'Variable first layer not implemented!'
      stop
  200 CONTINUE
C------- FROM main.f -------------------------------------------------
C-------- INITIALIZE SUMMARY OF RESIDUALS ------------------------------
      DO 48 L=1,NS
      NRES(1,L)=0
      NRES(2,L)=0
c      NXM(L)=0
c      NFM(L)=0
      SR(1,L)=0.
      SR(2,L)=0.
      SRSQ(1,L)=0.
      SRSQ(2,L)=0.
      SRWT(1,L)=0.
      SRWT(2,L)=0.
c      SXM(L)=0.
c      SXMSQ(L)=0.
c      SFM(L)=0.
c      SFMSQ(L)=0.
   48 CONTINUE
c      DO 49 I=1,4
c   49 QNO(I)=0.
      XFN=XFAR-XNEAR+0.000001
      TIME1=TIME2
      KSORT=1
C------- Initialize unused arrays --------------------------------------
      DO 43 L=1,NS
      FMGC(L)=0.
      XMGC(L)=0.
      KLAS(L)=0
      PRR(L)=0.
      CALR(L)=0.
      ICAL(L)=0
   43 CONTINUE
      DO 44 L=1,NR
      AMX(L)=0.
      PRX(L)=0.
      CALX(L)=0.
      XMAG(L)=99.9
      FMAG(L)=99.9
      FMP(L)=0.
      RMK(L)='   '
   44 CONTINUE
C-----------------------------------------------------------------------
      LATRT=0.
      LONRT=0.
      LATSV=0.
      LONSV=0.
  778 AVRPS = 0.0
      IEXIT=0
c      ZRES=P(NR+1)
c      KNST=JMIN(NR+1)/10
c      INST=JMIN(NR+1)-KNST*10
c      NRP=NR
c      nlecp=nrp
   30 IF (IDXS .EQ. 0) GO TO 80
C------- TREAT S DATA BY AUGMENTING P DATA -----------------------------
      NOS=0
c     DO 65 I=1,NRP
      DO 65 I=1,NRMAX
      IF (LDX(I) .EQ. 0) GO TO 65
      NOS=NOS+1
      NRS=NRP+NOS
c      TP(NRS)=TS(I)
c      W(NRS)=WS(I)
      TP(NRS)=TS(NOS)
      W(NRS)=WS(NOS)
      KSMP(NRS)=0
      IF ((KNST.NE.1).AND.(KNST.NE.6)) W(NRS)=0.
c      KDX(NRS)=KDX(I)
c      LDX(I)=NRS
      WRK(NRS)='    '
   65 CONTINUE
      NR=NRP+NOS
      IF (IPRN .GE. 1) THEN
          print *, 'NRP, NOS, NR: ',NRP,NOS,NR
      END IF
c      nlecp=nrp
C------- INITIALIZE TRIAL HYPOCENTER -----------------------------------
   80 K=KDX(NEAR)
      SVY1 = 0.0
      SVY2 = 0.0
      SVY3 = 0.0
      ERLMT = 0.
      DO 25 I = 1,3
      ISKP(I)=0
   25 CONTINUE
      IF (INST .NE. 9) GO TO 90
c      READ(12,85) ORG1,ORG2,LAT1,LAT2,LON1,LON2,Z
c   85 FORMAT(F5.0,F5.2,I5,F5.2,I5,2F5.2)
      ORG=60.*ORG1+ORG2
      LATEP=60.*LAT1+LAT2
      LONEP=60.*LON1+LON2
      GO TO 105
   90 IF (NR .GE. TEST(14)) GO TO 100
   96 WRITE(*,97)
   97 FORMAT(' ***** INSUFFICIENT DATA FOR LOCATING THIS QUAKE:')
      KKF = 1
      IF( NRP .EQ. 0 ) NRP = 1
      DO 98 L=1,NRP
c---- volcniques gua
      delta(i)=3
      K=KDX(I)
   98 WRITE(*,599) KDATE,KHR,JMIN(K),P(K),S(K),fmp(K),nsta(K),prmk(K)
c   98 WRITE(*,99) MSTA(L),PRMK(L),KDATE,KHR,JMIN(L),P(L),S(L)
c   99 FORMAT(5X,2A4,1X,I6,2I2,F5.2,7X,F5.2,f5.2)
  599 FORMAT(I6,1x,I2,1x,i2,1x,F5.2,7X,F5.2,2x,f5.2,1x,2a4)
      IEXIT=1
      IF (NRP .EQ. 1) RETURN
c     IF (NRP .EQ. 1) then
c       iheter=ihetol
c       RETURN
c     endif
      GO TO 575
  100 Z=ZTR
      zsv=ztr
c      IF (AZRES(NRP+1).NE. '    ') Z=ZRES
      ORG=PMIN-Z/5.-1.
      IF(LATRT.EQ.0.) GO TO 102
      LATEP=LATRT
      LONEP=LONRT
      GO TO 105
  102 IF (LATR .EQ. 0.) GO TO 104
      LATEP=LATR
      LONEP=LONR
      GO TO 105
  104 LATEP=LAT(K)+0.1
      LONEP=LON(K)+0.1
  105 ADJSQ=0.
      IPH=0
      NDEC=0
      PRMSSQ=100000.
      IF (ISW .EQ. '1   ') KNO=MNO(K)
      IF(ISW .EQ. '1   ') FLTEP=FLT(KNO,K)
      NIMAX=TEST(11)+.0001
C------- GEIGER'S ITERATION TO FIND HYPOCENTRAL ADJUSTMENTS ------------
  777 NI = 1
      IF (INST .EQ. 9) NI=NIMAX
  111 IF(ERLMT .EQ. 0.) GO TO 110
      LATEP = LATSV + LA(NA)*DELAT
      LONEP = LONSV + LO(NA)*DELON
      Z = ZSV + ALZ(NA)*DEZ
      IF(Z .LT.test(15)) Z=test(15)
  110 FMO=0.
      FNO=0.
      IF (IPRN .GE. 1) THEN
          print *, 'NI=',NI,', NDEC=',NDEC
      END IF
C** START AL LINDH'S MODIFICATION
      IF (SINGMD .EQ. 1) DELMIN = 99999.
C** END AL LINDH'S MODIFICATION
      DO 112 I=1,5
  112 SUM(I)=0.
      IF (IPRN .GE. 1) THEN
          print *, 'Hypocenter: ',LONEP/60.,LATEP/60.,Z,ORG
      END IF
C------- CALCULATE EPICENTRAL DISTANCE BY RICHTER'S METHOD -------------
C-- Note: in original hypo71 version:
C-- LON/LAT coordinates are assumed to be absolute values
C-- This is OK for computing distances,
C-- in azwtos.f, sign of DX/DY is changed if necessary
C-- this probably also modifies DX/DY in main routine,
C-- so partial derivatives are probably also correct
C-- As we use signed coordinates throughout, we need alternative KDX2
      DO 120 I=1,NR
      KDX2(I) = I
      JI=KDX(I)
      PHI = 0.0174532 * ((LAT(JI)+LATEP)/120.)
      SINPHI = SIN(PHI)
      SINP2  = SINPHI**2
      SINP4  = SINP2**2
      CA = 1.8553654 + 0.0062792*SINP2 + 0.0000319*SINP4
      CB = 1.8428071 + 0.0187098*SINP2 + 0.0001583*SINP4
      DX(I) = (LON(JI)-LONEP) * CA * COS(PHI)
      DY(I) = (LAT(JI)-LATEP) * CB
      DELTA(I)=SQRT(DX(I)**2+DY(I)**2)+0.000001
      WT(I)=W(I)
      ELEV2(I) = elev(JI)
      IF (SINGMD .EQ. 1) GO TO 113
      IF (NI .LE. 1) GO TO 115
C------- DISTANCE WEIGHTING --------------------------------------------
      IF (DELTA(I) .LE. XNEAR) GO TO 115
      WT(I)=W(I)*(XFAR-DELTA(I))/XFN
      GO TO 114
C** START AL LINDH'S MODIFICATION (TO PREVENT STATIONS WEIGHTED OUT)
  113 DELMIN = AMIN1(DELTA(I),DELMIN)
      YFAR = AMAX1(XFAR,3.*DELMIN)
      IF (NI .LE. 3) GOTO 115
      IF (DELTA(I) .GT. XNEAR) WT(I)=W(I)*(YFAR-DELTA(I))/(YFAR-XNEAR)
C** END AL LINDH'S MODIFICATION
  114 IF (WT(I) .LT. 0.005) WT(I)=0.
  115 IF (WT(I) .EQ. 0.) GO TO 120
      IF (KSMP(I) .EQ. 1) FMO=FMO+1.
      FNO=FNO+1.
      SUM(4)=SUM(4)+WT(I)
  120 CONTINUE
      IF (FNO .LT. TEST(14)) GO TO 96
      AVWT=SUM(4)/FNO
C------- NORMALIZE DISTANCE WEIGHTS ------------------------------------
      SUM(4)=0.0
      DO 122 I=1,NR
  122 WT(I)=WT(I)/AVWT
      IF ((NI.LE.2).OR.(KAZ.EQ.0)) GO TO 130
C------- AZIMUTHAL WEIGHTING -------------------------------------------
C-- Note: KDX or KDX2 is not important
C-- because we disabled change of sign for DX/DY in AZWTOS
      CALL AZWTOS(DX,DY,NR,WT,KDX,AZ,AZWT,KEY,INS,IEW,GAP)
      DO 123 I=1,NR
  123 WT(I)=WT(I)*AZWT(I)
C------- COMPUTE TRAVEL TIMES & DERIVATIVES ----------------------------
  130 ZSQ=Z**2
c************** on entre dans trvdrv quand iflag=0 ( premiere passe ou
c               premier passage de la deuxieme passe )
C-- Bug in hypo71?
C-- Replaced KDX with KDX2 (simple range from 1 to NR)
C-- Because DELTA, DX, DY correspond to phases, not stations!
C-- Original KDX only works if all stations are in order
C-- and there are no unused stations or missing P phases
      if(iflag.eq.0) CALL TRVDRV(ISW,V,D,DEPTH,VSQ,NL,THK,H,G,F,
     &  TID,DID,FLT,DELTA,DX,DY,ELEV2,NR,KDX2,KNO,FLTEP,Z,ZSQ,NV,NRP,
     &  X,T,ANIN)
c      print *, 'T: ', T(1:NR)
  131 FDLY=1.
      IF (ISW .EQ. '1   ') FDLY=0.
C------- CALCULATE TRAVEL TIME RESIDUALS X(4,I) & MODIFY THE DERIV'S ---
      DO 150 I=1,NR
      JI=KDX(I)
      IF (I .LE. NRP) GO TO 145
C------- S PHASE DATA --------------------------------------------------
C IF MODEL S used, continue like P wave - HM
C
      IF (NV .EQ. 2) GO TO 146
      T(I)=POS*T(I)
      X(1,I)=POS*X(1,I)
      X(2,I)=POS*X(2,I)
      X(3,I)=POS*X(3,I)
      X(4,I)=TP(I)-T(I)-ORG-POS*DLY(KNO,JI)*FDLY
      GO TO 150
  145 IF (KSMP(I) .EQ. 0) GO TO 146
C------- S-P DATA ------------------------------------------------------
      X(1,I)=(POS-1.)*X(1,I)
      X(2,I)=(POS-1.)*X(2,I)
      X(3,I)=(POS-1.)*X(3,I)
      X(4,I)=TS(I)-TP(I)-(POS-1.)*(DLY(KNO,JI)*FDLY+T(I))
      GO TO 150
C------- P TRAVEL TIME RESIDUAL ----------------------------------------
  146 X(4,I)=TP(I)-T(I)-ORG-DLY(KNO,JI)*FDLY
  150 CONTINUE
C------- COMPUTE AVR, AAR, RMSSQ, & SDR --------------------------------
      ONF=0.0
      DO 152 I=1,NR
      ONF = ONF + WT(I)*(1-KSMP(I))
      XWT = X(4,I)*WT(I)
      SUM(1)=SUM(1)+XWT
      SUM(2)=SUM(2)+ABS(XWT)
      SUM(3)=SUM(3)+X(4,I)*XWT
      SUM(5)=SUM(5)+XWT*(1-KSMP(I))
  152 CONTINUE
      IF(FNO .GT. FMO) AVRPS=SUM(5)/(ONF)
      AVR=SUM(1)/FNO
      AAR=SUM(2)/FNO
      IF (SINGMD .EQ. 1) GO TO 1520
      RMSSQ=SUM(3)/FNO
      GO TO 1521
C** START AL LINDH'S MODIFICATION
 1520 RMSSQ=SUM(3)/AMAX1(1.,FNO-4.)
C** END AL LINDH'S MODIFICATION
 1521 SDR=SQRT(ABS(RMSSQ-AVR**2))
      DO 153 I=1,5
      SUM(I)= 0.0
  153 CONTINUE
      IF (IPRN .GE. 1) THEN
          print *, 'RMSSQ: ',RMSSQ
      END IF
      IF (SINGMD .EQ. 1) GO TO 1530
      IF (RMSSQ .GE. TEST(1)) GO TO 154
      GO TO 1531
C** START AL LINDH'S MODIFICATION (START JEFFREYS WEIGHTING ON 4TH
C                                  ITERATION)
 1530 IF ((RMSSQ .GE. TEST(1)) .AND. (NI .GT. 3)) GO TO 154
C** END AL LINDH'S MODIFICATION
 1531 IF(ERLMT .EQ. 1.) GO TO 167
      IF(INST.EQ.9) GO TO 501
      IF(NI .GE. 2) GO TO 167
      GO TO 165
C------- JEFFREYS' WEIGHTING -------------------------------------------
  154 FMO=0.
      FNO=0.
      IF (IPRN .GE. 1) THEN
          print *, 'Jeffreys weighting'
      END IF
      DO 160 I=1,NR
      WRK(I)='    '
      IF (WT(I) .EQ. 0.) GO TO 160
      K=10.*ABS(X(4,I)-AVR)/SDR+1.5
      IF (K .GT. 41) K=41
      WT(I)=WT(I)*WF(K)
      IF (K .GT. 30) WRK(I)='****'
      IF (WT(I) .LT. 0.005) WT(I)=0.
      IF (WT(I) .EQ. 0.) GO TO 160
      IF (KSMP(I) .EQ. 1) FMO=FMO+1.
      FNO=FNO+1.
      SUM(4)=SUM(4)+WT(I)
  160 CONTINUE
      IF (FNO .LT. TEST(14)) GO TO 96
      AVWT=SUM(4)/FNO
      SUM(4)=0.0
      ONF=0.0
      DO 164 I=1,NR
      WT(I)=WT(I)/AVWT
      ONF = ONF + WT(I)*(1-KSMP(I))
      XWT=X(4,I)*WT(I)
      SUM(5)=SUM(5)+XWT*(1-KSMP(I))
  164 CONTINUE
C------- RECALCULATE AVRPS ---------------------------------------------
      IF(ERLMT .EQ. 1.) GO TO 163
      IF(INST .NE. 9) GO TO 163
      AVRPS = 0.0
      IF(FNO .NE. FMO) AVRPS = SUM(5)/ONF
      GO TO 501
  163 IF(FNO.EQ.FMO) AVRPS=0.0
      IF(FNO.EQ.FMO) GO TO 167
      AVRPS=SUM(5)/(ONF)
      SUM(5)=0.0
      IF(ERLMT .EQ. 1.) GO TO 167
C------- RESET FIRST ORIGIN TIME ---------------------------------------
      IF(NI.GE. 2) GO TO 167
  165 ORG=ORG+AVRPS
      IF (IPRN .GE. 1) THEN
          print *, 'Reset first origin time +',AVRPS,'->',ORG
      END IF
      DO 166 I=1,NR
      IF(KSMP(I) .EQ. 0) X(4,I)=X(4,I)-AVRPS
      XWT=WT(I)*X(4,I)
      SUM(5)=SUM(5)+XWT*(1 - KSMP(I))
      SUM(2)=SUM(2)+ABS(XWT)
      SUM(3)=SUM(3)+X(4,I)*XWT
  166 CONTINUE
      IF(FNO .GT. FMO) AVRPS=SUM(5)/(ONF)
      AAR=SUM(2)/FNO
      IF (SINGMD .EQ. 1) GO TO 1661
      RMSSQ = SUM(3)/FNO
      GO TO 1662
C** START AL LINDH'S MODIFICATION
 1661 RMSSQ = SUM(3)/AMAX1(1.,FNO-4.)
C** END AL LINDH'S MODIFICATION
 1662 GO TO 169
C------- FOR NI>1, COMPUTE AAR, & RMSSQ AS IF AVRPS=0. -----------------
  167 DO 168 I=1,NR
      XWT=WT(I)*(X(4,I)-AVRPS*(1-KSMP(I)))
      SUM(2)=SUM(2)+ABS(XWT)
      SUM(3)=SUM(3)+(X(4,I)-AVRPS*(1-KSMP(I)))*XWT
  168 CONTINUE
      AAR=SUM(2)/FNO
      IF (SINGMD .EQ. 1) GO TO 1681
      RMSSQ=SUM(3)/FNO
      GO TO 1682
C** START AL LINDH'S MODIFICATION
 1681 RMSSQ = SUM(3)/AMAX1(1.,FNO-4.)
C** END AL LINDH'S MODIFICATION
 1682 IF(ERLMT .EQ. 0.) GO TO 169
C------- OUTPUT RMS ERROR OF AUXILIARY POINTS --------------------------
      L = LATEP/60.
      ALA = LATEP - 60.*L
      L = LONEP/60.
      ALO = LONEP - 60.*L
      RMSX= SQRT(RMSSQ)
      DRMS = RMSX - RMSSV
      GO TO (1,2,3,4,5,6,1,2,3,4), NA
    1 WRITE(*,801) ALA,ALO,Z,AVRPS,RMSX,DRMS
  801 FORMAT(5F10.2,10X,F6.2)
      GO TO 174
    2 WRITE(*,802) ALA,ALO,Z,AVRPS,RMSX,DRMS
  802 FORMAT(5F10.2,28X,F6.2)
      GO TO 174
    3 WRITE(*,803) ALA,ALO,Z,AVRPS,RMSX,DRMS
  803 FORMAT(5F10.2,13X,'(',F6.2,')')
      GO TO 174
    4 WRITE(*,804) ALA,ALO,Z,AVRPS,RMSX,DRMS
  804 FORMAT(5F10.2,31X,'(',F6.2,')')
      IF(NA .EQ. 10) GO TO 550
      GO TO 174
    5 WRITE(*,805) ALA,ALO,Z,AVRPS,RMSX,DRMS
  805 FORMAT(/5F10.2,19X,F6.2)
      WRITE(*,807) RMSSV
  807 FORMAT(40X,F10.2,23X,'0.00')
      GO TO 174
    6 WRITE(*,806) ALA,ALO,Z,AVRPS,RMSX,DRMS
  806 FORMAT(5F10.2,22X,'(',F6.2,')'/)
  174 NA = NA + 1
      GO TO 111
C------- CHECK IF SOLUTION IS BETTER THAN PREVIOUS ONE -----------------
  169 IF((NI .EQ. 1) .AND. (NDEC .EQ. 0)) GO TO 170
      IF(PRMSSQ.GE.RMSSQ) GO TO 170
      IF (IPRN .GE. 1) THEN
          print *, 'Solution worse than previous one!'
      END IF
      NDEC = NDEC +1
      IF(NDEC .GT. 1) GO TO 175
      DO 177 I= 1,3
      B(I) = 0.0
      AF(I)=-1.0
      SE(I) = 0.0
  177 CONTINUE
      NI = NI -1
      BM1=Y(1)
      BM2=Y(2)
      BM3=Y(3)
      BMAX = ABS(Y(1))
      IIMAX = 1
      DO 176 I = 2,3
      IF(ABS(Y(I)).LE.BMAX) GO TO 176
      BMAX = ABS(Y(I))
      IIMAX = I
  176 CONTINUE
      ISKP(IIMAX)=1
      Y(1)=-BM1/5.
      Y(2)=-BM2/5.
      Y(3)=-BM3/5.
      Y(4)=-Y(1)*XMEAN(1)-Y(2)*XMEAN(2)-Y(3)*XMEAN(3)
      XADJSQ=Y(1)**2+Y(2)**2+Y(3)**2
      KP=0
      IF(XADJSQ .LT. 4.*TEST(4)/25.) GO TO 170
  175 IF(NDEC .EQ. 5) GO TO 170
      GO TO 325
C------- STEPWISE MULTIPLE REGRESSION ANALYSIS OF TRAVEL TIME RESIDUALS-
  170 IF(NDEC .GE. 1) NI = NI + 1
      IF (INST.EQ.1) GO TO 250
      IF(ISKP(3) .EQ. 1) GO TO 250
      IF (INST .EQ. 9) GO TO 501
      IF ((FNO.EQ.4) .AND. (FMO.LT.4)) GO TO 250
C---- FREE SOLUTION
      KZ=0
      KF=0
      CALL SWMREG(TEST,IPRN,NR,KSMP,FNO,X,WT,ISKP,KF,KZ,XMEAN,
     &  B,Y,SE,AF,ONF,FLIM)
C------- AVOID CORRECTING DEPTH IF HORIZONTAL CHANGE IS LARGE ----------
      IF (Y(1)**2+Y(2)**2 .LT. TEST(2)) GO TO 300
C---- FIXED DEPTH SOLUTION
  250 KZ=1
      KF=0
      CALL SWMREG(TEST,IPRN,NR,KSMP,FNO,X,WT,ISKP,KF,KZ,XMEAN,
     &  B,Y,SE,AF,ONF,FLIM)
C------- LIMIT FOCAL DEPTH CHANGE & AVOID HYPOCENTER IN THE AIR --------
  300 DO 275 I= 1,3
      ISKP(I)=0
  275 CONTINUE
      OLDY1=Y(1)
      OLDY2=Y(2)
      OLDY3=Y(3)
      ABSY1=ABS(Y(1))
      ABSY2=ABS(Y(2))
      ABSY3=ABS(Y(3))
      IF(ABSY1.GT.ABSY2) GO TO 305
      ABSGR=ABSY2
      GO TO 308
  305 ABSGR=ABSY1
  308 IF(ABSY3.LE.TEST(5)) GO TO 310
      I=ABSY3/TEST(5)
      Y(3)=Y(3)/(I+1)
  310 CONTINUE
c      print *,'------>',z,y(3),z+y(3),test(15)
      IF((Z+Y(3)).GT.test(15)) GO TO 315
      Y(3)=-Z*TEST(12)+.000001
      ISKP(3) = 1
C------- LIMIT HORIZONTAL ADJUSTMENT OF EPICENTER ----------------------
  315 CONTINUE
c      print *,z,y(3)
      IF(ABSGR.LE.TEST(10)) GO TO 320
      I=ABSGR/TEST(10)
      Y(1)=Y(1)/(I+1)
      Y(2)=Y(2)/(I+1)
  320 Y(4)=Y(4)-(Y(3)-OLDY3)*XMEAN(3)-(Y(1)-OLDY1)*XMEAN(1)
     1 -(Y(2)-OLDY2)*XMEAN(2)
      XADJSQ=Y(1)**2+Y(2)**2+Y(3)**2
      IF (IPRN .GE. 1) THEN
          print *, 'XADJSQ: ',XADJSQ
      END IF
      KP=0
      NDEC=0
      JPH=0
c************** on sort le resultat si iprn > 1 dans le cas ou
c               deuxieme passe alors iflag # 0
c 325 IF (IPRN .GE. 1.and.(iflag.ne.0.or.ihetol.eq.0)) CALL OUTPUT
  325 IF (IPRN .GE. 1) CALL OUTPUT
     &  (TEST,INST,KNST,KNO,IW,INS,IEW,DLY,FMGC,XMGC,
     &  KLAS,PRR,CALR,ICAL,FLT,QSPA,NSTA,KDATE,KHR,NR,NRP,NS,
     &  PRMK,JMIN,P,S,SRMK,AMX,PRX,CALX,RMK,DT,FMP,AZRES,QRMK,KDX,LDX,
     &  WT,TP,T,WRK,KSMP,TS,TIME1,TIME2,DELTA,DX,DY,AVXM,
     &  XMAG,AVFM,FMAG,MAG,FNO,X,B,Y,SE,AF,AZ,AIN,ANIN,TEMP,KEY,
     &  LATEP,LONEP,Z,ORG,NI)
      IF(NDEC .GE. 1) GO TO 330
C------- TERMINATE ITERATION IF HYPOCENTER ADJUSTMENT < TEST(4) --------
      IF (SINGMD .EQ. 1) GO TO 326
      IF (XADJSQ .LT. TEST(4)) GO TO 500
      GO TO 330
C** START AL LINDH'S MODIFICATION (FORCING AT LEAST 5 ITERATIONS)
  326 IF ((XADJSQ .LT. TEST(4)) .AND. (NI .GT. 4)) GO TO 500
C** END AL LINDH'S MODIFICATION
  330 IF(NI .EQ. NIMAX) GO TO 500
C------- ADJUST HYPOCENTER ---------------------------------------------
      IF (IPRN .GE. 1) THEN
        print *, 'Hypocentral adjustment:'
        print *, '  X=',Y(1),', Y=',Y(2),', Z=',Y(3),' km, T=',Y(4),' s'
      END IF
      PHI = 0.0174532 * (LATEP/60.)
      SINPHI = SIN(PHI)
      SINP2  = SINPHI**2
      SINP4  = SINP2**2
      CA = 1.8553654 + 0.0062792*SINP2 + 0.0000319*SINP4
      CB = 1.8428071 + 0.0187098*SINP2 + 0.0001583*SINP4
      LATEP = LATEP + (Y(2)/CB)
      LONEP = LONEP + (Y(1)/(CA*COS(PHI)))
      Z=Z+Y(3)
      ORG=ORG+Y(4)
      SVY1 = Y(1)
      SVY2 = Y(2)
      SVY3 = Y(3)
      ADJSQ=XADJSQ
      IF(NDEC .EQ. 0) PRMSSQ=RMSSQ
      IF(NDEC.GE.1) GO TO 110
      NI = NI + 1
      IF(NI .LE. NIMAX) GO TO 111
C------- RESET ORIGIN TIME ---------------------------------------------
  500 ORG=ORG+XMEAN(4)
      GO TO 502
  501 XMEAN(4)=0.0
  502 DO 505 I=1,5
  505 SUM(I)=0.0
      SUMM = 0.0
      DO 510 I=1,NR
      IF (KSMP(I) .EQ. 0) X(4,I)=X(4,I)-XMEAN(4)
      IF (WT(I) .EQ. 0.) GO TO 510
      IF(INST .NE. 9) GO TO 509
      XWTS=WT(I)*(X(4,I)**2)
      IF(KSMP(I) .EQ. 0) XWTS=WT(I)*((X(4,I)-AVRPS)**2)
      SUMM = SUMM + XWTS
  509 XWT=X(4,I)*WT(I)
      SUM(1)=SUM(1)+XWT
      SUM(2)=SUM(2)+ABS(XWT)
      SUM(3)=SUM(3)+X(4,I)*XWT
      SUM(5)=SUM(5)+XWT*(1-KSMP(I))
  510 CONTINUE
      RM9SV = SUMM/FNO
      AVR=SUM(1)/FNO
      AVRPS = 0.0
      IF(FNO .GT. FMO) AVRPS=SUM(5)/ONF
      AAR=SUM(2)/FNO
      IF (SINGMD .EQ. 1) GO TO 511
      RMSSQ=SUM(3)/FNO
      GO TO 512
C** START AL LINDH'S MODIFICATION
  511 RMSSQ=SUM(3)/AMAX1(1.,FNO-4.)
C** END AL LINDH'S MODIFICATION
C------- COMPUTE ERROR ESTIMATES BY SOLVING FULL NORMAL EQUATION -------
  512 KF=2
      KP=1
      KZ=0
      CALL SWMREG(TEST,IPRN,NR,KSMP,FNO,X,WT,ISKP,KF,KZ,XMEAN,
     &  B,Y,SE,AF,ONF,FLIM)
      DO 521 I =1,3
  521 Y(I)=0.0
      IF(INST.EQ.1) KZ = 1
c***************  on donne si ihetol=0 ou iflag # 0  voir plus haut
c     if(iflag.ne.0.or.ihetol.eq.0)
       CALL OUTPUT(TEST,INST,KNST,KNO,IW,INS,IEW,DLY,FMGC,XMGC,
     &  KLAS,PRR,CALR,ICAL,FLT,QSPA,NSTA,KDATE,KHR,NR,NRP,NS,
     &  PRMK,JMIN,P,S,SRMK,AMX,PRX,CALX,RMK,DT,FMP,AZRES,QRMK,KDX,LDX,
     &  WT,TP,T,WRK,KSMP,TS,TIME1,TIME2,DELTA,DX,DY,AVXM,
     &  XMAG,AVFM,FMAG,MAG,FNO,X,B,Y,SE,AF,AZ,AIN,ANIN,TEMP,KEY,
     &  LATEP,LONEP,Z,ORG,NI)
       QSD(1) = QS
       QSD(2) = QD
c      IF (KMS .EQ. 1) CALL MISING
c     &  (NSTA,LAT,LON,NS,MAG,TEMP,DMIN,JDX,
c     &  JMAX,LATEP,LONEP,INS,IEW)
c      IF ((KNST.GE.5) .OR. (KFM.GE.1)) CALL FMPLOT
c     &                   (KPAPER,KFM,FNO,NRP,AZ,AIN,SYM,SUCARD)
c      QNO(JAV)=QNO(JAV)+1.
c      IF (JAV .GT. IQ) GO TO 523
C------- COMPUTE SUMMARY OF TRAVEL TIME RESIDUALS ----------------------
      DO 522 I=1,NRP
      IF ((WT(I).EQ.0.) .OR. (KSMP(I).EQ.1))  GO TO 522
      JI=KDX(I)
      NRES(KNO,JI)=NRES(KNO,JI)+1
      SR(KNO,JI)=SR(KNO,JI)+X(4,I)*WT(I)
      SRSQ(KNO,JI)=SRSQ(KNO,JI)+X(4,I)**2*WT(I)
      SRWT(KNO,JI)=SRWT(KNO,JI)+WT(I)
  522 CONTINUE
  523 IF (KTEST .NE. 1.) goto 550
C------- COMPUTE RMS AT AUXILIARY POINTS -------------------------------
      RMSSV = SQRT(RMSSQ)
      IF(INST.EQ.9) RMSSV = SQRT(RM9SV)
      ERLMT = 1.
      LATSV = LATEP
      LONSV = LONEP
      ZSV = Z
      PHI = 0.0174532 * (LATEP/60.)
      SINPHI = SIN(PHI)
      SINP2  = SINPHI**2
      SINP4  = SINP2**2
      CA = 1.8553654 + 0.0062792*SINP2 + 0.0000319*SINP4
      CB = 1.8428071 + 0.0187098*SINP2 + 0.0001583*SINP4
      DELAT = TEST(13)/CB
      DELON = TEST(13)/(CA*COS(PHI))
      DEZ = TEST(13)
      WRITE (*,525)
  525 FORMAT (/'       LAT       LON         Z     AVRPS       RMS
     1                DRMS'/)
      NA=1
      GO TO 111
  550 TIME1=TIME2
  575 CONTINUE
C------- CHECK FOR MULTIPLE SOLUTIONS OF THE SAME EARTHQUAKE -----------
c      IF(IPRO.NE.' ** ') RETURN
c      NR=NRP
c      NRP1=NR +1
c      READ(12,600)  CHECK,IPRO,KNST,INST,ZRES,LAT1,LAT2,LON1,LON2,
c     1 AZRES(NRP1)
c      WRITE(*,601) CHECK,IPRO,KNST,INST,ZRES,LAT1,LAT2,LON1,LON2
c  601 FORMAT(//2A4,9X,2I1,F5.2,1X,2(I4,F6.2),'--- RUN AGAIN ---')
c  600 FORMAT(2A4,9X,2I1,F5.2,1X,2(I4,F6.2),T21,A4)
c      LATRT=60.*LAT1+LAT2
c      LONRT=60.*LON1+LON2
c      IF(CHECK.EQ.'    ') GO TO 30
c      WRITE(*,610) CHECK
c  610 FORMAT(/' ERROR ',A4,' SKIPPED.   INST. CARD DID NOT FOLLOW ***')
      RETURN
      END
c-------------------
      SUBROUTINE OUTPUT(TEST,INST,KNST,KNO,IW,INS,IEW,DLY,FMGC,XMGC,
     &  KLAS,PRR,CALR,ICAL,FLT,QSPA,NSTA,KDATE,KHR,NR,NRP,NS,
     &  PRMK,JMIN,P,S,SRMK,AMX,PRX,CALX,RMK,DT,FMP,AZRES,QRMK,KDX,LDX,
     &  WT,TP,T,WRK,KSMP,TS,TIME1,TIME2,DELTA,DX,DY,AVXM,
     &  XMAG,AVFM,FMAG,MAG,FNO,X,B,Y,SE,AF,AZ,AIN,ANIN,TEMP,KEY,
     &  LATEP,LONEP,Z,ORG,NI)
      include 'H_param.f'
C------- OUTPUT HYPOCENTER ---------------------------------------------
      CHARACTER*1 RMKO,RMK2,RMK3,RMK4,Q,QS,QD,SYM3
      CHARACTER*1 CLASS(4),SYMBOL(5),QRMK(NRMAX),IW(NSMAX)
      CHARACTER*1 INS(NSMAX),IEW(NSMAX)
      CHARACTER*3 RMK(NRMAX)
      CHARACTER*4 ISW,XMAGOU,FMAGOU,SWTOUT,FMPOUT,RMK5,IPRO
      CHARACTER*4 NSTA(NSMAX),PRMK(NRMAX),WRK(NRMAX),AZRES(NRMAX)
      CHARACTER*4 SRMK(NRMAX)
      CHARACTER*5 ERHOUT,SE3OUT
      CHARACTER*6 MAGOUT,SKOUT,TSKOUT,SRESOU,DTKOUT,X4KOUT,TSKCAL
c      character*6 stmp
c      CHARACTER*13 Coord_Cartes
      CHARACTER*48 AHEAD
      CHARACTER*80 SUCARD
      CHARACTER*14 FPRINT,FPUNCH
      INTEGER*4 JMIN(NRMAX),KDX(NRMAX),LDX(NRMAX),KEY(NRMAX)
      INTEGER*4 NI,KSMP(NSMAX),ICAL(NSMAX),KLAS(NSMAX)
      REAL*4 LAT2,LON2,LATEP,LONEP,MAG,LATR,LONR
      REAL*4 AF(3),B(4),Y(4),SE(4),TEST(20),X(4,NRMAX),QSPA(9,40)
      REAL*4 FLT(2,NSMAX),DLY(2,NSMAX)
      REAL*4 AMX(NRMAX),PRX(NRMAX),CALX(NRMAX),CAL(NRMAX),XMAG(NRMAX)
      REAL*4 FMP(NRMAX),FMAG(NRMAX),TEMP(NRMAX),DEMP(NRMAX)
      REAL*4 DELTA(NRMAX),DX(NRMAX),DY(NRMAX),ANIN(NRMAX),AIN(NRMAX)
      REAL*4 AZ(NRMAX),WT(NRMAX),T(NRMAX),P(NRMAX),TP(NRMAX),DT(NRMAX)
      REAL*4 S(NRMAX),TS(NRMAX),FMGC(NSMAX),XMGC(NSMAX),PRR(NSMAX)
      REAL*4 CALR(NSMAX)
      REAL*8 TIME1,TIME2
c      real*8 xut8,yut8
      COMMON/C1/ IQ,KMS,KFM,IPUN,IMAG,IR,KPAPER,KSORT,KSEL
      COMMON/C2/ LATR,LONR,ONF,FLIM
      COMMON/C3/ AHEAD,IPRO
      COMMON/C4/ NEAR,IEXIT,IDXS
c      COMMON/C5/ PMIN,XFN
      COMMON/O1/ IPH,JPH,NDEC,JMAX,JAV,KF,KP,KZ,KKF
      COMMON/O2/ AVRPS,DMIN,RMSSQ,ADJSQ,ZSQ,AVR,AAR
      COMMON/O3/ SUCARD
      COMMON/O5/ QS,QD
c      common/stdio/lui,luo,lua1,lua2
      DATA CLASS/'A','B','C','D'/
      DATA SYMBOL/' ','1','2','Q','*'/
c these next 2 vars are undefined in the code, added in EW7.5
c      CHARACTER*1 Auto_Manuel
c      CHARACTER*6 Fichier_Origine
c      data is2/0/
C-----------------------------------------------------------------------
c      IF ((IPRN.GE.2) .OR. (KP.EQ.1)) CALL XFMAGS
c     & (TEST,FMGC,XMGC,KLAS,PRR,CALR,ICAL,IMAG,IR,QSPA,
c     &  AMX,PRX,CALX,FMP,KDX,DELTA,ZSQ,NRP,CAL,NM,AVXM,SDXM,XMAG,NF,
c     &  AVFM,SDFM,FMAG,MAG)
c
      NM=0
      NF=0
      FPUNCH = 'HYPO71PC.PUN'
      OPEN(7,FILE=FPUNCH,STATUS='unknown')
      FPRINT='HYPO71PC.PRT'
      OPEN(8,FILE=FPRINT,STATUS='unknown')
c
      LAT1=LATEP/60.
      LAT2=LATEP-60.*LAT1
      LON1=LONEP/60.
      LON2=LONEP-60.*LON1
      ADJ=SQRT(ADJSQ)
      RMS=SQRT(RMSSQ)
      JHR=KHR
      OSAVE = ORG
      IF (ORG .GE. 0.) GO TO 5
      ORG=ORG+3600.
      KHR=KHR-1
    5 KMIN=ORG/60.0
      SEC=ORG-60.0*KMIN
      ERH=SQRT(SE(1)**2+SE(2)**2)
      NO=FNO
      RMK2=' '
      RMKO=' '
C---- KZ=1 FOR FIXED DEPTH; ONF=0 FOR ORIGIN TIME BASED ON SMP'S
      IF (ONF .EQ. 0.) RMKO='*'
      IF (KZ .EQ. 1) RMK2='*'
c      JMAX=0
      DO 10 I=1,NR
c      DXI=DX(I)
c      DYI=DY(I)
c      IF ((DXI.EQ.0.).AND.(DYI.EQ.0.)) GO TO 6
c      JI=KDX(I)
c      IF (INS(JI) .EQ. 'S') DYI=-DYI
c      IF (IEW(JI) .EQ. 'W') DXI=-DXI
c      AZ(I)=AMOD(ATAN2(DXI,DYI)*57.29578 + 360., 360.)
c      GO TO 7
c    6 AZ(I)= 999.
c    7 CONTINUE
      AIN(I)=ASIN(ANIN(I))*57.29578
      IF (AIN(I) .LT. 0.) AIN(I)=180.+AIN(I)
      AIN(I)=180.-AIN(I)
c      SWT=0.
c      IF (LDX(I) .EQ. 0.) GO TO 8
c      KK=LDX(I)
c      SWT=WT(KK)
c    8 IF ((WT(I).EQ.0.).AND.(SWT.EQ.0.)) GO TO 10
c      JMAX=JMAX+1
c      TEMP(JMAX)=AZ(I)
   10 CONTINUE
c      CALL SORT(TEMP,KEY,JMAX)
c      GAP=TEMP(1)+360.-TEMP(JMAX)
c      DO 20 I=2,JMAX
c      DTEMP=TEMP(I)-TEMP(I-1)
c      IF (DTEMP .GT. GAP) GAP=DTEMP
c   20 CONTINUE
      CALL AZWTOS(DX,DY,NR,WT,KDX,AZ,TEMP,KEY,INS,IEW,GAP)
      IGAP=GAP+0.5
      DO 25 I=1,NR
      K=KDX(I)
   25 DEMP(K)=DELTA(I)
      CALL SORT(DEMP,KEY,NS)
      DO 27 I=1,NS
      K=KEY(I)
      PWT=0.
      DO 22 J=1,NRP
      IF (KDX(J) .EQ. K) PWT=WT(J)
   22 CONTINUE
      SWT=0.
      IF (LDX(K) .EQ. 0.) GO TO 26
c      KK=LDX(K)
      DO 23 KK=NRP+1,NR
      IF (KDX(KK) .EQ. K) SWT=WT(KK)
   23 CONTINUE
   26 IF ((PWT.GT.0.).OR.(SWT.GT.0.)) GO TO 28
   27 CONTINUE
   28 DMIN=DEMP(I)
      IDMIN=DMIN+0.5
      OFD=Z
      TFD=2.*Z
      IF (OFD .LT. 5.) OFD=5.
      IF (TFD .LT. 10.) TFD=10.
      JS=4
      IF ((RMS.LT.0.50).AND.(ERH.LE.5.0)) JS=3
      IF ((RMS.LT.0.30).AND.(ERH.LE.2.5).AND.(SE(3).LE.5.0)) JS=2
      IF ((RMS.LT.0.15).AND.(ERH.LE.1.0).AND.(SE(3).LE.2.0)) JS=1
      JD=4
      IF (NO .LT. 6) GO TO 30
      IF ((GAP.LE.180.).AND.(DMIN.LE.50.)) JD=3
      IF ((GAP.LE.135.).AND.(DMIN.LE.TFD)) JD=2
      IF ((GAP.LE. 90.).AND.(DMIN.LE.OFD)) JD=1
   30 JAV=(JS+JD+1)/2
      Q=CLASS(JAV)
      QS=CLASS(JS)
      QD=CLASS(JD)
      TIME2=SEC+1.D+02*KMIN+1.D+04*KHR+1.D+06*KDATE
      IF(IPRN .EQ. 0) GO TO 52
      IF(NI .NE. 1) GO TO 60
      IF(NDEC .GE. 1) GO TO 60
      IF (JPH .EQ. 1) GO TO 60
   52 KKYR=KDATE/10000
      KKMO=(KDATE-KKYR*10000)/100
      KKDAY=(KDATE-KKYR*10000-KKMO*100)
      JPH=1
      IF(KSEL) 501,501,505
  501 WRITE(8,502)
  502 FORMAT(///)
      GO TO 535
  505 WRITE(8,506)
  506 FORMAT(1H1)
      WRITE(8,53) AHEAD,KKYR,KKMO,KKDAY,KHR,KMIN
   53 FORMAT(/,30X,A48,T112,I2,'/',I2,'/',I2,4X,I2,':',I2)
  535 IF( TIME2 - TIME1 .GT. -20.)GO TO 60
      WRITE(8,54)
   54 FORMAT(' ***** FOLLOWING EVENT IS OUT OF ORDER *****')
   60 IF ((KP.EQ.1) .AND. (IPRN.EQ.0)) GO TO 67
      IF (IPH .EQ. 1) GO TO 62
      WRITE(8,61) INS(1),IEW(1)
   61 FORMAT(/,59X,'  ADJUSTMENTS (KM)  PARTIAL F-VALUES  STANDARD '
     +,'ERRORS  ADJUSTMENTS TAKEN',/
     +,'  I  ORIG  LAT ',A1
     2,'    LONG ',A1,'   DEPTH  DM  RMS AVRPS SKD   CF   '
     3,'DLAT  DLON    DZ  DLAT  DLON    DZ  DLAT  DLON    DZ  '
     4,'DLAT  DLON    DZ')
      IF (IPRN .EQ. 1) IPH=1
   62 WRITE(8,63) NI,SEC,LAT1,LAT2,LON1,LON2,Z,RMK2,IDMIN,RMS,AVRPS,
     1 QS,KF,QD,FLIM,B(2),B(1),B(3),AF(2),AF(1),AF(3),SE(2),SE(1),
     2 SE(3),Y(2),Y(1),Y(3)
   63 FORMAT(I3,F6.2,I3,'-',F5.2,I4,'-',F5.2,F6.2,A1,I3,F5.2,F6.2,
     1 1X,A1,I1,A1,13F6.2)
      IF (KP .EQ. 0) GO TO 100
   67 JNST=KNST*10+INST
      IF (NM .EQ. 0) AVXM=0.
      IF (NF .EQ. 0) AVFM=0.
      MAGOUT = '      '
      IF (MAG .NE. 99.9) WRITE(MAGOUT,68) MAG
   68 FORMAT(F6.2)
      SE3OUT = '     '
      IF (SE(3) .NE. 0.) WRITE(SE3OUT,70) SE(3)
   70 FORMAT(F5.1)
      ERHOUT = '     '
      IF (ERH .NE. 0.) WRITE(ERHOUT,70) ERH
      WRITE(8,75) INS(1),IEW(1)
   75 FORMAT(//,'  DATE    ORIGIN    LAT ',A1,'    LONG ',A1,'    DEPTH'
     1,'    MAG NO DM GAP M  RMS  ERH  ERZ Q SQD  ADJ IN NR  AVR  AAR'
     2,' NM AVXM SDXM NF AVFM SDFM I')
      WRITE(8,86) KDATE,RMKO,KHR,KMIN,SEC,LAT1,LAT2,LON1,LON2
     1,Z,RMK2,MAGOUT,NO,IDMIN,IGAP,KNO,RMS,ERHOUT,SE3OUT,Q,QS
     2,QD,ADJ,JNST,NR,AVR,AAR,NM,AVXM,SDXM,NF,AVFM,SDFM,NI
   86 FORMAT(1X,I6,A1,2I2,F6.2,I3,'-',F5.2,I4,'-',F5.2,1X,F6.2,A1,A6
     1,2I3,I4,I2,F5.2,2A5,2(1X,A1),'|',A1,F5.2,2I3,2F5.2,2(I3,2F5.1),I2)
      IF ((QRMK(1).NE.SYMBOL(4)).AND.(QRMK(1).NE.SYMBOL(5)))
     1QRMK(1)=SYMBOL(1)
      SYM3=SYMBOL(KNO+1)
c      IF (IPUN .EQ. 0) GO TO 100
c      WRITE(7,87) KDATE,KHR,KMIN,SEC,LAT1,LAT2,iabs(LON1),abs(LON2)
c     1,Z,RMK2,MAGOUT,NO,IGAP,DMIN,RMS,ERHOUT,SE3OUT,QRMK(1)
c     2,Q,SYM3
   87 FORMAT(I6,1X,2I2,F6.2,I3,'-',F5.2,I4,'-',F5.2,1X,F6.2,A1,A6,I3
     1,I4,F5.1,F5.2,2A5,3A1)
  100 CONTINUE
      WRITE(SUCARD,87) KDATE,KHR,KMIN,SEC,LAT1,LAT2,LON1,LON2
     1,Z,RMK2,MAGOUT,NO,IGAP,DMIN,RMS,ERHOUT,SE3OUT,QRMK(1),Q,SYM3
      IF (KP .EQ. 1) GO TO 105
      IF(IPRN .LE. 1) GO TO 300
  105 WRITE(8,110)
  110 FORMAT(/,'  STN  DIST AZM AIN PRMK HRMN P-SEC TPOBS TPCAL DLY/H1'
     1,' P-RES P-WT AMX PRX CALX K XMAG RMK FMP FMAG SRMK S-SEC TSOBS'
     2,' S-RES  S-WT    DT')
c-------------------
      DO 200 I=1,NS
      KJI=I
      IF (KSORT .EQ. 1) KJI=KEY(I)
c      KJI=KDX(K)
      K=0
      DO 116 L=1,NR
      IF (KDX(L) .NE. KJI) GO TO 116
      K=L
      GO TO 117
  116 CONTINUE
  117 KK=0
      DO 118 L=NRP+1,NR
      IF (KDX(L) .NE. KJI) GO TO 118
      KK=L
      GO TO 119
  118 CONTINUE
  119 TPK=0.
      X4KOUT='      '
      RMK3=' '
      RMK4=' '
      XMAGOU='    '
      FMAGOU='    '
      IF (K .EQ. 0 .OR. K .GT. NRP) GO TO 161
      TPK=TP(K)-ORG
      IF (TPK .LT. 0.) TPK=TPK+3600.
      WRITE(X4KOUT,112) X(4,K)
  112 FORMAT(F6.2)
      IF ((AZRES(K).NE.' .  ').AND.(AZRES(K).NE.'    ').AND.
     1(AZRES(K).NE.'0.  ')) GO TO 114
c      X4KOUT = '      '
  114 RMK3=' '
      IF (XMAG(K) .EQ. 99.9) GO TO 115
      IF (ABS(XMAG(K)-AVXM) .GE. 0.5) RMK3='*'
  115 RMK4=' '
      IF (FMAG(K) .EQ. 99.9) GO TO 130
      IF (ABS(FMAG(K)-AVFM) .GE. 0.5) RMK4='*'
  130 XMAGOU = '    '
      IF (XMAG(K) .NE. 99.9) WRITE(XMAGOU,160) XMAG(K)
  160 FORMAT(F4.1)
c      FMAGOU = '    '
      IF (FMAG(K) .NE. 99.9) WRITE(FMAGOU,160) FMAG(K)
  161 IAZ=AZ(K)+0.5
      IAIN=AIN(K)+0.5
      IAMX=AMX(K)
      IPRX=100.*PRX(K)+0.5
      FMPOUT = '    '
      IFMPK = FMP(K)
      IF (FMP(K) .NE. 0.) WRITE(FMPOUT,1111) IFMPK
 1111 FORMAT(I4)
c      IF (LDX(K) .NE. 0) GO TO 163
      IF (KK .NE. 0) GO TO 163
C-----CHECK FOR SMP DATA
      IF (KSMP(K) .EQ. 0) GO TO 165
      WRITE(SRESOU,112) X(4,K)
      RMK5 = '    '
      SWTOUT = '****'
      TSK = S(K) - P(K)
      WRITE(TSKOUT,112) TSK
      GO TO 168
c  163 KK=LDX(K)
  163 CONTINUE
      RMK5=WRK(KK)
      SWT=WT(KK)
c      TSK=TS(KK-NRP)-ORG
      TSK=TP(KK)-ORG
      WRITE(SRESOU,112) X(4,KK)
      WRITE(SWTOUT,160) SWT
      WRITE(TSKOUT,112) TSK
      GO TO 168
  165 SKOUT = '      '
      TSKOUT = '      '
      SRESOU = '      '
      RMK5 = '    '
      SWTOUT = '    '
  168 DLYK=DLY(KNO,KJI)
      IF (ISW .EQ. '1   ') DLYK=FLT(KNO,KJI)
      DTKOUT = '      '
      IF (DT(K) .NE. 0.) WRITE(DTKOUT,112) DT(K)
      IF (S(K) .NE. 999.99) WRITE(SKOUT,68) S(KK-NRP)
      PKOUT=0.
      TKOUT=0.
      IF (K .EQ. 0 .OR. K .GT. NRP) GO TO 178
      PKOUT=P(K)
      TKOUT=T(K)
  178 WRITE(8,176,ERR=179) NSTA(KJI),DELTA(K),IAZ,IAIN,PRMK(K),JHR
     1,JMIN(K),PKOUT,TPK,TKOUT,DLYK,X4KOUT,WRK(K),WT(K),IAMX,IPRX
     2,CALX(K),KLAS(KJI),XMAGOU,RMK3,RMK(K),FMPOUT,FMAGOU,RMK4
     3,SRMK(KK-NRP),SKOUT,TSKOUT,SRESOU,RMK5,SWTOUT,DTKOUT,IW(KJI)
  176 FORMAT(1X,A4,F6.1,2I4,1X,A4,1X,2I2,4F6.2,A6,A2,F4.2,I4,I3,F6.2,I2
     1,A4,A1,1X,A3,A4,A4,A1,1X,A4,3A6,A2,A4,A6,T6,A1)
  179 IF (IPUN .NE. 2) GO TO 200
      ISEC = 100.*SEC
      IF (K .EQ. 0) GO TO 200
      WRITE(7,177) NSTA(KJI),DELTA(K),AZ(K),AIN(K),PRMK(K),TPK,X4KOUT
     1,WT(K),XMAGOU,RMK(K),FMAGOU,KDATE,KHR,KMIN,ISEC,KJI,SYM3
  177 FORMAT(A4,3F6.1,1X,A4,F6.2,A6,F5.1,A6,1X,A3,A6,I7,2I2,2I4,A1)
  200 CONTINUE
      IF (IPUN .NE. 2) GO TO 300
      WRITE(7,205)
  205 FORMAT(' $$$')
  300 KHR = JHR
      ORG = OSAVE
      CLOSE(7)
      CLOSE(8)
      RETURN
      END
      SUBROUTINE NO_OUT(TEST,INST,KNST,KNO,IW,INS,IEW,DLY,FMGC,XMGC,
     &  KLAS,PRR,CALR,ICAL,FLT,QSPA,NSTA,KDATE,KHR,NR,NRP,
     &  PRMK,JMIN,P,S,SRMK,AMX,PRX,CALX,RMK,DT,FMP,AZRES,QRMK,KDX,LDX,
     &  WT,TP,T,WRK,KSMP,TS,TIME1,TIME2,DELTA,DX,DY,AVXM,
     &  XMAG,AVFM,FMAG,MAG,FNO,X,B,Y,SE,AF,AZ,AIN,ANIN,TEMP,KEY,
     &  LATEP,LONEP,Z,ORG,NI)
      include 'H_param.f'
C------- OUTPUT HYPOCENTER ---------------------------------------------
      CHARACTER*1 RMKO,RMK2,RMK3,RMK4,Q,QS,QD,SYM3
      CHARACTER*1 CLASS(4),SYMBOL(5),QRMK(NRMAX),IW(NSMAX)
      CHARACTER*1 INS(NSMAX),IEW(NSMAX)
      CHARACTER*3 RMK(NRMAX)
      CHARACTER*4 ISW,XMAGOU,FMAGOU,SWTOUT,FMPOUT,RMK5,IPRO
      CHARACTER*4 NSTA(NSMAX),PRMK(NRMAX),WRK(NRMAX),AZRES(NRMAX)
      CHARACTER*4 SRMK(NRMAX)
      CHARACTER*5 ERHOUT,SE3OUT
      CHARACTER*6 MAGOUT,SKOUT,TSKOUT,SRESOU,DTKOUT,X4KOUT,TSKCAL
c      character*6 stmp
c      CHARACTER*13 Coord_Cartes
      CHARACTER*48 AHEAD
      CHARACTER*80 SUCARD
      CHARACTER*14 FPRINT
      INTEGER*4 JMIN(NRMAX),KDX(NRMAX),LDX(NRMAX),KEY(NRMAX)
      INTEGER*4 NI,KSMP(NSMAX),ICAL(NSMAX),KLAS(NSMAX)
      REAL*4 LAT2,LON2,LATEP,LONEP,MAG,LATR,LONR
      REAL*4 AF(3),B(4),Y(4),SE(4),TEST(20),X(4,NRMAX),QSPA(9,40)
      REAL*4 FLT(2,NSMAX),DLY(2,NSMAX)
      REAL*4 AMX(NRMAX),PRX(NRMAX),CALX(NRMAX),CAL(NRMAX),XMAG(NRMAX)
      REAL*4 FMP(NRMAX),FMAG(NRMAX),TEMP(NRMAX),DEMP(NRMAX)
      REAL*4 DELTA(NRMAX),DX(NRMAX),DY(NRMAX),ANIN(NRMAX),AIN(NRMAX)
      REAL*4 AZ(NRMAX),WT(NRMAX),T(NRMAX),P(NRMAX),TP(NRMAX),DT(NRMAX)
      REAL*4 S(NRMAX),TS(NRMAX),FMGC(NSMAX),XMGC(NSMAX),PRR(NSMAX)
      REAL*4 CALR(NSMAX)
      REAL*8 TIME1,TIME2
c      real*8 xut8,yut8
      COMMON/C1/ IQ,KMS,KFM,IPUN,IMAG,IR,KPAPER,KSORT,KSEL
      COMMON/C2/ LATR,LONR,ONF,FLIM
      COMMON/C3/ AHEAD,IPRO
      COMMON/C4/ NEAR,IEXIT,IDXS
c      COMMON/C5/ PMIN,XFN
      COMMON/O1/ IPH,JPH,NDEC,JMAX,JAV,KF,KP,KZ,KKF
      COMMON/O2/ AVRPS,DMIN,RMSSQ,ADJSQ,ZSQ,AVR,AAR
      COMMON/O3/ SUCARD
      COMMON/O5/ QS,QD
c      common/stdio/lui,luo,lua1,lua2
      DATA CLASS/'A','B','C','D'/
      DATA SYMBOL/' ','1','2','Q','*'/
      RETURN
      END
