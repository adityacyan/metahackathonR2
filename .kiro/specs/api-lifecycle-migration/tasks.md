# Implementation Plan: API Lifecycle Migration Environment

## Overview

This implementation plan creates a new Migration Environment that extends the existing API Conformance Gym to train agents on API evolution scenarios. The environment manages backward compatibility through contract preservation, breaking change detection, and progressive ticket-based evolution while integrating with existing validation and reward systems.

## Tasks

- [x] 1. Create core data models for migration environment
  - [x] 1.1 Implement MigrationAction and MigrationObservation models
    - Create MigrationAction extending APIAction with schema_json and migration_notes
    - Create MigrationObservation extending APIObservation with migration-specific fields
    - Add baseline_schema_json, active_ticket, contract_test_report, breaking_change_report fields
    - _Requirements: 9.1, 9.2_

  - [x] 1.2 Implement contract suite data models
    - Create ContractExpectation model with path, method, required_response_fields
    - Create ContractSuite model with required_operations, required_security, required_response_fields
    - Add baseline_schema_hash for validation
    - _Requirements: 1.1, 1.4_

  - [x] 1.3 Implement breaking change data models
    - Create BreakingChange model with change_type, path, description, severity
    - Create BreakingChangeReport model with breaking_change_count, breaking_changes, breaking_penalty
    - _Requirements: 2.1, 2.2, 2.4_

  - [x] 1.4 Implement ticket system data models
    - Create MigrationTicket model with ticket_id, ticket_type, title, description, acceptance_criteria
    - Add difficulty field and support for different ticket types (additive, deprecation, security, compliance)
    - _Requirements: 3.1, 3.4_

  - [ ]* 1.5 Write property tests for data model validation
    - **Property 1: Contract Suite Generation Bounds**
    - **Validates: Requirements 1.1**

- [x] 2. Implement contract suite generation and testing
  - [x] 2.1 Create ContractSuiteGrader class
    - Implement generate_contract_suite() method to extract 3-8 required operations from baseline schema
    - Extract required response fields from GET operation responses
    - Generate security requirements for all operations
    - _Requirements: 1.1, 1.4, 1.5_

  - [x] 2.2 Implement contract testing functionality
    - Create run_contract_tests() method to validate evolved schemas against contract suite
    - Check for missing operations, response field regressions, auth regressions
    - Calculate contract pass rate (0.0 to 1.0) based on satisfied expectations
    - _Requirements: 1.2, 1.3_

  - [ ]* 2.3 Write property tests for contract preservation
    - **Property 2: Contract Preservation Completeness**
    - **Validates: Requirements 1.2, 1.4, 1.5**
    - **Property 3: Contract Pass Rate Range**
    - **Validates: Requirements 1.3**

- [x] 3. Implement breaking change detection system
  - [x] 3.1 Create BreakingChangeDetector class
    - Implement detect_breaking_changes() method to compare consecutive schema versions
    - Identify removed operations, removed fields, changed response structures
    - Classify breaking changes by type and severity (critical, major, minor)
    - _Requirements: 2.1, 2.2, 2.4, 2.5_

  - [x] 3.2 Implement breaking change penalty calculation
    - Calculate penalties based on change severity and count
    - Apply appropriate penalties to reward calculation
    - _Requirements: 2.3_

  - [ ]* 3.3 Write property tests for breaking change detection
    - **Property 4: Breaking Change Detection Accuracy**
    - **Validates: Requirements 2.1, 2.5**
    - **Property 5: Breaking Change Classification Consistency**
    - **Validates: Requirements 2.2, 2.4**
    - **Property 6: Breaking Change Penalty Application**
    - **Validates: Requirements 2.3**

