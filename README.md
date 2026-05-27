# Cogito Coverage Decay

This repository contains the code and reproducibility materials for the technical article:

**Coverage decay: when style prompts forget themselves**  
Author: Nic Omolabi  
Technical article / reproducibility protocol, May 2026

## Overview

Large language models often follow style or reasoning instructions at the start of a long response, then gradually drift back toward generic structure. This project calls that failure mode **coverage decay**.

Cogito is a lightweight prompting-layer control loop designed to reduce that drift by:

1. generating an initial response;
2. scoring reasoning-pattern coverage;
3. critiquing the response against the user’s preferred reasoning patterns;
4. refining the response until coverage improves or the iteration limit is reached.

The project is not a finished benchmark. It is a reproducible technical experiment for testing whether reasoning-structure persistence can be improved through iterative preference application.

## Repository contents

```text
scripts/     Core experiment and scoring code
data/        Question sets and example profile files
article/     Technical article draft
results/     Experiment outputs, if published
docs/        Protocol notes and supporting documentation
