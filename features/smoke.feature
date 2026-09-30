Feature: The app is up

  Proves the harness works -- the book is loaded, the app is serving inside
  the database, a real browser reaches it, and a screenshot lands. It asserts
  almost nothing about insurance; that is the other features' job.

  If this fails, nothing else in the suite is worth reading.

  Scenario: the customer picker is served from the database
    Given the app is running
    When I open the customer picker page
    Then the page says how many policyholders there are
    And I see "BF-100000"
    And I capture "the customer picker"
    And the app said it was running, and logged that request
