      SUBROUTINE SWMREG(TEST,IPRN,NR,KSMP,FNO,X,W,ISKP,KF,KZ,XMEAN,
     &  B,Y,BSE,AF,ONF,FLIM)
C------- COMPUTE GEIGER ADJUSTMENTS BY STEP-WISE MULTIPLE REGRESSION OF
C        TRAVEL TIME RESIDUALS -----------------------------------------
      include 'H_param.f'
      INTEGER*4 ISKP(4),IDX(4),KSMP(NSMAX)
      REAL*4 AF(3),V(3),PF(3),TEST(15),A(7,7),T(7,7)
      REAL*4 B(4),Y(4),BSE(4),XMEAN(4),XSUM(4),SIGMA(4),S(4,4)
      REAL*4 W(NRMAX),X(4,NRMAX)
      DATA L,M,MM,M1/3,4,7,5/
Cf2py intent(out) FLIM
C-----------------------------------------------------------------------
      KFLAG=0
      SVTEST = TEST(3)
      ONF=0.0
      FLIM = TEST(3)
      DO 2 I=1,3
      AF(I)=-1.00
    2 CONTINUE
      DO 5 I=1,NR
      ONF=ONF + W(I)*(1-KSMP(I))
    5 CONTINUE
      DO 10 I=1,MM
      DO 10 J=1,MM
   10 A(I,J)=0.
C-----COMPUTE MEANS,STANDARD DEVIATIONS,AND CORRECTED SUMS OF SQUARE
      DO 40 I=1,M
      XSUM(I)=0.
      XMEAN(I)=0.
      DO 40 J=1,M
   40 S(I,J)=0.
      DO 50 K=1,NR
      DO 50 I=1,M
      TEMP=X(I,K)*W(K)
      ETMP=TEMP*(1-KSMP(K))
      XSUM(I)=XSUM(I)+ETMP
      DO 50 J=I,M
   50 S(I,J)=S(I,J)+TEMP*X(J,K)
      DO 70 I=1,M
      IF (ONF .EQ. 0.) GO TO 65
      XMEAN(I)=XSUM(I)/ONF
      DO 60 J=I,M
   60 S(I,J)=S(I,J)-XSUM(I)*XSUM(J)/ONF
   65 A(I,I)=1.
      IF (S(I,I) .LT. 0.000001) S(I,I)=0.000001
      SIGMA(I)=SQRT(S(I,I))
   70 CONTINUE
