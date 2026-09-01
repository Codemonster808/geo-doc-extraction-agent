Feature: Intake gateway dedup and validation
  Spec: docs/specs/spec-confidence-gated-extraction.md

  Scenario: a new document is accepted
    Given a report with id INTAKE-NEW-001 and unique text long enough to be a real report
    When the document is uploaded to the intake gateway
    Then the gateway responds 200 accepted

  Scenario: the same content re-uploaded under a different report id is rejected as a duplicate
    Given a report with id INTAKE-DUP-001 and unique text long enough to be a real report
    And the document has already been uploaded once
    When the same content is uploaded again with report id INTAKE-DUP-002
    Then the gateway responds 409 duplicate
    And the response includes the content_hash

  Scenario: text under 20 characters is rejected as too short to be a real report
    Given a report with id INTAKE-SHORT-001 and text "too short"
    When the document is uploaded to the intake gateway
    Then the gateway responds 400 rejected
