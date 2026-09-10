Feature: The demo is up

  The walking skeleton. It proves the harness works -- the book is seeded, the
  app is serving inside the database, a real browser reaches it, and a
  screenshot lands -- and it asserts almost nothing about insurance, because
  that is the other features' job.

  If this fails, nothing else in the suite is worth reading.

  Scenario: the customer picker is served from the database
    Given the demo is running
    When I open the customer picker page
    Then the page mentions 900 policyholders
    And I see "BF-100000"
    And I capture "the customer picker"
