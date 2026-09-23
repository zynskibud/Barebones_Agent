"""Run the evals: grid to configurations to suites.

Read config/grid.yaml and compute every combination with itertools.product.
Skip configurations that already have results in runs/.
--stage 1 runs the baseline only. --stage 2 changes one axis at a time from the baseline. No --stage runs all.
"""
