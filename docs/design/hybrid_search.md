# Hybrid Search & Reciprocal Rank Fusion (RRF) Guide

This guide explains conceptually how the AI Search Application retrieves relevant document passages to answer user queries. It focuses on the business and retrieval logic without detailing the technical database or code implementations.

---

## 1. What is Hybrid Search?

A search system must handle two fundamentally different types of queries:
1. **Exact Matches**: Queries searching for specific words, IDs, product codes, or exact terminology (e.g., "ERP", "GDPR", "Směrnice S-10.150").
2. **Conceptual Questions**: Queries written in natural conversational language that ask about a topic without knowing the exact words used in the documents (e.g., "how do we log working hours" when the document uses "evidence pracovní doby").

To solve this, our system runs two distinct search strategies in parallel and merges their results:

```
                  ┌───────────────────────┐
                  │      User Query       │
                  └──────────┬────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
   ┌────────────────────┐        ┌────────────────────┐
   │   Keyword Search   │        │  Semantic Search   │
   │  (Exact Matcher)   │        │ (Concept Matcher)  │
   └──────────┬─────────┘        └──────────┬─────────┘
              │                             │
              │  Ranked List                │  Ranked List
              └──────────────┬──────────────┘
                             ▼
               ┌───────────────────────────┐
               │ Reciprocal Rank Fusion    │
               │ (Weighted RRF Merge Step) │
               └─────────────┬─────────────┘
                             ▼
                  ┌───────────────────────┐
                  │ Unified Top Results   │
                  └───────────────────────┘
```

### Keyword Search (Lexical Matching)
* **How it works**: Scans the text files looking for the exact occurrences of the words in the query.
* **Strengths**: High precision for exact terminology, specific abbreviations, and names.
* **Weaknesses**: Cannot find information if the author used a synonym or a slightly different phrasing (e.g., searching for "contracts" will miss passages mentioning "agreements").

### Semantic Search (Vector Meaning Matching)
* **How it works**: Translates the mathematical "meaning" of the query into a high-dimensional concept space and finds passages whose semantic concepts are closest.
* **Strengths**: High recall. It understands synonyms, context, and intent. It finds answers even when there are zero overlapping words between the query and the document.
* **Weaknesses**: Can occasionally miss specific unique IDs or codes if they are semantically similar to generic terms.

---

## 2. Reciprocal Rank Fusion (RRF)

Because Keyword Search and Semantic Search produce entirely different scoring metrics (keyword density rank vs. concept distance scores), their scores cannot be compared directly. It is impossible to say whether a keyword score of `5.4` is better than a semantic similarity score of `0.82`.

To merge them fairly, we use **Reciprocal Rank Fusion (RRF)**.

### The Concept of RRF
Instead of looking at raw scores, RRF looks only at the **rank (position)** of a document in each search result. 
* A document ranked #1 is considered highly relevant.
* A document ranked #10 is less relevant.
* A document ranked #100 is very low relevance.

RRF rewards documents that appear near the top of either list, and heavily rewards documents that appear in **both** lists.

### The Scoring Formula
Each document's final RRF score is calculated as follows:

$$\text{RRF Score} = W_{\text{vector}} \times \left( \frac{1}{k + \text{Rank}_{\text{vector}}} \right) + W_{\text{keyword}} \times \left( \frac{1}{k + \text{Rank}_{\text{keyword}}} \right)$$

* **$\text{Rank}$**: The 1-based index of the document in the list (1 for #1, 2 for #2, etc.). If a document did not qualify for a list, its rank contribution is $0$.
* **$k$ (Smoothing Constant)**: Set to `60`. This prevents early ranks (like #1 vs #2) from completely dominating the scores, allowing high-quality runner-up documents to still be considered.
* **$W_{\text{vector}}$ (Semantic Weight)**: Set to `0.6` (60%). This represents the preference given to conceptual meaning.
* **$W_{\text{keyword}}$ (Keyword Weight)**: Set to `0.4` (40%). This represents the preference given to exact keyword hits.

By adjusting the weights ($0.6$ vs $0.4$), we ensure that the semantic concept is given a slightly higher priority, while exact keyword hits still act as a strong boost.

---

## 3. Concrete Search Example

To see RRF in action, let us walk through a small example using Czech corporate guidelines.

### Sample Document Passages
* **Passage A**: *"Evidence pracovní doby na vedení společnosti Dolphin Consulting podléhá kontrole a zapisuje se do interního ERP systému."*
* **Passage B**: *"Pravidla pro evidenci smluv v naší společnosti vyžadují zveřejňování každé písemné objednávky v registru smluv."*
* **Passage C**: *"Zpracování osobních údajů a ochrana soukromí zaměstnanců se řídí směrnicí GDPR."*

### The User Query
> **"Jaká jsou pravidla pro registr smluv?"**

---

### Step 1: Keyword Search Runs
The system cleans the query and looks for exact matches for the words **"pravidla"**, **"registr"**, and **"smluv"**.

1. **Passage B** contains "Pravidla", "registr", and "smluv". It is a perfect keyword match.
   * **Rank in Keyword Search**: **#1**
2. **Passage A** and **Passage C** contain none of these search words.
   * **Rank in Keyword Search**: **Unranked (Not found)**

---

### Step 2: Semantic Search Runs
The system translates the query "Jaká jsou pravidla pro registr smluv?" into its conceptual meaning (legal obligations, administrative procedures, and agreements tracking).

1. **Passage B** is highly relevant conceptually (explains the rules for contracts registry).
   * **Rank in Semantic Search**: **#1**
2. **Passage A** is somewhat relevant (discusses company administration rules, recording working hours, and the internal database ERP system).
   * **Rank in Semantic Search**: **#2**
3. **Passage C** is not relevant (deals with privacy and GDPR, not contracts).
   * **Rank in Semantic Search**: **Unranked**

---

### Step 3: Reciprocal Rank Fusion (RRF) Calculation
Now, we compute the fused RRF scores for each passage.

#### Calculating Passage B:
* **Semantic Rank**: #1 $\rightarrow$ Score Contribution: $0.6 \times \frac{1}{60 + 1} = 0.6 \times 0.01639 = 0.00983$
* **Keyword Rank**: #1 $\rightarrow$ Score Contribution: $0.4 \times \frac{1}{60 + 1} = 0.4 \times 0.01639 = 0.00656$
* **Total RRF Score**: $0.00983 + 0.00656 = \mathbf{0.01639}$

#### Calculating Passage A:
* **Semantic Rank**: #2 $\rightarrow$ Score Contribution: $0.6 \times \frac{1}{60 + 2} = 0.6 \times 0.01613 = 0.00968$
* **Keyword Rank**: Unranked $\rightarrow$ Score Contribution: $0$
* **Total RRF Score**: $0.00968 + 0 = \mathbf{0.00968}$

#### Calculating Passage C:
* Unranked in both lists.
* **Total RRF Score**: $\mathbf{0.00000}$

---

### Final Ranked Results Sent to LLM
The search system sorts the fused scores in descending order and returns the top matches:

| Position | Passage | RRF Score | Why it succeeded |
| :--- | :--- | :--- | :--- |
| **#1** | **Passage B** (Registr smluv) | **0.01639** | Ranked #1 in both semantic and keyword searches (Highest relevance). |
| **#2** | **Passage A** (Evidence pracovní doby) | **0.00968** | Ranked #2 in semantic search, despite having zero keyword overlaps. |

This combined list guarantees that the system returns Passage B as the absolute primary source of truth, while still providing Passage A as useful context, and completely discarding Passage C as irrelevant. The generative AI model then uses this filtered context to write its detailed answer.
