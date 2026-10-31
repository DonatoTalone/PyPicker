      SUBROUTINE AZWTOS(DX,DY,NR,WT,KDX,AZ,AZWT,KEY,INS,IEW,GAP)
C------- AZIMUTHAL WEIGHTING OF STATIONS BY QUADRANTS ------------------
	include 'H_param.f'
      CHARACTER*1 INS(NSMAX),IEW(NSMAX)
      INTEGER*4 KTX(4),KEMP(NRMAX),KEY(NRMAX),KDX(NRMAX)
      REAL*4 TX(4),TXN(4),DX(NRMAX),DY(NRMAX),WT(NRMAX),AZ(NRMAX)
      REAL*4 AZWT(NRMAX),TEMP(NRMAX)
      REAL*4 GAP
Cf2py intent(out) GAP
Cf2py intent(inout) AZ,AZWT
C-----------------------------------------------------------------------
      J=0
      DO 10 I=1,NR
      IF (WT(I) .EQ. 0.) GO TO 10
      DXI=DX(I)
      DYI=DY(I)
      IF ((DXI.EQ.0.).AND.(DYI.EQ.0.)) GO TO 6
      JI=KDX(I)
C-- Original hypo71 assumes absolute LON/LAT and DX/DY
C-- but we always use signed coordinates
c      IF (INS(JI) .EQ. 'S') DYI=-DYI
c      IF (IEW(JI) .EQ. 'W') DXI=-DXI
      AZ(I)=AMOD(ATAN2(DXI,DYI)*57.29578 + 360., 360.)
      GO TO 7
    6 AZ(I)=999.
    7 J=J+1
      TEMP(J)=AZ(I)
   10 CONTINUE
      CALL SORT(TEMP,KEY,J)
      GAP=TEMP(1)+360.-TEMP(J)
      IG=1
      DO 20 I=2,J
      DTEMP=TEMP(I)-TEMP(I-1)
      IF (DTEMP .LE. GAP) GO TO 20
      GAP=DTEMP
      IG=I
   20 CONTINUE
      TX(1)=TEMP(IG)-0.5*GAP
      TX(2)=TX(1)+90.
      TX(3)=TX(1)+180.
      TX(4)=TX(1)+270.
      DO 124 I=1,4
      TXN(I)=0.
      IF (TX(I) .LT. 0.) TX(I)=TX(I)+360.
      IF (TX(I).GT.360.) TX(I)=TX(I)-360.
  124 CONTINUE
      CALL SORT(TX,KTX,4)
      DO 130 I=1,NR
      IF (WT(I) .EQ. 0.) GO TO 130
      IF (AZ(I) .GT. TX(1)) GO TO 126
  125 TXN(1)=TXN(1)+1.
      KEMP(I)=1
      GO TO 130
  126 IF (AZ(I) .GT. TX(2)) GO TO 127
      TXN(2)=TXN(2)+1.
      KEMP(I)=2
      GO TO 130
  127 IF (AZ(I) .GT. TX(3)) GO TO 128
      TXN(3)=TXN(3)+1.
      KEMP(I)=3
      GO TO 130
  128 IF (AZ(I) .GT. TX(4)) GO TO 125
      TXN(4)=TXN(4)+1.
      KEMP(I)=4
  130 CONTINUE
      XN=4
      IF (TXN(1).EQ.0.) XN=XN-1
      IF (TXN(2).EQ.0.) XN=XN-1
      IF (TXN(3).EQ.0.) XN=XN-1
      IF (TXN(4).EQ.0.) XN=XN-1
      FJ=J/XN
      DO 150 I=1,NR
      IF (WT(I) .EQ. 0.) GO TO 150
      KI=KEMP(I)
c      WT(I)=WT(I)*FJ/TXN(KI)
      AZWT(I)=FJ/TXN(KI)
  150 CONTINUE
      RETURN
      END
C
C
      SUBROUTINE SORT(X,KEY,NO)
      DIMENSION X(NO),KEY(NO)
C-----------------------------------------------------------------------
      DO 1 I=1,NO
 1    KEY(I)=I
      MO=NO
 2    IF (MO-15) 21,21,23
 21   IF (MO-1) 29,29,22
 22   MO=2*(MO/4)+1
      GO TO 24
 23   MO=2*(MO/8)+1
 24   KO=NO-MO
      JO=1
 25   I=JO
 26   IF (X(I)-X(I+MO)) 28,28,27
 27   TEMP=X(I)
      X(I)=X(I+MO)
      X(I+MO)=TEMP
      KEMP=KEY(I)
      KEY(I)=KEY(I+MO)
      KEY(I+MO)=KEMP
      I=I-MO
      IF (I-1) 28,26,26
 28   JO=JO+1
      IF (JO-KO) 25,25,2
 29   RETURN
      END
