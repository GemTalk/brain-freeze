Feature: Filing a claim and being told what it pays

  The other half of CUJ-3, and the screen the demo's argument rests on. A
  claimant describes an episode -- what they ate, how much it hurt, how long it
  went on -- and is told what it pays. Nobody types a figure in: the severity
  implies the amount, and the app hands that to `brainfreeze.adjudicate` and
  reports what comes back. It works nothing out for itself, which is the only
  reason the notebook, the agent and this page can never disagree about a
  claim.

  So the decision is checked three times over. Against itself -- what it was
  assessed at, less what the episode cap took off, less the deductible, is
  what was paid. Against the rules module, driven with the terms and the
  claim count that this browser was shown rather than anything read from the
  database. And against the book afterwards: the claim is still there, with
  the same figures, and the policy's totals have moved by exactly it.

  Flavour and toppings are here too. They were added in CUJ-4 after 900
  policies were already committed, so a claim filed today has them and the
  2,172 filed before the questions existed do not.

  BF-100332 is this scenario's own policy, per the rule at the top of
  `tests/test_app.py`. This scenario WRITES, and the suite re-seeds once per
  run rather than once per scenario, so sharing a policy would make the order
  scenarios happen to run in part of the test.

  Background:
    Given the demo is running

  Scenario: an episode is assessed, capped, and paid, and the book agrees
    Given I open the policy BF-100332
    Then the policy is covered today
    And I note the cover terms and what the policy has claimed so far
    And I capture "the policy before the claim"

    When I go to file a claim
    Then nothing warns that a claim would be refused
    And I capture "what happened?"

    When I report ice cream, Mint choc chip, topped with Sprinkles and Hot fudge, pain 9, lasting Longer than ten
    Then I am shown a decision
    And the decision names the flavour and the toppings
    And the decision shows the assessment, the episode cap, the deductible and the payout
    And the amount assessed is what that severity is worth
    And those four figures add up
    And those four figures are the ones the rules give
    And I capture "the decision"

    When I open the policy BF-100332
    Then the claim is on the record with the figures the decision showed
    And it sits in date order, among episodes that have not happened yet
    And the policy's totals moved by exactly this claim
    And I capture "the claim on the record"