C-----COMPUTE AND AUGMENT CORRELATION MATRIX A
      DO 80 I=1,L
      I1=I+1
      DO 80 J=I1,M
      A(I,J)=S(I,J)/(SIGMA(I)*SIGMA(J))
   80 A(J,I)=A(I,J)
      PHI=FNO-1.
      DO 120 I=M1,MM
      A(I-M,I)=1.
  120 A(I,I-M)=-1.
      DO 140 I=1,M
      B(I)=0.
      Y(I)=0.
      BSE(I)=0.
  140 IDX(I)=0
      IF (IPRN .LT. 3) GO TO 150
      WRITE(8,45)
   45 FORMAT(///, '***** DATA *****',//,4X,'K',8X,'W'
     1,14X,'X1',14X,'X2',14X,'X3',14X,'X4',/)
      DO 47 K=1,NR
      WRITE(8,46) K,W(K),(X(I,K),I=1,M)
   46 FORMAT(I5,8E16.8)
   47 CONTINUE
      WRITE(8,75) (XMEAN(I),I=1,M)
   75 FORMAT(/,' MEAN',16X,8E16.8)
      WRITE(8,76) (SIGMA(I),I=1,M)
   76 FORMAT(/,' SIGMA',15X,7E16.8)
      WRITE(8,77)
   77 FORMAT(///,' ***** CORRECTED SUMS OF SQUARES MATRIX *****',/)
      DO 78 I=1,M
   78 WRITE(8,95) (S(I,J),J=1,M)
      WRITE(8,85)
   85 FORMAT(///,' ***** CORRELATION MATRIX R *****',/)
      DO 90 I=1,M
   90 WRITE(8,95) (A(I,J),J=1,M)
   95 FORMAT(7E18.8)
C-----STEPWISE MULTIPLE REGRESSION
      WRITE(8,125) NR,L,TEST(3)
  125 FORMAT(///, '********** STEPWISE MULTIPLE REGRESSION ANALYSIS'
     1,' **********',//' NUMBER OF DATA....................',I5
     2,              /,' NUMBER OF INDEPENDENT VARIABLES...',I5
     3,              /,' CRITICAL F-VALUE..................',F8.2)
  150 DO 300 NSTEP=1,L
      NU=0
      MU=0
      IF (IPRN .LT. 3) GO TO 155
      WRITE(8,154) NSTEP,KZ,KF
  154 FORMAT(//,' ***** STEP NO.',I2,' *****',5X,'KZ =',I2,5X,'KF =',I2)
C-----FIND VARIABLE TO ENTER REGRESSION
  155 VMAX=0.
      MAX=NSTEP
      DO 160 I=1,L
      IF(ISKP(I).EQ.1) GO TO 160
      IF (IDX(I) .EQ. 1) GO TO 160
      IF ((I.EQ.3).AND.(KZ.EQ.1)) GO TO 160
      V(I)=A(I,M)*A(M,I)/A(I,I)
      IF (V(I) .LE. VMAX) GO TO 160
      VMAX=V(I)
      MAX=I
  160 CONTINUE
      F=0.0
      IF(VMAX.EQ.0.0) GO TO 163
      IF(VMAX.EQ.A(M,M)) THEN
         F=1000.
      ELSE
         F=(PHI-1.)*VMAX/(A(M,M)-VMAX)
      END IF
      IF(F .GE. 1000.) F=999.99
  163 AF(MAX)=F
      IF(KF .GE. 2) GO TO 165
      IF (F .LT. TEST(3)) GO TO 400
  165 IF ((MAX.EQ.3).AND.(KZ.EQ.1)) GO TO 300
      NU=MAX
      IDX(NU)=1
      PHI=PHI-1.
C-----COMPUTE MATRIX T FOR THE ENTRANCE OF VARIABLE X(NU)
      DO 170 J=1,MM
  170 T(NU,J)=A(NU,J)/A(NU,NU)
      DO 180 I=1,MM
      IF (I .EQ. NU) GO TO 180
      DO 175 J=1,MM
  175 T(I,J)=A(I,J)-A(I,NU)*A(NU,J)/A(NU,NU)
  180 CONTINUE
      DO 190 I=1,MM
      DO 190 J=1,MM
  190 A(I,J)=T(I,J)
      DO 200 I=1,L
      IF (IDX(I) .EQ. 0) GO TO 200
      IF (ABS(A(M,M)*A(I+M,I+M)) .LT. .000001 ) GO TO 195
      PF(I)=PHI*A(I,M)**2/(A(M,M)*A(I+M,I+M))
      IF(PF(I) .GE. 1000.0) PF(I)=999.99
      AF(I) = PF(I)
      GO TO 200
  195 PF(I) = 999.99
  200 CONTINUE
      IF (IPRN .LT. 3) GO TO 210
      CALL ANSWER(A,S,XMEAN,SIGMA,IDX,PHI,L,M,MM,PF,NU,'ENTERING')
  210 IF (KF .EQ. 2) GO TO 300
      IF(KF .GE. 3) GO TO 450
C-----FIND VARIABLE TO LEAVE REGRESSION
      DO 250 K=1,L
      IF (IDX(K) .EQ. 0) GO TO 250
      IF (PF(K) .GE. TEST(3)) GO TO 250
      MU=K
      F=PF(MU)
      IDX(MU)=0
      PHI=PHI+1.
      DO 220 J=1,MM
  220 T(MU,J)=A(MU,J)/A(MU+M,MU+M)
      DO 230 I=1,MM
      IF (I .EQ. MU) GO TO 230
      DO 225 J=1,MM
      IF (J .EQ. MU) GO TO 225
      T(I,J)=A(I,J)-A(I,MU+M)*A(MU+M,J)/A(MU+M,MU+M)
  225 CONTINUE
  230 CONTINUE
      DO 240 I=1,MM
      IF (I .EQ. MU) GO TO 240
      T(I,MU)=A(I,MU)-A(I,MU+M)/A(MU+M,MU+M)
  240 CONTINUE
      DO 245 I=1,MM
      DO 245 J=1,MM
  245 A(I,J)=T(I,J)
      IF (IPRN .LT. 3) GO TO 250
      CALL ANSWER(A,S,XMEAN,SIGMA,IDX,PHI,L,M,MM,PF,MU,'LEAVING')
  250 CONTINUE
  300 CONTINUE
C-----CHECK TERMINATION CONDITION
  400 KOUT=0
      DO 410 I=1,L
  410 KOUT=KOUT+IDX(I)
      B(4)=XMEAN(M)
      IF (KOUT .NE. 0) GO TO 450
      IF(KF .NE. 1) GO TO 420
      KF = 3
      GO TO 150
  420 TEST(3)= TEST(3)/TEST(6)
      FLIM=TEST(3)
      KF=1
      KFLAG = 0
      IF(TEST(6) .GT. 1.) GO TO 150
      KFLAG = 1
      KF = 4
      GO TO 150
C-----COMPUTE REGRESSION CONSTANT,COEFFICIENTS,AND STANDARD ERRORS
  450 YSE=77.7
      IF (PHI .GE. 1) YSE=SIGMA(M)*SQRT(ABS(A(M,M)/PHI))
      DO 500 I=1,L
      IF (IDX(I) .EQ. 0) GO TO 500
      B(I)=A(I,M)*SQRT(S(M,M)/S(I,I))
      BSE(I)=YSE*SQRT(ABS(A(I+M,I+M)/S(I,I)))
      IF(KF .NE. 3) Y(I)=B(I)
      IF(KFLAG .EQ. 0) GO TO 480
      IF(ABS(B(I)) .LE. TEST(6)*BSE(I)) Y(I)=0.
  480 IF(PHI .LT. 1.) BSE(I) = 0.
      B(4)=B(4)-Y(I)*XMEAN(I)
  500 CONTINUE
      IF(KF .NE. 3) Y(4)=B(4)
      TEST(3)=SVTEST
      RETURN
      END
C
C
      SUBROUTINE ANSWER(A,S,XMEAN,SIGMA,IDX,PHI,L,M,MM,PF,NDX,ADX)
C------- PRINT INTERMEDIATE RESULTS OF REGRESSION ANALYSIS (SWMREG) ---
      CHARACTER*8 ADX
      INTEGER*4 IDX(4)
      REAL*4 A(7,7),S(4,4),XMEAN(4),SIGMA(4),B(4),BSE(4),PF(3)
C-----------------------------------------------------------------------
      DO 410 I=1,MM
      WRITE(8,400) (A(I,J),J=1,MM)
  400 FORMAT(7E18.8)
  410 CONTINUE
      FVE=1.-A(M,M)
      B0=XMEAN(M)
      YSE=77.7
      IF (PHI .GE. 1) YSE=SIGMA(M)*SQRT(ABS(A(M,M)/PHI))
      DO  5 I=1,L
      IF (IDX(I).EQ.0) GO TO  5
      B(I)=A(I,M)* SQRT(ABS(S(M,M)/S(I,I)))
      BSE(I)=YSE* SQRT(ABS(A(I+M,I+M)/S(I,I)))
      B0=B0-B(I)*XMEAN(I)
    5 CONTINUE
      WRITE(8,10) ADX,NDX,FVE,YSE,B0
   10 FORMAT(/,' VARIABLE ', A8, '................',I5
     2,      /,' FRACTION OF VARIATION EXPLAINED..',E18.8
     3,      /,' STANDARD ERROR OF Y..............',E18.8
     4,      /,' CONSTANT IN REGRESSION EQUATION..',E18.8)
      WRITE(8,20)
   20 FORMAT(/,' VARIABLE     COEFFICIENT      STANDARD ERROR'
     1,'     PARTIAL F-VALUE')
      DO 40 I=1,L
      IF (IDX(I).EQ.0) GO TO 40
      WRITE(8,30) I,B(I),BSE(I),PF(I)
   30 FORMAT(I5,3E20.6)
   40 CONTINUE
      RETURN
      END