- [x] 4. Checkpoint - Ensure core components work together
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement ticket system and grading
  - [x] 5.1 Create TicketSatisfactionGrader class
    - Implement score_ticket_satisfaction() method to evaluate schema changes against ticket criteria
    - Support different ticket types with specific acceptance criteria
    - Return satisfaction scores in range [0.0, 1.0]
    - _Requirements: 3.2, 3.4_

  - [x] 5.2 Implement ticket progression logic
    - Advance to next ticket when satisfaction score >= 0.8
    - Handle ticket queue management and completion tracking
    - _Requirements: 3.2, 3.5_

  - [ ]* 5.3 Write property tests for ticket system
    - **Property 7: Ticket Progression Threshold**
    - **Validates: Requirements 3.2**

- [x] 6. Create main MigrationEnvironment class
  - [x] 6.1 Implement MigrationEnvironment extending APIEnvironment
    - Override reset() method to initialize baseline schema and contract suite
    - Override step() method to handle migration-specific validation and scoring
    - Maintain baseline schema preservation throughout episode
    - _Requirements: 6.1, 6.4, 9.1, 9.3_

  - [x] 6.2 Implement state management and transitions
    - Track iteration counts, completion status, and episode termination
    - Maintain schema history and validation results
    - Handle graceful termination at max iterations or completion
    - _Requirements: 6.2, 6.3, 6.5_

  - [ ]* 6.3 Write property tests for environment state
    - **Property 12: Baseline Schema Preservation**
    - **Validates: Requirements 6.4**
    - **Property 13: State Transition Consistency**
    - **Validates: Requirements 6.2**

- [x] 7. Implement reward calculation system
  - [x] 7.1 Create MigrationRewardCalculator class
    - Implement multi-component reward calculation with proper weighting
    - Contract preservation: 45%, ticket satisfaction: 25%, schema quality: 20%, progress: 10%
    - Subtract breaking change penalties and behavior penalties
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 7.2 Implement reward clamping and validation
    - Clamp final rewards to range [0.0, 1.0]
    - Handle edge cases and invalid calculations
    - _Requirements: 4.6_

  - [x] 7.3 Write property tests for reward calculation
    - **Property 9: Reward Component Weighting**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
    - **Property 10: Reward Range Clamping**
    - **Validates: Requirements 4.6**
    - **Property 11: Penalty Subtraction Consistency**
    - **Validates: Requirements 4.5**

- [x] 8. Implement observation system and error handling
  - [x] 8.1 Create comprehensive observation generation
    - Include all required components: baseline schema, active ticket, contract results
    - Add breaking change reports, ticket satisfaction scores, validation information
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 8.2 Implement robust error handling
    - Handle invalid JSON schemas with descriptive error observations
    - Manage initialization errors for insufficient baseline schemas
    - Provide graceful fallback behavior for edge cases
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ]* 8.3 Write property tests for observation system
    - **Property 14: Observation Completeness**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**
    - **Property 15: Error Handling Robustness**
    - **Validates: Requirements 10.1, 10.5**
    - **Property 16: Initialization Error Handling**
    - **Validates: Requirements 10.2**

- [x] 9. Integration with existing codebase
  - [x] 9.1 Integrate with ValidationPipeline
    - Reuse existing ValidationPipeline for schema quality scoring
    - Maintain compatibility with existing validation patterns
    - _Requirements: 5.1, 5.2, 5.3, 9.2_

  - [x] 9.2 Integrate with reward and grading systems
    - Extend existing reward calculation patterns for migration-specific metrics
    - Maintain compatibility with existing grading infrastructure
    - _Requirements: 9.3, 9.4_

  - [x] 9.3 Add environment registration and configuration
    - Register MigrationEnvironment with existing environment system
    - Ensure coexistence with existing conformance testing environments
    - _Requirements: 9.4, 9.5_

- [x] 10. Performance optimization and testing
  - [x] 10.1 Implement performance optimizations
    - Ensure schema validation completes within 2 seconds for 50-path schemas
    - Optimize contract testing to execute within 1 second
    - Optimize breaking change detection to complete within 500ms for 100-operation schemas
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 10.2 Add concurrent execution support
    - Support parallel agent training with stable memory consumption
    - Ensure thread safety for concurrent episode execution
    - _Requirements: 8.4, 8.5_

  - [ ]* 10.3 Write integration tests for complete system
    - Test end-to-end migration scenarios with multiple tickets
    - Validate performance requirements under load
    - Test error handling across all components

