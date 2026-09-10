Feature: Getting a quote and buying a policy

  The first thing anyone touches. Five questions, three priced plans, and a
  policy at the end of it.

  The point worth watching is that the quote is an OBJECT. It has an id, it can
  be re-opened, and accepting it sells at the price it showed -- none of that
  state goes through the browser. Before it was an object, the answers were
  round-tripped in hidden form fields so accepting could recompute, which is
  the one place this demo did the opposite of what it claims.

  Background:
    Given the demo is running

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

    When I accept the Standard plan
    Then I am shown a policy
    And the policy was sold at the price the quote showed
    And I capture "the policy that was bought"

    When I re-open the quote by its id
    Then the quote names the policy it became
    And I capture "the quote remembers what it became"
