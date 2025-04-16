@ Azumanga Daioh Break song (first half), voice-adapted to sound reasonably well in River City Ransom EX.
@ Alternative Catnip Dreams voice numbers are also listed.

	.include "MPlayDef.s"

	.equ	azumanga_grp, voicegroup000
	.equ	azumanga_pri, 0
	.equ	azumanga_rev, 0
	.equ	azumanga_mvl, 100
	.equ	azumanga_key, 0
	.equ	azumanga_tbs, 1
	.equ	azumanga_exg, 0
	.equ	azumanga_cmp, 1

	.section .rodata
	.global	azumanga
	.align	2

@**************** Track 1 (Midi-Chn.1) ****************@

azumanga_1:
	.byte		VOL   , 127*azumanga_mvl/mxv
	.byte	KEYSH , azumanga_key+0
azumanga_1_B1:
@ 000   ----------------------------------------
	.byte	TEMPO , 120*azumanga_tbs/2
	.byte	W02
	.byte		VOICE , 12 @ 61 - Brass Section
	.byte	W01
	.byte	W01
@ 001   ----------------------------------------
	.byte	TEMPO , 125*azumanga_tbs/2
	.byte		N10   , Gn3 , v112
	.byte	W18
	.byte		N03   
	.byte	W06
@ 002   ----------------------------------------
	.byte		N12   , Cn4 
	.byte	W24
@ 003   ----------------------------------------
	.byte		N10   , Dn4 
	.byte	W18
	.byte		N03   , En4 
	.byte	W06
@ 004   ----------------------------------------
	.byte		N12   , Cn4 
	.byte	W24
@ 005   ----------------------------------------
	.byte		N10   , An3 
	.byte	W18
	.byte		N03   , Gn3 
	.byte	W06
@ 006   ----------------------------------------
	.byte		N12   , Cn4 
	.byte	W24
@ 007   ----------------------------------------
	.byte		N12   
	.byte	W24
@ 008   ----------------------------------------
	.byte		N12   
	.byte	W24
@ 009   ----------------------------------------
	.byte	W24
@ 010   ----------------------------------------
	.byte	FINE

@**************** Track 2 (Midi-Chn.2) ****************@

azumanga_2:
	.byte		VOL   , 127*azumanga_mvl/mxv
	.byte	KEYSH , azumanga_key+0
azumanga_2_B1:
@ 000   ----------------------------------------
	.byte	W02
	.byte		VOICE , 0 @ 72 - Piccolo
	.byte	W01
	.byte	W01
@ 001   ----------------------------------------
	.byte		N10   , Gn3 , v100
	.byte	W18
	.byte		N03   
	.byte	W06
@ 002   ----------------------------------------
	.byte		N12   , Cn4 
	.byte	W24
@ 003   ----------------------------------------
	.byte		N10   , Dn4 
	.byte	W18
	.byte		N03   , En4 
	.byte	W06
@ 004   ----------------------------------------
	.byte		N12   , Cn4 
	.byte	W24
@ 005   ----------------------------------------
	.byte		N10   , An3 
	.byte	W18
	.byte		N03   , Gn3 
	.byte	W06
@ 006   ----------------------------------------
	.byte		N12   , Cn4 
	.byte	W24
@ 007   ----------------------------------------
	.byte		N12   
	.byte	W24
@ 008   ----------------------------------------
	.byte		N12   
	.byte	W24
@ 009   ----------------------------------------
	.byte	W24
@ 010   ----------------------------------------
	.byte	FINE

@**************** Track 3 (Midi-Chn.3) ****************@

azumanga_3:
	.byte		VOL   , 127*azumanga_mvl/mxv
	.byte	KEYSH , azumanga_key+0
azumanga_3_B1:
@ 000   ----------------------------------------
	.byte	W01
	.byte	W01
	.byte		VOICE , 9 @ 61 - Brass Section
	.byte	W01
	.byte	W01
@ 001   ----------------------------------------
	.byte	W23
	.byte		N12   , Cn2 , v112
	.byte	W01
@ 002   ----------------------------------------
	.byte	W23
	.byte		        Bn1 
	.byte	W01
@ 003   ----------------------------------------
	.byte	W23
	.byte		        An1 
	.byte	W01
@ 004   ----------------------------------------
	.byte	W23
	.byte		        Fn1 
	.byte	W01
@ 005   ----------------------------------------
	.byte	W23
	.byte		        Ds1 
	.byte	W01
@ 006   ----------------------------------------
	.byte	W23
	.byte		        Dn1 
	.byte	W01
@ 007   ----------------------------------------
	.byte	W23
	.byte		        Cn1 
	.byte	W01
@ 008   ----------------------------------------
	.byte	W24
