
# E-Presso Analytical Assistant — Testing

## Overview

The E-Presso application uses a rules-based analytical assistant that answers questions using approved Python functions. The assistant calculates results from the selected dataset, explains its findings, and provides a tool-call log for transparency.

## Test 1: Total Revenue

**Question:** What is our total revenue?

**Expected result:** $42,174,440.00

**Actual result:** $42,174,440.00

**Tool used:** get_total

**Status:** PASS

The assistant correctly calculated total revenue using all 25,200 sales records.

## Test 2: Revenue Comparison

**Question:** How did revenue change from 2027 to 2028?

**Expected results:**
- 2027: $8,824,720.00
- 2028: $8,969,470.00
- Increase: $144,750.00 (approximately 1.6%)

**Actual results:** Matched expected values.

**Tool used:** group_total

**Status:** PASS

The assistant correctly filtered the data by year, calculated revenue for each year, and reported the dollar and percentage changes.

## Test 3: Data Quality

**Question:** Are there any missing values or duplicate records in our sales data?

**Expected results:**
- Records examined: 25,200
- Completely duplicate rows: 0
- Columns with missing values: None

**Actual results:** Matched expected values.

**Tool used:** data_quality_report

**Status:** PASS

The assistant correctly identified that the Sales dataset contained no completely duplicate rows or missing values. This does not guarantee that every record is accurate.

## Test 4: Unsupported Analytical Question

**Question:** Why did customer satisfaction decrease in 2028?

**Expected behavior:** The assistant should acknowledge that it cannot determine the cause using its current approved analytical functions.

**Actual behavior:** The assistant explained its limitations and suggested additional analysis.

**Tool used:** None

**Status:** PASS

The assistant did not invent an explanation or make unsupported causal claims.

## Test 5: Updated Data

**Question:** What is our total revenue?

**Test procedure:**
1. Created a temporary copy of the Sales Excel workbook.
2. Increased one Revenue value by exactly $1,000.
3. Uploaded the modified workbook to Streamlit.
4. Checked the dashboard's Total Revenue.
5. Asked the assistant to calculate total revenue.
6. Removed the replacement workbook and restored the original dataset.

**Original revenue:** $42,174,440.00

**Modified revenue:** $42,175,440.00

**Expected change:** +$1,000.00

**Actual result:** Both the dashboard and assistant returned $42,175,440.00.

**Tool used:** get_total

**Status:** PASS

This test demonstrated that calculations respond to changes in the loaded data rather than relying on hardcoded totals.

## Improvement and Retesting

During development, the assistant initially returned overall revenue when asked for revenue in 2028.

The rules-based router was updated to recognize years in questions and apply a Year filter. The Sales dataset was also prepared with a Year column for the assistant.

**Retest question:** What was our total revenue in 2028?

**Retest result:** $8,969,470.00 using 5,040 sales records.

**Status:** PASS

## Current Limitations

- The assistant uses predefined rules rather than a generative language model.
- It supports only questions that match its approved routing rules.
- It cannot independently determine causes of business performance changes.
- Its responses depend on the dataset currently selected and loaded.
- Data-quality checks do not establish that every record is accurate.
- Tool-call logs are available in the application for inspection.