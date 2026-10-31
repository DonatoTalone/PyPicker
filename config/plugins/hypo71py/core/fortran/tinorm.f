      FUNCTION TINORM(ALPHA)                                            TINORM
      DIMENSION A(3),B(3)                                               TINORM
      DATA(A(I),I=1,3)/.010328,.802853,2.515517/,(B(I),I=1,3)/.0010308, TINORM
     1.189269,1.432788/                                                 TINORM
C-----------------------------------------------------------------------TINORM
C     APPROXIMATION TO INVERSE NORMAL DISTRIBUTION                      TINORM
C-----------------------------------------------------------------------TINORM
      IF(.NOT.(ALPHA.GT.0..AND.ALPHA.LT.1.)) GO TO 1                    TINORM
      X=ALPHA                                                           TINORM
      IF(X.GT..5) X=1.-X                                                TINORM
      X=SQRT(-2.*ALOG(X))                                               TINORM
      TINORM=X-(A(3)+X*(A(2)+X*A(1)))/(1.+X*(B(3)+X*(B(2)+X* B(1))))    TINORM
c     CALL OVERFL(I)                                                    TINORM
C          CHANGE     R.VERBEIREN   23/02/83
C                                   11/04/90 - microvax 
C     IF(I.EQ.1) RETURN 2                                               TINORM
c     IF(I.EQ.1) RETURN 1
      IF(ALPHA.LT..5) TINORM=-TINORM                                    TINORM
    1 RETURN                                                            TINORM
C   1 RETURN 2                                                          TINORM
c   1 RETURN 1
      END                                                               TINORM