- [x] 11. Checkpoint - Ensure episode termination works correctly
  - [x] 11.1 Implement episode termination logic
    - Terminate when all tickets completed and contract pass rate >= 0.95
    - Terminate at maximum iterations with appropriate status
    - _Requirements: 3.5, 6.5_

  - [x] 11.2 Write property tests for termination
    - **Property 8: Episode Termination Conditions**
    - **Validates: Requirements 3.5, 6.5**

- [x] 12. Final integration and wiring
  - [x] 12.1 Wire all components together in MigrationEnvironment
    - Connect contract suite generation, breaking change detection, ticket grading
    - Integrate reward calculation with all scoring components
    - Ensure proper data flow between all graders and validators
    - _Requirements: All requirements_

  - [x] 12.2 Add example usage and documentation
    - Create example scripts demonstrating environment usage
    - Document integration points with existing API Conformance Gym
    - _Requirements: 9.1, 9.5_

- [x] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 14. Implement agent prompt contract and step message templates
  - [ ] 14.1 Add system prompt contract for migration behavior
    - Define strict JSON-only output and complete-schema output requirements
    - Enforce v1 stability rules, v2 introduction only for breaking changes, and deprecation handling
    - Enforce security coverage and operation summary/description requirements
    - _Requirements: HANDOFF 3.1, HANDOFF 3.2_

  - [ ] 14.2 Add per-step user message template assembly
    - Include baseline schema JSON, active ticket, contract test report, and validation feedback
    - Ensure deterministic field layout so the agent receives consistent training context
    - _Requirements: HANDOFF 3.3_

  - [ ] 14.3 Add tests for prompt and message contract integrity
    - Validate required sections are always present and non-empty
    - Validate template output remains machine-parseable and deterministic
    - _Requirements: HANDOFF 3_

- [ ] 15. Implement explicit anti-gaming penalties and breaking penalty formula
  - [ ] 15.1 Implement exact breaking penalty formula
    - Use breaking_penalty = min(0.5, 0.05 * breaking_change_count)
    - Add extra penalty when breaking changes touch contract-critical operations
    - _Requirements: HANDOFF 4, HANDOFF 5_

  - [ ] 15.2 Implement behavior penalty rules
    - Apply repeated schema penalty (+0.10)
    - Apply no-progress penalty after step 2 when progress delta < 0.01 (+0.05)
    - Apply mass-deletion heuristic penalty for large operation-count drops (+0.10 or higher)
    - _Requirements: HANDOFF 5, HANDOFF Anti-gaming_

  - [ ] 15.3 Add property tests for anti-gaming and penalty application
    - Validate penalties are consistently subtracted from base reward
    - Validate endpoint deletion behavior produces immediate compatibility impact
    - _Requirements: HANDOFF 2, HANDOFF 5_

- [ ] 16. Add training resumability workflow and judge deliverables
  - [ ] 16.1 Implement resumable checkpoint workflow
    - Persist model checkpoints including adapter weights, tokenizer assets, and trainer state
    - Persist rollout datasets incrementally to iteration JSONL files
    - Persist progress state with iteration, episode index, env seed, and last checkpoint path
    - _Requirements: HANDOFF 7_

  - [ ] 16.2 Implement restart procedures for local and hub-based training
    - Resume training from latest checkpoint path
    - Resume rollout collection from persisted progress state
    - Support hub checkpoint strategy for intermediate checkpoint sync
    - _Requirements: HANDOFF 7_

  - [ ] 16.3 Add judge-ready deliverables tasks
    - Add HF Space run target for environment execution
    - Add README deliverables: problem, mechanics, reward, before-after example, and plots
    - Add metrics artifact showing continued training after interruption
    - _Requirements: HANDOFF 8, HANDOFF Minimum proof for judges_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties from the design document
- Integration tasks ensure seamless compatibility with existing API Conformance Gym
- Performance tasks ensure the environment meets scalability requirements
- The implementation builds incrementally from data models to complete environment