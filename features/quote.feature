Feature: Getting a quote and buying a policy

  Five questions, three priced plans, and a policy at the end of it -- shown
  as its ID card.

  The quote is an object. It has an id, it can be re-opened, and accepting it
  sells at the price it showed -- none of that state goes through the
  browser.

  Background:
    Given the app is running

  Scenario: a quote is an object, and the policy is sold at the price it showed
    When I open the quote page
    And I capture "the five questions"

    When I answer age 9, no migraine, no tension headaches, eating fast, on slushies
    Then I am shown a saved quote
    And the quote prices all three plans
    And no state is hidden in the page
    And I capture "three plans, priced"

    When I re-open the quote by its id
    Then the quote prices all three plans
    And I capture "the same quote, re-opened"

    When I accept the Sundae plan
    Then I am shown a policy
    And I am shown its ID card
    And the policy was sold at the price the quote showed
    And I capture "the policy that was bought"
    And its card can be kept as an SVG of the same policy

    When I re-open the quote by its id
    Then the quote names the policy it became
    And I capture "the quote remembers what it became"
