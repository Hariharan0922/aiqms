# Validation rules and generation gate

Rules are evaluated on the server against the exact template version, answers and applicability decisions for the selected document version.

| Rule code | Condition | Severity | Blocks generation |
|---|---|---|---|
| `FIELD_REQUIRED` | Required value missing/blank | blocker | yes |
| `FIELD_TYPE_INVALID` | Value type does not match field schema | error | yes |
| `FIELD_TOO_SHORT` | Text does not meet configured minimum length | error | yes |
| `FIELD_OPTION_INVALID` | Value is outside a controlled option list | error | yes |
| `FIELD_DATE_INVALID` | Date is not ISO `YYYY-MM-DD` | error | yes |
| `APPLICABILITY_UNRESOLVED` | Internal mapping has no applicable/not-applicable decision | blocker | yes |
| `APPLICABILITY_RATIONALE_REQUIRED` | Not-applicable decision has no rationale | blocker | yes |
| `REQUIREMENT_MAPPING_UNVERIFIED` | Requirement placeholder has not been validated against source text | warning | no, but review is required before release |

The generation gate rejects calls if there is no successful current validation run or if the version's validation state is stale. Input or applicability edits, and evidence uploads, invalidate the validation state.

## Resolution principles

- Correct missing or invalid input instead of dismissing a rule failure.
- A non-applicability decision must have a rationale and later be verified by an authorized quality role.
- Warnings are retained in the validation result and should be handled in review; they must not be hidden by the UI.
- The rule engine validates configured completeness and consistency only. It does not independently prove legal compliance, product safety, or ISO 13485 conformity.
- The optional local LLM does not currently participate in this validation gate. Later semantic suggestions should be stored as suggestions/findings and remain subject to deterministic rules and qualified human decisions.
