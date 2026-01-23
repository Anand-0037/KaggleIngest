# Implementation Plan: Enhanced N Ranking

## Overview

This implementation plan breaks down the Enhanced Notebook Ranking feature into discrete, incremental tasks. The approach follows a bottom-up strategy: build individual calculator components first, then compose them into the main ranker, and finally integrate with the existing NotebookService.

## Tasks

- [ ] 1. Create core data structures and configuration
  - Create `RankingConfig` dataclass with default values
  - Create `RankingMetadata` dataclass for score breakdown
  - Create `RankedNotebook` dataclass for output
  - Add configuration loading methods (from_env, from_file)
  - _Requirements: 5.1, 5.2_

- [ ] 1.1 Write property test for configuration validation
  - **Property 12: Configuration Validation**
  - **Validates: Requirements 5.3**

- [ ] 2. Implement BaseScoreCalculator
  - Create `BaseScoreCalculator` class
  - Implement logarithmic scaling: `log10(upvotes + 1) * 10`
  - Handle edge cases (zero upvotes, negative values)
  - _Requirements: 1.1, 6.1_

- [ ] 2.1 Write property test for upvote score monotonicity
  - **Property 1: Upvote Score Monotonicity**
  - **Validates: Requirements 1.1, 6.1**

- [ ] 3. Implement TimeDecayCalculator
  - Create `TimeDecayCalculator` class with config parameters
  - Implement age calculation from ISO timestamp
  - Implement linear decay function for 30-180 day range
  - Apply floor of 0.5 for notebooks older than 180 days
  - Handle missing/invalid timestamps (default to 180 days)
  - _Requirements: 1.2, 2.1, 2.2, 2.3, 2.4_

- [ ] 3.1 Write property test for recent notebooks no decay
  - **Property 3: Recent Notebooks No Decay**
  - **Validates: Requirements 2.1**

- [ ] 3.2 Write property test for linear decay in middle range
  - **Property 4: Linear Decay in Middle Range**
  - **Validates: Requirements 2.2**

- [ ] 3.3 Write property test for old notebooks minimum decay
  - **Property 5: Old Notebooks Minimum Decay**
  - **Validates: Requirements 2.3**

- [ ] 3.4 Write property test for missing timestamp default
  - **Property 18: Missing Timestamp Default**
  - **Validates: Requirements 2.4**

- [ ] 3.5 Write property test for time decay monotonicity
  - **Property 2: Time Decay Monotonicity**
  - **Validates: Requirements 1.2, 6.2**

- [ ] 4. Implement CodeQualityCalculator
  - Create `CodeQualityCalculator` class with config parameters
  - Implement code cell counting from NotebookContent
  - Implement markdown cell counting from NotebookContent
  - Calculate code-to-markdown ratio (handle division by zero)
  - Apply penalty (0.7) for fewer than 5 code cells
  - Apply penalty (0.8) for ratio below 0.3
  - Combine penalties multiplicatively when both apply
  - Return 1.0 when content is missing
  - _Requirements: 1.4, 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 4.1 Write property test for code quality penalty application
  - **Property 6: Code Quality Penalty Application**
  - **Validates: Requirements 3.3, 3.4**

- [ ] 4.2 Write property test for code quality no penalty
  - **Property 7: Code Quality No Penalty**
  - **Validates: Requirements 3.5**

- [ ] 4.3 Write property test for missing content default
  - **Property 20: Missing Content Default**
  - **Validates: Requirements 8.1**

- [ ] 5. Implement ExecutionStatusCalculator
  - Create `ExecutionStatusCalculator` class with config parameters
  - Extract execution status from NotebookMeta (handle various field names)
  - Apply boost (1.2) for "complete" or "success" status
  - Apply penalty (0.6) for "error" or "failed" status
  - Return 1.0 for missing or unknown status
  - _Requirements: 1.3, 4.1, 4.2, 4.3, 4.4_

