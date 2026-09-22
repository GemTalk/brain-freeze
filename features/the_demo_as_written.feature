Feature: The demo, in the order the presenter walks it

  Every other feature here proves a part. `quote.feature` proves a quote is an
  object, `claim.feature` proves the arithmetic, `cross_surface.feature` proves
  another session can move the book under a running app. Nothing proved the
  SEQUENCE, and the sequence is the product: `DEMO.md` chains beats 2, 3 and 6
  onto a single policy, and each link was only ever checked in isolation.

  That gap is not theoretical. The demo script and the notebook drifted apart
  for five days -- the script stopped filing a claim while the notebook went on
  saying "the claim filed in the browser is in the notebook's objects" -- and
  every test in this suite stayed green, because no test read the script as a
  running order.

  WHY THIS SCENARIO CLAIMS AGAINST THE POLICY IT JUST BOUGHT

  `DEMO.md` beat 3 files its claim against BF-100332. This scenario cannot:
  BF-100332 is `claim.feature`'s own policy, the suite seeds once per run
  rather than once per scenario, and two scenarios writing to one policy would
  make the order behave happens to run them in part of the test.

  So it claims against the policy it bought a moment earlier, which is the
  same thing in every way the figures care about. Both are Standard, so both
  carry a $60.00 episode cap and a $5.00 deductible, and the assessment
  depends only on the pain score and the duration. The four figures are
  therefore the ones the script promises. It is also closer to what DEMO.md
  says it is doing -- "the spine is one policy" -- than the script itself is.

  WHERE THE FIGURES COME FROM

  Not from this file. The step reads them out of `DEMO.md`, so the chain is:
  `tests/test_demo_script.py` proves the script's figures are what the rules
  give, and this proves the browser shows the script's figures. Change the
  rules without changing the script and the unit test fails; change the script
  without changing the app and this fails.

  The policy is left lapsed. Nothing else uses it -- it did not exist when the
  run started -- and the reseed at the top of the next run is the reset.

  Background:
    Given the demo is running

  Scenario: the spine holds, from the front door to the refusal
    When I open the customer picker page
    Then the page says how many policyholders there are
    And I capture "beat 1 -- an insurance company"

    When I open the quote page
    And I answer age 9, no migraine, no tension headaches, eating fast, on slushies
    Then I am shown a saved quote
    And the quote scores 85.0 and bands it High
    And the quote prices all three plans
    And the Standard plan is priced at the figure DEMO.md quotes
    And no state is hidden in the page
    And I capture "beat 2 -- the quote is an object"

    When I accept the Standard plan
    Then I am shown a policy
    And the policy was sold at the price the quote showed
    And the policy it sold is one the seeded book did not contain
    And I capture "beat 2 -- the policy it became"

    When I re-open the quote by its id
    Then the quote names the policy it became
    And I capture "beat 2 -- the quote remembers"

    When I re-open that policy
    Then the policy is covered today
    And I note the cover terms and what the policy has claimed so far

    When I open that policy's claim form
    Then I am invited to file a claim
    And nothing warns that a claim would be refused

    When I report slushie, Mint choc chip, topped with Sprinkles and Hot fudge, pain 9, lasting Longer than ten
    Then I am shown a decision
    And the decision shows the assessment, the episode cap, the deductible and the payout
    And those four figures add up
    And the decision reads the figures DEMO.md promises
    And I capture "beat 3 -- the decision"

    When another session lapses that policy
    And I re-open that policy
    Then the policy is shown as lapsed
    And the app was never restarted
    And I capture "beat 6 -- moved by another session"

    When I open that policy's claim form
    Then I am told cover has ended
    And I capture "beat 6 -- the refusal that names the date"
