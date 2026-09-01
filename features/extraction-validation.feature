Feature: Domain validation of extracted geology records
  Spec: docs/specs/spec-confidence-gated-extraction.md

  Scenario: New York coordinates are rejected even though they are valid floats
    Given a record that would type-check with lat 40.7 and lon -74.0
    When ExtractedRecord is constructed
    Then validation fails because the point is outside the survey region

  Scenario: a 50000 m depth is rejected
    Given a record with depth_m 50000
    When ExtractedRecord is constructed
    Then validation fails because depth is out of plausible range

  Scenario: a mineral not on the whitelist is rejected
    Given a record with mineral Unobtainium
    When ExtractedRecord is constructed
    Then validation fails because the mineral is not recognized
