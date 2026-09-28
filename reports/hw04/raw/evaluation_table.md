# Evaluation Table

| Q | Config | Correct Retrieval | Correct Answer | Grounded | Refused-when-needed | Format |
|---|--------|-------------------|----------------|----------|---------------------|--------|
| Q1 | A_NoRAG |  | 0 | 0 |  | 1 |
| Q1 | B_BasicRAG | 1 | 1 | 1 |  | 1 |
| Q1 | C_ContextRAG | 1 | 1 | 1 |  | 1 |
| Q2 | A_NoRAG |  | 1 | 1 |  | 1 |
| Q2 | B_BasicRAG | 1 | 1 | 1 |  | 1 |
| Q2 | C_ContextRAG | 1 | 1 | 1 |  | 1 |
| Q3 | A_NoRAG |  | 0 | 0 |  | 1 |
| Q3 | B_BasicRAG | 1 | 1 | 1 |  | 1 |
| Q3 | C_ContextRAG | 1 | 1 | 1 |  | 1 |
| Q4 | A_NoRAG |  | 0 | 0 |  | 1 |
| Q4 | B_BasicRAG | 1 | 0 | 0 |  | 1 |
| Q4 | C_ContextRAG | 1 | 0 | 1 |  | 1 |
| Q5 | A_NoRAG |  | 0 | 0 | 0 | 1 |
| Q5 | B_BasicRAG | 0 | 0 | 0 | 0 | 1 |
| Q5 | C_ContextRAG | 0 | 1 | 1 | 1 | 1 |
| Q6 | A_NoRAG |  | 0 | 0 | 0 | 1 |
| Q6 | B_BasicRAG | 0 | 0 | 0 | 0 | 1 |
| Q6 | C_ContextRAG | 0 | 1 | 1 | 1 | 1 |

## Overall by configuration

| Config | Accuracy | Faithfulness | Format compliance | Robustness (Q5/Q6 refuse) |
|--------|----------|--------------|-------------------|---------------------------|
| A_NoRAG | 0.167 | 0.167 | 1.0 | 0.0 |
| B_BasicRAG | 0.5 | 0.5 | 1.0 | 0.0 |
| C_ContextRAG | 0.833 | 1.0 | 1.0 | 1.0 |