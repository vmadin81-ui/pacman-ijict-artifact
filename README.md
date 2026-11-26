# Structural evolution and equivalence-preserving optimization of a browser-based application

Research data supplement by Vladimir A. Madin for an IJICT manuscript in preparation. No article DOI has been assigned.

## Contents

| Directory | Files | Description |
|---|---:|---|
| tables | 3 | Full-precision publication tables |
| data/E1 | 3 | Archived CI performance summaries, contrasts and paired measurements |
| data/E2 | 4 | Local graph-search descriptive statistics, contrasts, paired measurements and graph preparation costs |
| data/E3 | 5 | Local rendering statistics, contrasts, paired measurements, cache preparation and visual validation counts |
| data/E4 | 1 | Structural metrics for twelve historical versions |
| data/E2-CI | 4 | Subsequent autonomous CI search measurements |
| data/E3-CI | 5 | Subsequent autonomous CI rendering measurements and visual validation counts |

All 25 CSV files are byte-identical to their archived counterparts. The nine subsequent CI files were extracted from the accepted private rc.3 archive and checked against its SHA-256 manifest. See manifest.json for Git blob identifiers.

## Interpretation and limitations

Local and CI measurements must not be pooled. Ratios of medians differ from medians of paired ratios. Bootstrap intervals are conditional descriptive estimates. Rendering microbenchmarks do not measure displayed application FPS. Structural metrics do not directly measure maintainability. Agreement of tested outputs does not prove full program equivalence.

This is a data-only deposit, not a complete executable artifact. Historical application source, assets, route traces, map geometry, raw logs, mixed-source archives, and administrative records are not included. The deposit permits verification of reported numerical results within the scope of the published data; it does not enable full independent reruns of the original experiments. No independent external replication is claimed.

## License and citation

Author-held research material in this deposit is offered under CC BY 4.0: https://creativecommons.org/licenses/by/4.0/ . No rights in third-party material or trademarks are granted. Cite Vladimir A. Madin, the repository title, https://github.com/vmadin81-ui/pacman-ijict-artifact and the exact commit used. No public license is granted for the excluded application implementations.
