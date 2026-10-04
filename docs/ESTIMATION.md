# Estimation (Exp 3)

Function points from Exp 3: UFP = 117 (7 EI, 4 EO, 4 EQ, 5 ILF, 1 EIF), VAF = 1.05, **adjusted FP = 123**.

The delivered system maps onto those counts: 5 internal files (users, vehicles, test drives, sales/invoices, service records)
and 1 external interface (payment gateway).

Actual delivered size: about 1,090 non-blank lines of Python application code, 590 lines of tests, 440 lines of templates.
Basic COCOMO (organic mode, E = 2.4 x KLOC^1.05) on the Python code gives about 2.6 person-months and 3.6 months schedule.
FP-based estimates run higher than the real code size because Python and Flask are far more compact than the
language-neutral function-point scale assumes.
