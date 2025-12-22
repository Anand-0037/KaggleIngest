# TOON Specification v1.0
**Token-Oriented Object Notation**

## 1. Introduction
TOON is a minimal, token-efficient serialization format designed specifically for appending structured data into LLM context windows. It prioritizes high information density and human readability over strict machine parseability (though it remains machine-parseable).

**Goals:**
1.  **Token Efficiency**: Reduce token count by 30-50% compared to JSON.
2.  **Readability**: Look like a natural document structure.
3.  **Parsability**: RegEx-friendly headers for sections.

## 2. Structure
A TOON document consists of sequential **Sections**. Each section starts with a header line defined as `section_name{comma,separated,keys}` followed by data lines.

### 2.1 Header Format
```
section_name{key1,key2,key3}
```
*   `section_name`: Lowercase identifier (e.g., `metadata`, `notebooks`).
*   `{...}`: Definition of column names (for tabular data) or keys (for key-value pairs).

### 2.2 Data Format
Data follows immediately after the header.

**Key-Value Type (Single Row)**
Used for metadata.
```
metadata{Title,URL,Status}
Titanic Survival,https://kaggle.com/c/titanic,Active
```

**Tabular Type (Multiple Rows)**
Used for lists or datasets.
```
notebooks{id,author,score}
1,Manav Sehgal,0.92
2,Yassine Ghouzam,0.89
```

### 2.3 Special Field Handling
*   **Lists**: Enclosed in `[]`. Example: `[col1, col2, col3]`
*   **Multiline Text**: If a field contains newlines (e.g., code blocks), it SHOULD be strictly escaped or (preferred in TOON) placed in a separate generic block if it's large content.
*   *Note: For the current implementation, large content blocks (like notebook cells) are separated by standard Markdown headers outside the TOON tabular structure.*

## 3. Standard Sections as of v1.0

### `metadata`
Required. Contains high-level resource info.
```
metadata{title,url,description,source}
```

### `schema`
Optional. Describes attached CSV files.
```
schema{filename,columns,sample_rows}
```

### `notebooks`
Optional. Summary of included notebooks.
```
notebooks{index,title,author,votes,url}
```

### `statistics`
Optional. Execution stats.
```
statistics{requested,successful,failed,duration_seconds}
```

## 4. Example Document

```text
metadata{Title,URL,Type}
Titanic Competition,https://kaggle.com/c/titanic,Competition

schema{File,Columns}
train.csv,[PassengerId, Survived, Pclass]
test.csv,[PassengerId, Pclass]

notebooks{index,title,votes}
1,EDA To Prediction,1200
2,Titanic Top 4%,980
```
