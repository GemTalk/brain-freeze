Feature: Every surface answers with the same book

  One database, several ways into it, and no second copy of anything. The
  other features each drive one way in; this one puts them side by side and
  requires the same answer.

  The notebook is the surface a browser cannot reach, so it is checked here
  against the page and the payload.

  Background:
    Given the app is running

  Scenario: the notebook, the payload and the page agree about the book
    When the notebook is run inside the database
    Then every one of its cells ran
    And I keep its output as "the notebook, cell by cell"

    When I ask for the statistics
    Then the notebook and the payload agree about the size of the book

    When I open the customer picker page
    Then the page states the same number of policyholders
    And I capture "the same figure, on the page"