- [ ] 5.1 Write property test for execution status boost
  - **Property 8: Execution Status Boost**
  - **Validates: Requirements 4.2**

- [ ] 5.2 Write property test for execution status penalty
  - **Property 9: Execution Status Penalty**
  - **Validates: Requirements 4.3**

- [ ] 5.3 Write property test for missing execution status default
  - **Property 19: Missing Execution Status Default**
  - **Validates: Requirements 4.4**

- [ ] 6. Checkpoint - Ensure all calculator tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Implement ScoreCalculator
  - Create `ScoreCalculator` class that orchestrates individual calculators
  - Implement `calculate_score()` method
  - Compute base score using BaseScoreCalculator
  - Apply time decay factor
  - Apply code quality factor
  - Apply execution status factor
  - Multiply all factors to get final score
  - Build RankingMetadata with all component values
  - Return tuple of (final_score, metadata)
  - _Requirements: 1.5, 6.2, 6.3, 6.4_

- [ ] 7.1 Write property test for score composition
  - **Property 10: Score Composition**
  - **Validates: Requirements 1.5, 6.2, 6.3, 6.4**

- [ ] 8. Implement NotebookRanker
  - Create `NotebookRanker` class with config initialization
  - Implement `rank_notebooks()` method
  - Iterate through notebooks and compute scores
  - Match notebooks with content when available
  - Sort notebooks by score in descending order
  - Assign rank positions (1-indexed)
  - Return list of RankedNotebook objects
  - _Requirements: 6.5_

- [ ] 8.1 Write property test for descending sort order
  - **Property 11: Descending Sort Order**
  - **Validates: Requirements 6.5**

- [ ] 8.2 Write property test for graceful missing data handling
  - **Property 17: Graceful Missing Data Handling**
  - **Validates: Requirements 8.1, 8.2, 8.3**

- [ ] 8.3 Write property test for configuration application
  - **Property 13: Configuration Application**
  - **Validates: Requirements 5.5**

- [ ] 9. Extend output formatting for ranking metadata
  - Modify TOON encoder to include ranking scores in notebooks section
  - Add ranking_score, base_score, and factor fields to TOON output
  - Modify JSON formatter to include ranking_details object
  - Ensure all metadata fields are serialized correctly
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [ ] 9.1 Write property test for output completeness
  - **Property 14: Output Completeness**
  - **Validates: Requirements 7.1, 7.2**

- [ ] 9.2 Write property test for TOON format ranking metadata
  - **Property 15: TOON Format Ranking Metadata**
  - **Validates: Requirements 7.3**

- [ ] 9.3 Write property test for JSON format ranking details
  - **Property 16: JSON Format Ranking Details**
  - **Validates: Requirements 7.4**

- [ ] 10. Integrate NotebookRanker into NotebookService
  - Import NotebookRanker in NotebookService
  - Replace `_rank_notebooks()` method to use NotebookRanker
  - Pass processed content to ranker when available
  - Update method to return RankedNotebook objects
  - Maintain backward compatibility with existing callers
  - _Requirements: 8.4_

- [ ] 10.1 Write integration test for NotebookService ranking
  - Test end-to-end ranking through NotebookService
  - Verify backward compatibility with existing code
  - _Requirements: 8.4_

- [ ] 11. Add configuration file support
  - Create default `ranking_config.json` in backend/config/
  - Document configuration parameters in README
  - Add environment variable overrides
  - Test configuration loading in various scenarios
  - _Requirements: 5.1, 5.2_

- [ ] 12. Final checkpoint - End-to-end verification
  - Run full test suite
  - Test with real Kaggle competition data
  - Verify TOON output includes ranking metadata
  - Verify JSON output includes ranking details
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Each task references specific requirements for traceability
- Property tests validate universal correctness properties
- Integration tests validate end-to-end functionality
- The implementation follows a bottom-up approach: calculators → scorer → ranker → integration
