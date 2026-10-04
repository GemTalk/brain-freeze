Feature: Every claim on the book, in one list

  Claims are filed one policy at a time, but read across the whole book. The
  claims page lists them newest first -- by claim id, which is the order they
  were filed, since the seeded episodes are dated into 2027 -- a page at a
  time, and can be narrowed to the ones that were refused.

  The count it states has to be the book's, checked against the JSON
  surface rather than against a number written down here. And a claim id
  typed into its search box goes straight to that claim, as a policy id does
  on the policies page.

  Background:
    Given the app is running

  Scenario: the book's claims, newest first, narrowed, and found by id
    When I open the claims page
    Then the page says as many claims as the book holds
    And the claims are listed newest first
    And I capture "every claim, newest first"

    When I narrow the list to the refused claims
    Then every claim listed was refused
    And I capture "only the refused claims"

    When I search the claims for CLM-001285
    Then I am shown the decision on CLM-001285
    And I capture "a claim found by its id"
