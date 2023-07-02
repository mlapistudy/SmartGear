# SmartGear

This is the artifact for our OOPSLA'23 paper “Run-Time Prevention of Software Integration Failures of Machine Learning APIs)”. We hope this artifact can motivate and help future research to further tackle ML software defects. This artifact aims for Available Badge.


## What's inside the artifact:

For availability and reusability, we provide source code of our tool SmartGear and the instructions for setting up the working environment. In addition, we provide benchmark suite empirical study and experiment results.

Below are details of what is included in each part:

- Source code of Keeper.  Located in `./source_code`
- A benchmark suite of 55 applications and their empirical study results (Section 3). Located in `./benchmark/emperical_study.xlsx`, containing
  - Software project name
  - GitHub link
  - Used ML API
  - Failures (Figure 4)
- A benchmark suite of 65 applications and their evaluation results (Section 3). Located in `./benchmark/evaluation.xlsx`, containing
  - Software project name
  - GitHub link
  - Used ML API
  - Failure groundtruth
  - SmartGear detection result (Table 4&5)
  - SmartGear recovery result (Table 4&5, Figure 17)
  - Application statistics


## Getting Started Guide
Please refer to `./source_code/readme.md` for install instructions and basic testing.