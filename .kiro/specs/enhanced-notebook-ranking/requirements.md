# Requirements Document

## Introduction

KaggleIngest currently ranks notebooks primarily by upvote count with basic time decay. This feature enhances the ranking algorithm to incorporate multiple quality signals including recency, code quality metrics, execution success, and engagement patterns to surface the most valuable notebooks for LLM context generation.

## Glossary

- **Notebook_Ranker**: The system component responsible for scoring and ordering notebooks
- **Quality_Signal**: A measurable attribute that indicates notebook valus, recency, code quality)
- **Ranking_Score**: A computed numerical value used to order notebooks
- **Time_Decay_Factor**: A multiplier that reduces score based on notebook age
- **Execution_Status**: Whether a notebook ran successfully on Kaggle
- **Code_Quality_Metric**: Measurable indicators of code structure and documentation quality

## Requirements

### Requirement 1: Multi-Signal Ranking

**User Story:** As a developer, I want notebooks ranked by multiple quality signals, so that I receive the most relevant and high-quality implementation patterns for my competition.

#### Acceptance Criteria

1. WHEN ranking notebooks, THE Notebook_Ranker SHALL incorporate upvote count as a primary signal
2. WHEN ranking notebooks, THE Notebook_Ranker SHALL apply time decay based on last update timestamp
3. WHEN ranking notebooks, THE Notebook_Ranker SHALL consider execution status as a quality signal
4. WHEN ranking notebooks, THE Notebook_Ranker SHALL weight code-to-markdown ratio as a quality indicator
5. WHEN computing the final score, THE Notebook_Ranker SHALL combine all signals using configurable weights

### Requirement 2: Time Decay Implementation

**User Story:** As a developer, I want recent notebooks prioritized over outdated ones, so that I get current best practices and techniques.

#### Acceptance Criteria

1. WHEN a notebook is less than 30 days old, THE Notebook_Ranker SHALL apply no time decay penalty
2. WHEN a notebook is between 30 and 180 days old, THE Notebook_Ranker SHALL apply linear decay from 1.0 to 0.5
3. WHEN a notebook is older than 180 days, THE Notebook_Ranker SHALL apply a minimum decay factor of 0.5
4. WHEN last_updated timestamp is missing, THE Notebook_Ranker SHALL treat the notebook as 180 days old

### Requirement 3: Code Quality Scoring

**User Story:** As a developer, I want notebooks with substantial code and documentation ranked higher, so that I get actionable implementation examples rather than discussion-only notebooks.

#### Acceptance Criteria

1. WHEN analyzing a notebook, THE Notebook_Ranker SHALL count total code cells
2. WHEN analyzing a notebook, THE Notebook_Ranker SHALL count total markdown cells
3. WHEN code cells are fewer than 5, THE Notebook_Ranker SHALL apply a penalty factor of 0.7
4. WHEN the code-to-markdown ratio is below 0.3, THE Notebook_Ranker SHALL apply a penalty factor of 0.8
5. WHEN a notebook has both substantial code and documentation, THE Notebook_Ranker SHALL apply no penalty

### Requirement 4: Execution Status Validation

**User Story:** As a developer, I want notebooks that executed successfully prioritized, so that I get working code examples.

#### Acceptance Criteria

1. WHEN notebook metadata includes execution status, THE Notebook_Ranker SHALL extract the status value
2. WHEN execution status is "complete" or "success", THE Notebook_Ranker SHALL apply a boost factor of 1.2
3. WHEN execution status is "error" or "failed", THE Notebook_Ranker SHALL apply a penalty factor of 0.6
4. WHEN execution status is unavailable, THE Notebook_Ranker SHALL apply no adjustment

### Requirement 5: Configurable Ranking Weights

**User Story:** As a system administrator, I want to adjust ranking weights without code changes, so that I can tune the algorithm based on user feedback.

#### Acceptance Criteria

1. THE Notebook_Ranker SHALL load ranking weights from configuration
2. WHEN configuration is missing, THE Notebook_Ranker SHALL use default weights
3. THE Notebook_Ranker SHALL validate that all weights are positive numbers
4. THE Notebook_Ranker SHALL normalize weights to sum to 1.0 before applying
5. WHERE weight configuration is updated, THE Notebook_Ranker SHALL apply new weights to subsequent ranking operations

### Requirement 6: Ranking Score Computation

**User Story:** As a developer, I want a transparent ranking algorithm, so that I understand why certain notebooks are prioritized.

#### Acceptance Criteria

1. THE Notebook_Ranker SHALL compute a base score from upvote count using logarithmic scaling
2. THE Notebook_Ranker SHALL multiply the base score by the time decay factor
3. THE Notebook_Ranker SHALL multiply the result by code quality factors
4. THE Notebook_Ranker SHALL multiply the result by execution status factor
5. THE Notebook_Ranker SHALL return notebooks sorted by final score in descending order

### Requirement 7: Ranking Metadata Exposure

**User Story:** As a developer, I want to see ranking scores and factors in the output, so that I can understand the ranking decisions.

#### Acceptance Criteria

1. WHEN returning ranked notebooks, THE Notebook_Ranker SHALL include the final ranking score
2. WHEN returning ranked notebooks, THE Notebook_Ranker SHALL include individual factor values
3. WHEN formatting output as TOON, THE Notebook_Ranker SHALL include ranking metadata in the notebooks section
4. WHEN formatting output as JSON, THE Notebook_Ranker SHALL include a ranking_details object for each notebook

### Requirement 8: Backward Compatibility

**User Story:** As a system maintainer, I want the new ranking system to work with existing cached data, so that we don't need to re-fetch all competitions.

#### Acceptance Criteria

1. WHEN notebook metadata lacks new fields, THE Notebook_Ranker SHALL compute scores using available data only
2. WHEN applying the ranking algorithm, THE Notebook_Ranker SHALL handle missing timestamps gracefully
3. WHEN processing legacy notebook objects, THE Notebook_Ranker SHALL not raise exceptions for missing fields
4. THE Notebook_Ranker SHALL maintain the same NotebookMeta interface for compatibility
