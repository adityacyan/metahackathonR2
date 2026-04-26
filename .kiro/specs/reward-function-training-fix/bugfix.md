# Bugfix Requirements Document

## Introduction

The training graphs show severe training instability with binary reward oscillation (+1 and -3), high KL divergence (6+), and completion length collapse (dropping to near 0). The root cause is that the `reward_env_step()` function in the training notebook adds a bonus to the environment reward, pushing values outside the documented [0.0, 1.0] range. This causes the GRPO trainer to receive out-of-range rewards that lead to policy collapse and training failure.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the `reward_env_step()` function calculates rewards THEN the system adds `0.5 * ticket_satisfaction_score` as a bonus to the environment reward, producing values up to 1.5

1.2 WHEN rewards exceed the documented [0.0, 1.0] range THEN the GRPO trainer receives out-of-range reward signals that cause binary reward patterns (+1 and -3)

1.3 WHEN the GRPO trainer processes out-of-range rewards THEN training exhibits high KL divergence (6+), completion length collapse (near 0), and binary reward standard deviation oscillation

### Expected Behavior (Correct)

2.1 WHEN the `reward_env_step()` function calculates rewards THEN the system SHALL return the environment reward directly without adding bonuses, keeping values in [0.0, 1.0]

2.2 WHEN rewards are passed to the GRPO trainer THEN the system SHALL ensure all reward values are within the documented [0.0, 1.0] range

2.3 WHEN the GRPO trainer processes rewards THEN training SHALL exhibit stable reward curves, controlled KL divergence, and consistent completion lengths

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the environment's `MigrationRewardCalculator.calculate_reward()` computes rewards THEN the system SHALL CONTINUE TO return values in [0.0, 1.0] using the formula R = 0.45*C + 0.25*T + 0.20*Q + 0.10*P - B - K

3.2 WHEN the `reward_json_valid()` function validates JSON completions THEN the system SHALL CONTINUE TO return 1.0 for valid JSON and -1.0 for invalid JSON

3.3 WHEN the environment step fails due to invalid schema THEN the system SHALL CONTINUE TO return -2.0 as the error penalty in `reward_env_step()`

3.4 WHEN the training notebook collects prompts and runs episodes THEN the system SHALL CONTINUE TO use the same episode generation and evaluation logic
