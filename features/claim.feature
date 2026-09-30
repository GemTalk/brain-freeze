Feature: Filing a claim and being told what it pays

  A claimant describes an episode -- what they ate, how much it hurt, how long
  it went on -- and is told what it pays. Nobody types a figure in: the
  severity implies the amount, and the app hands that to
  `brainfreeze.adjudicate` and reports what comes back. It works nothing out
  for itself, which is why the notebook, the agent and this page cannot
  disagree about a claim.

  So the decision is checked three ways: against itself (assessed, less the
  episode cap, less the deductible, is what was paid); against the rules,
  driven with the terms this browser was shown; and against the book
  afterwards, where the claim is on record and the policy's totals moved by
  exactly it.

  BF-100332 is this scenario's own policy, per the rule at the top of
  `tests/test_app.py`: it writes, and the book is loaded once per run.

  Background:
    Given the app is running

  Scenario: an episode is assessed, capped, and paid, and the book agrees
    Given I open the policy BF-100332
    Then the policy is covered today
    And I note the cover terms and what the policy has claimed so far
    And I capture "the policy before the claim"

    When I go to file a claim
    Then nothing warns that a claim would be refused
    And I capture "what happened?"

    When I report ice cream, pain 9, lasting Longer than ten
    Then I am shown a decision
    And the decision names what was eaten
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