@ 009   ----------------------------------------
	.byte	W23
	.byte	FINE

@**************** Track 4 (Midi-Chn.4) ****************@

azumanga_4:
	.byte		VOL   , 127*azumanga_mvl/mxv
	.byte	KEYSH , azumanga_key+0
azumanga_4_B1:
@ 000   ----------------------------------------
	.byte	W01
	.byte		VOICE , 9 @ 61 - Brass Section
	.byte	W01
	.byte		PAN   , c_v+60
	.byte	W01
	.byte	W01
@ 001   ----------------------------------------
	.byte	W23
	.byte		N12   , Cn3 , v112
	.byte	W01
@ 002   ----------------------------------------
	.byte	W23
	.byte		        Bn2 
	.byte	W01
@ 003   ----------------------------------------
	.byte	W23
	.byte		        An2 
	.byte	W01
@ 004   ----------------------------------------
	.byte	W23
	.byte		        Fn2 
	.byte	W01
@ 005   ----------------------------------------
	.byte	W23
	.byte		        Ds2 
	.byte	W01
@ 006   ----------------------------------------
	.byte	W23
	.byte		        Dn2 
	.byte	W01
@ 007   ----------------------------------------
	.byte	W23
	.byte		        Cn2 
	.byte	W01
@ 008   ----------------------------------------
	.byte	W24
@ 009   ----------------------------------------
	.byte	W23
	.byte	FINE

@**************** Track 5 (Midi-Chn.5) ****************@

azumanga_5:
	.byte		VOL   , 127*azumanga_mvl/mxv
	.byte	KEYSH , azumanga_key+0
azumanga_5_B1:
@ 000   ----------------------------------------
	.byte	W02
	.byte		VOICE , 12 @ 47 - Timpani
	.byte	W01
	.byte	W01
@ 001   ----------------------------------------
	.byte		N10   , Gn5 , v092
	.byte	W18
	.byte		N03   
	.byte	W06
@ 002   ----------------------------------------
	.byte		N12   , Cn6 
	.byte	W24
@ 003   ----------------------------------------
	.byte		N10   , Dn6 
	.byte	W18
	.byte		N03   , En6 
	.byte	W06
@ 004   ----------------------------------------
	.byte		N12   , Cn6 
	.byte	W24
@ 005   ----------------------------------------
	.byte		N10   , An5 
	.byte	W18
	.byte		N03   , Gn5 
	.byte	W06
@ 006   ----------------------------------------
	.byte		N12   , Cn6 
	.byte	W24
@ 007   ----------------------------------------
	.byte		N12   
	.byte	W24
@ 008   ----------------------------------------
	.byte		N12   
	.byte	W24
@ 009   ----------------------------------------
	.byte	W24
@ 010   ----------------------------------------
	.byte	FINE

@**************** Track 6 (Midi-Chn.10) ****************@

azumanga_6:
	.byte		VOL   , 127*azumanga_mvl/mxv
	.byte	KEYSH , azumanga_key+0
azumanga_6_B1:
@ 000   ----------------------------------------
	.byte	W03
	.byte		VOICE , 127 @ 127 - Drums
	.byte	W01
@ 001   ----------------------------------------
azumanga_6_001:
	.byte		N01   , Dn1 , v100
	.byte	W18
	.byte		        Dn1 , v092
	.byte	W06
	.byte	PEND
@ 002   ----------------------------------------
	.byte		        Dn1 , v100
	.byte		N01   , Cs2 , v092
	.byte	W24
@ 003   ----------------------------------------
azumanga_6_003:
	.byte		N01   , Dn1 , v100
	.byte	W18
	.byte		        Dn1 , v076
	.byte	W03
	.byte		        Dn1 , v072
	.byte	W03
	.byte	PEND
@ 004   ----------------------------------------
	.byte	PATT
	 .word	azumanga_6_001
@ 005   ----------------------------------------
	.byte	PATT
	 .word	azumanga_6_003
@ 006   ----------------------------------------
	.byte		N01   , Dn1 , v100
	.byte	W24
@ 007   ----------------------------------------
	.byte		N01   
	.byte	W24
@ 008   ----------------------------------------
	.byte		N01   
	.byte	W24
@ 009   ----------------------------------------
	.byte	FINE

@******************************************************@
	.align	2

azumanga:
	.byte	6	@ NumTrks
	.byte	0	@ NumBlks
	.byte	azumanga_pri	@ Priority
	.byte	azumanga_rev	@ Reverb.

	.word	azumanga_grp

	.word	azumanga_1
	.word	azumanga_2
	.word	azumanga_3
	.word	azumanga_4
	.word	azumanga_5
	.word	azumanga_6

	.end
