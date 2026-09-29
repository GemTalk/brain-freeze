@tutorial
Feature: Step 2 -- launch the web app

  The README's second step: look around, get a quote, buy the policy, file a
  claim against it -- then stop the app and start it again, and find both
  still there. Nothing was saved, because nothing needed to be.

  Scenario: a policy bought and a claim filed are still there after a restart
    When I open the customer picker page
    Then the page says how many policyholders there are
    And I capture "the customers"

    When I open the policy BF-100539
    Then I am shown a policy
    And I capture "one policyholder's history"

    When I open the quote page
    And I answer age 9, no migraine, no tension headaches, eating fast, on slushies
    Then the quote prices all three plans
    And I capture "a quote"

    When I accept the Standard plan
    Then I am shown a policy
    And I capture "the policy I bought"

    When I go to file a claim
    And I report ice cream, pain 9, lasting Longer than ten
    Then I am shown a decision
    And I capture "the claim I filed"

    When the app is stopped and started again
    And I go back to the policy I bought
    Then the claim I filed is on it
    And I capture "both still there after a restart"
